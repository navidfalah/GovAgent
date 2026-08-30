"""FastAPI application schemas — request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from govagents.core.models import (
    AssessmentStatus,
    ComplianceStatus,
    DecisionType,
    EvidenceStrength,
    GovernanceReport,
    RiskLevel,
)


class AssessmentRequest(BaseModel):
    """Request body for submitting a new governance assessment."""

    title: str = Field(..., min_length=5, max_length=200, description="Short title for the proposal")
    description: str = Field(..., min_length=20, description="Full description of the AI system or deployment proposal")
    organization: str | None = Field(None, description="Deploying organization name")
    sector: str | None = Field(None, description="Industry sector (healthcare, finance, public-sector, etc.)")
    deployment_context: str | None = Field(None, description="Where and how the system will be deployed")
    technical_details: str | None = Field(None, description="Technical architecture and implementation details")

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Employee Productivity Monitoring AI",
                "description": "A company wants to deploy an AI system that analyzes employee communications to identify productivity problems and flag underperforming employees.",
                "organization": "Acme Corp",
                "sector": "enterprise",
                "deployment_context": "Internal HR system monitoring all employee Slack and email communications",
                "technical_details": "NLP model analyzing text sentiment and communication patterns. Outputs productivity scores updated daily."
            }
        }
    }


class AssessmentCreatedResponse(BaseModel):
    """Response after creating a new assessment."""

    assessment_id: str
    status: AssessmentStatus
    message: str
    stream_url: str


class AssessmentSummary(BaseModel):
    """Brief summary of an assessment (for list views)."""

    id: str
    proposal_title: str
    status: AssessmentStatus
    decision: DecisionType | None = None
    overall_risk: RiskLevel | None = None
    compliance_confidence: float | None = None
    created_at: datetime
    completed_at: datetime | None = None
    processing_time_seconds: float | None = None


class PolicySourceResponse(BaseModel):
    """Response for a policy source."""

    id: str
    name: str
    version: str
    type: str
    jurisdiction: str
    description: str
    chunk_count: int = 0


class CorpusStatusResponse(BaseModel):
    """Status of the policy corpus."""

    total_chunks: int
    sources: list[PolicySourceResponse]
    embedding_model: str
    status: str  # ready | empty | loading


class HealthResponse(BaseModel):
    """API health check response."""

    status: str
    version: str
    corpus_ready: bool
    corpus_chunks: int
