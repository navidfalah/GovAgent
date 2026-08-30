"""Orchestrator — coordinates the multi-agent governance assessment pipeline."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import AsyncIterator, Callable

import govagents.agents  # Trigger registry decorators
from govagents.core.registry import registry
from govagents.core.llm import LLMClient, get_llm_client
from govagents.core.logging import get_logger
from govagents.core.models import (
    AgentContext,
    GovernanceReport,
    Proposal,
    SSEEvent,
)
from govagents.orchestration.debate import DebateProtocol
from govagents.orchestration.message_bus import MessageBus

log = get_logger(__name__)


class Coordinator:
    """Orchestrates the multi-agent governance assessment pipeline.

    Pipeline:
    1. [PARALLEL] Policy Agent + Risk Agent + Technical Agent
    2. [SEQUENTIAL] Compliance Agent (needs policy output)
    3. [SEQUENTIAL] Ethics Agent (needs risk output)
    4. [OPTIONAL] Debate Protocol (if disagreements detected)
    5. [FINAL] Governance Agent (synthesizes all)

    Streams SSE events at each stage for real-time frontend updates.
    """

    def __init__(
        self,
        llm: LLMClient | None = None,
        message_bus: MessageBus | None = None,
    ) -> None:
        self.llm = llm or get_llm_client()
        self.bus = message_bus or MessageBus()
        self.debate = DebateProtocol(llm=self.llm)

        # Initialize all agents using the Registry
        self.policy_agent = registry.get_agent_class("PolicyAgent")(llm_client=self.llm)
        self.risk_agent = registry.get_agent_class("RiskAgent")(llm_client=self.llm)
        self.technical_agent = registry.get_agent_class("TechnicalAgent")(llm_client=self.llm)
        self.compliance_agent = registry.get_agent_class("ComplianceAgent")(llm_client=self.llm)
        self.ethics_agent = registry.get_agent_class("EthicsAgent")(llm_client=self.llm)
        self.governance_agent = registry.get_agent_class("GovernanceAgent")(llm_client=self.llm)

    async def assess(
        self,
        proposal: Proposal,
        sse_callback: Callable[[SSEEvent], None] | None = None,
    ) -> GovernanceReport:
        """Run the full governance assessment pipeline for a proposal.

        Args:
            proposal: The AI system proposal to assess
            sse_callback: Optional callback for streaming SSE events

        Returns:
            GovernanceReport with the final governance decision
        """
        start_time = time.perf_counter()
        context = AgentContext(proposal=proposal)

        async def emit(event_name: str, agent: str | None = None, data: dict = {}) -> None:
            event = SSEEvent(event=event_name, agent=agent, data=data)
            await self.bus.emit_sse(event)
            if sse_callback:
                sse_callback(event)

        log.info("pipeline_start", proposal_id=proposal.id, title=proposal.title)

        try:
            # ── DAG Execution (Parallel Paths) ────────────────────────────────
            await emit("phase_start", data={"phase": "parallel_dag_execution", "phase_num": 1})

            async def path_policy_compliance():
                policy_out = None
                if proposal.pipeline_config.policy.enabled:
                    await emit("agent_start", agent="policy", data={"message": "Searching policy corpus..."})
                    policy_out = await self.policy_agent.run(context)
                    await emit("agent_complete", agent="policy", data={
                        "requirements": len(policy_out.requirements),
                        "message": f"Found {len(policy_out.requirements)} applicable requirements"
                    })
                
                compliance_out = None
                if proposal.pipeline_config.compliance.enabled:
                    await emit("agent_start", agent="compliance", data={"message": "Checking compliance with requirements..."})
                    compliance_out = await self.compliance_agent.run(context)
                    await emit("agent_complete", agent="compliance", data={
                        "status": compliance_out.overall_status.value,
                        "score": round(compliance_out.overall_compliance_score, 2),
                        "message": f"Compliance: {compliance_out.overall_status.value} ({compliance_out.overall_compliance_score:.0%})"
                    })
                return policy_out, compliance_out

            async def path_risk_ethics():
                risk_out = None
                if proposal.pipeline_config.risk.enabled:
                    await emit("agent_start", agent="risk", data={"message": "Analyzing risks..."})
                    risk_out = await self.risk_agent.run(context)
                    await emit("agent_complete", agent="risk", data={
                        "risk_level": risk_out.overall_risk_level.value,
                        "risks": len(risk_out.risks),
                        "message": f"Identified {len(risk_out.risks)} risks — Overall: {risk_out.overall_risk_level.value}"
                    })
                
                ethics_out = None
                if proposal.pipeline_config.ethics.enabled:
                    await emit("agent_start", agent="ethics", data={"message": "Evaluating ethical dimensions..."})
                    ethics_out = await self.ethics_agent.run(context)
                    await emit("agent_complete", agent="ethics", data={
                        "score": round(ethics_out.overall_score, 2),
                        "dimensions": len(ethics_out.dimensions),
                        "message": f"Ethics score: {ethics_out.overall_score:.0%}"
                    })
                return risk_out, ethics_out

            async def path_technical():
                technical_out = None
                if proposal.pipeline_config.technical.enabled:
                    await emit("agent_start", agent="technical", data={"message": "Analyzing technical architecture..."})
                    technical_out = await self.technical_agent.run(context)
                    await emit("agent_complete", agent="technical", data={
                        "findings": len(technical_out.findings),
                        "compliant": technical_out.architecture_compliant,
                        "message": f"Found {len(technical_out.findings)} technical findings"
                    })
                return technical_out

            # Run all configured DAG paths in parallel
            await asyncio.gather(
                path_policy_compliance(),
                path_risk_ethics(),
                path_technical(),
                return_exceptions=False,
            )

            # ── Phase 4: Debate (if disagreements) ───────────────────────────
            debate_log = []
            disagreements = self.debate.detect_disagreements(context)
            if disagreements:
                await emit("debate_start", data={
                    "disagreements": len(disagreements),
                    "message": f"Detected {len(disagreements)} disagreement(s) — running debate..."
                })
                log.info("running_debate", disagreements=len(disagreements))
                debate_log = await self.debate.run_debate(context, disagreements)
                await emit("debate_complete", data={
                    "rounds": len(debate_log),
                    "message": f"Debate complete — {len(debate_log)} disagreement(s) resolved"
                })

            # ── Phase 5: Governance Decision ──────────────────────────────────
            await emit("phase_start", data={"phase": "governance_decision", "phase_num": 5})
            await emit("agent_start", agent="governance", data={"message": "Synthesizing final governance decision..."})
            report = await self.governance_agent.run(context)

            # Add debate outcomes to report
            if debate_log:
                report.debate_rounds = debate_log
                report.agent_disagreements = [
                    d.get("disagreement", {}).get("description", "") for d in debate_log
                ]

            elapsed = time.perf_counter() - start_time
            report.processing_time_seconds = elapsed
            report.total_tokens_used = self.llm.get_usage_stats()["total_tokens"]
            
            if hasattr(report, "completed_at"):
                report.completed_at = datetime.utcnow()

            await emit("agent_complete", agent="governance", data={
                "decision": report.decision.value,
                "risk": report.overall_risk.value,
                "confidence": round(report.compliance_confidence, 2),
                "message": f"Decision: {report.decision.value}"
            })

            await emit("done", data={
                "report_id": report.id,
                "decision": report.decision.value,
                "elapsed_seconds": round(elapsed, 1),
            })

            log.info(
                "pipeline_complete",
                proposal_id=proposal.id,
                decision=report.decision.value,
                elapsed_s=round(elapsed, 1),
                tokens=report.total_tokens_used,
            )
            return report

        except Exception as e:
            log.error("pipeline_error", error=str(e), proposal_id=proposal.id, exc_info=True)
            await emit("error", data={"error": str(e)})
            raise

    def create_sse_stream(self) -> asyncio.Queue:
        """Create a new SSE stream queue."""
        return self.bus.add_sse_queue()

    def remove_sse_stream(self, q: asyncio.Queue) -> None:
        """Remove an SSE stream queue."""
        self.bus.remove_sse_queue(q)
