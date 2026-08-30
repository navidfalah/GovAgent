"""Assessment routes — submit, stream, and retrieve governance assessments."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sse_starlette.sse import EventSourceResponse

from govagents.api.schemas import (
    AssessmentCreatedResponse,
    AssessmentSummary,
)
from govagents.core.logging import get_logger
from govagents.core.models import (
    AssessmentRecord,
    AssessmentRequest,
    AssessmentStatus,
    GovernanceReport,
    Proposal,
    SSEEvent,
)

log = get_logger(__name__)

router = APIRouter(prefix="/api/assess", tags=["assessments"])

# In-memory assessment store (replace with DB for production)
_assessments: dict[str, AssessmentRecord] = {}
# SSE queues per assessment: assessment_id -> list of queues
_sse_queues: dict[str, list[asyncio.Queue]] = {}


@router.post("", response_model=AssessmentCreatedResponse, status_code=202)
async def create_assessment(
    request: AssessmentRequest,
    background_tasks: BackgroundTasks,
) -> AssessmentCreatedResponse:
    """Submit an AI system proposal for governance assessment.

    This starts the assessment pipeline asynchronously.
    Use the stream endpoint to receive real-time updates.
    """
    from govagents.policies.ingestion import ingest_policies

    proposal = Proposal(
        title=request.title,
        description=request.description,
        organization=request.organization,
        sector=request.sector,
        deployment_context=request.deployment_context,
        technical_details=request.technical_details,
    )

    record = AssessmentRecord(
        id=proposal.id,
        proposal=proposal,
        status=AssessmentStatus.PENDING,
    )
    _assessments[record.id] = record
    _sse_queues[record.id] = []

    # Run assessment in background
    background_tasks.add_task(_run_assessment_task, record.id)

    log.info("assessment_created", id=record.id, title=proposal.title)

    return AssessmentCreatedResponse(
        assessment_id=record.id,
        status=AssessmentStatus.PENDING,
        message="Assessment queued. Connect to the stream URL to receive real-time updates.",
        stream_url=f"/api/assess/{record.id}/stream",
    )


async def _run_assessment_task(assessment_id: str) -> None:
    """Background task that runs the full assessment pipeline."""
    from govagents.core.llm import get_llm_client
    from govagents.orchestration.coordinator import Coordinator
    from govagents.policies.ingestion import ingest_policies

    record = _assessments.get(assessment_id)
    if not record:
        return

    record.status = AssessmentStatus.RUNNING

    try:
        # Ensure policies are ingested
        await ingest_policies()

        # Create coordinator with SSE callback
        coordinator = Coordinator()

        def sse_callback(event: SSEEvent) -> None:
            """Broadcast SSE event to all connected clients for this assessment."""
            queues = _sse_queues.get(assessment_id, [])
            for q in queues:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    pass

        report = await coordinator.assess(record.proposal, sse_callback=sse_callback)

        record.report = report
        record.status = AssessmentStatus.COMPLETED
        record.completed_at = datetime.now(timezone.utc)

        log.info(
            "assessment_complete",
            id=assessment_id,
            decision=report.decision.value,
        )

    except Exception as e:
        log.error("assessment_failed", id=assessment_id, error=str(e), exc_info=True)
        record.status = AssessmentStatus.FAILED
        record.error = str(e)

        # Send error event to all listeners
        error_event = SSEEvent(event="error", data={"error": str(e)})
        for q in _sse_queues.get(assessment_id, []):
            try:
                q.put_nowait(error_event)
            except asyncio.QueueFull:
                pass


@router.get("/{assessment_id}/stream")
async def stream_assessment(assessment_id: str) -> EventSourceResponse:
    """Stream real-time assessment updates via Server-Sent Events.

    Connect to this endpoint to receive live agent activity updates
    as the governance assessment pipeline executes.
    """
    if assessment_id not in _assessments:
        raise HTTPException(status_code=404, detail="Assessment not found")

    record = _assessments[assessment_id]

    async def event_generator():
        # If assessment is already complete, send final report immediately
        if record.status == AssessmentStatus.COMPLETED and record.report:
            yield {
                "event": "done",
                "data": json.dumps(
                    {
                        "report_id": record.report.id,
                        "decision": record.report.decision.value,
                        "elapsed_seconds": record.report.processing_time_seconds,
                    }
                ),
            }
            return

        if record.status == AssessmentStatus.FAILED:
            yield {"event": "error", "data": json.dumps({"error": record.error})}
            return

        # Create a queue for this client
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        _sse_queues[assessment_id].append(queue)

        try:
            # Send initial connected event
            yield {"event": "connected", "data": json.dumps({"assessment_id": assessment_id})}

            while True:
                try:
                    event: SSEEvent = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {
                        "event": event.event,
                        "data": json.dumps(
                            {
                                "agent": event.agent,
                                "timestamp": event.timestamp.isoformat(),
                                **event.data,
                            }
                        ),
                    }
                    if event.event in ("done", "error"):
                        break
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield {"event": "ping", "data": json.dumps({"status": record.status.value})}
        finally:
            if queue in _sse_queues.get(assessment_id, []):
                _sse_queues[assessment_id].remove(queue)

    return EventSourceResponse(event_generator())


@router.get("/{assessment_id}", response_model=AssessmentRecord)
async def get_assessment(assessment_id: str) -> AssessmentRecord:
    """Get the full assessment record including the governance report."""
    record = _assessments.get(assessment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return record


@router.get("", response_model=list[AssessmentSummary])
async def list_assessments() -> list[AssessmentSummary]:
    """List all assessments (most recent first)."""
    summaries = []
    for record in sorted(
        _assessments.values(), key=lambda r: r.created_at, reverse=True
    ):
        report = record.report
        summaries.append(
            AssessmentSummary(
                id=record.id,
                proposal_title=record.proposal.title,
                status=record.status,
                decision=report.decision if report else None,
                overall_risk=report.overall_risk if report else None,
                compliance_confidence=report.compliance_confidence if report else None,
                created_at=record.created_at,
                completed_at=record.completed_at,
                processing_time_seconds=report.processing_time_seconds if report else None,
            )
        )
    return summaries


@router.delete("/{assessment_id}", status_code=204)
async def delete_assessment(assessment_id: str) -> None:
    """Delete an assessment record."""
    if assessment_id not in _assessments:
        raise HTTPException(status_code=404, detail="Assessment not found")
    del _assessments[assessment_id]
    _sse_queues.pop(assessment_id, None)
