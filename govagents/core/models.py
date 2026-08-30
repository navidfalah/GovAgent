"""Shared Pydantic data models for GovAgents."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enumerations ──────────────────────────────────────────────────────────────


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ComplianceStatus(str, Enum):
    SATISFIED = "SATISFIED"
    PARTIALLY_SATISFIED = "PARTIALLY_SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DecisionType(str, Enum):
    APPROVED = "APPROVED"
    CONDITIONAL_APPROVAL = "CONDITIONAL_APPROVAL"
    REJECTED = "REJECTED"
    ABSTAINED = "ABSTAINED"  # insufficient evidence


class EvidenceStrength(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    NONE = "NONE"


class AgentRole(str, Enum):
    POLICY = "policy"
    COMPLIANCE = "compliance"
    RISK = "risk"
    ETHICS = "ethics"
    TECHNICAL = "technical"
    GOVERNANCE = "governance"
    ORCHESTRATOR = "orchestrator"


class MessageType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    DEBATE_CHALLENGE = "debate_challenge"
    DEBATE_REPLY = "debate_reply"
    FINAL = "final"


# ── Policy Models ─────────────────────────────────────────────────────────────


class PolicySource(BaseModel):
    """Represents a policy document source."""

    id: str
    name: str
    version: str = "1.0"
    type: str  # regulation | standard | guideline | framework
    jurisdiction: str = "international"
    effective_date: str | None = None
    url: str | None = None
    description: str = ""


class PolicyChunk(BaseModel):
    """A chunk of policy text ready for embedding."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    source_name: str
    article: str | None = None
    section: str | None = None
    requirement_type: str | None = None  # transparency | oversight | privacy | etc.
    text: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyRequirement(BaseModel):
    """A specific governance requirement extracted from policy."""

    id: str
    source_id: str
    source_name: str
    article: str | None = None
    title: str
    text: str
    requirement_type: str
    relevance_score: float = 0.0
    tags: list[str] = Field(default_factory=list)


# ── Proposal Models ───────────────────────────────────────────────────────────


class Proposal(BaseModel):
    """An AI system or deployment proposal to be assessed."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    organization: str | None = None
    sector: str | None = None  # healthcare | finance | public-sector | etc.
    deployment_context: str | None = None
    technical_details: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Agent Assessment Models ───────────────────────────────────────────────────


class RequirementAssessment(BaseModel):
    """An agent's assessment of a single policy requirement."""

    requirement_id: str
    requirement_title: str
    status: ComplianceStatus
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_strength: EvidenceStrength = EvidenceStrength.NONE
    reasoning: str
    evidence_citations: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class RiskItem(BaseModel):
    """An identified risk."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    category: str  # technical | organizational | legal | ethical | operational
    likelihood: float = Field(ge=0.0, le=1.0)
    impact: float = Field(ge=0.0, le=1.0)
    severity: RiskLevel
    affected_requirements: list[str] = Field(default_factory=list)
    mitigation: str = ""


class EthicsDimension(BaseModel):
    """Assessment of a single ethics/sovereignty dimension."""

    dimension: str  # transparency | accountability | privacy | oversight | autonomy | sovereignty
    score: float = Field(ge=0.0, le=1.0)
    status: ComplianceStatus
    reasoning: str
    concerns: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class TechnicalFinding(BaseModel):
    """A technical architecture finding."""

    title: str
    severity: RiskLevel
    description: str
    implication: str
    recommendation: str


# ── Agent Output Models ───────────────────────────────────────────────────────


class PolicyAgentOutput(BaseModel):
    requirements: list[PolicyRequirement]
    search_queries: list[str] = Field(default_factory=list)
    total_policies_searched: int = 0
    reasoning: str = ""


class ComplianceAgentOutput(BaseModel):
    requirement_assessments: list[RequirementAssessment]
    overall_compliance_score: float = Field(ge=0.0, le=1.0, default=0.0)
    overall_status: ComplianceStatus = ComplianceStatus.UNKNOWN
    reasoning: str = ""


class RiskAgentOutput(BaseModel):
    risks: list[RiskItem]
    overall_risk_level: RiskLevel = RiskLevel.MEDIUM
    risk_score: float = Field(ge=0.0, le=1.0, default=0.5)
    reasoning: str = ""


class EthicsAgentOutput(BaseModel):
    dimensions: list[EthicsDimension]
    overall_score: float = Field(ge=0.0, le=1.0, default=0.0)
    sovereignty_concerns: list[str] = Field(default_factory=list)
    reasoning: str = ""


class TechnicalAgentOutput(BaseModel):
    findings: list[TechnicalFinding]
    architecture_compliant: bool = False
    technical_debt: list[str] = Field(default_factory=list)
    reasoning: str = ""


# ── Agent Communication ───────────────────────────────────────────────────────


class AgentMessage(BaseModel):
    """A typed message passed between agents."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: AgentRole
    receiver: AgentRole | None = None  # None = broadcast
    type: MessageType
    topic: str
    content: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    in_reply_to: str | None = None


class DebatePosition(BaseModel):
    """An agent's position in a debate round."""

    agent: AgentRole
    claim: str
    evidence: list[str]
    confidence: float
    concedes: bool = False


# ── Final Governance Report ───────────────────────────────────────────────────


class RequiredAction(BaseModel):
    """A required remediation action."""

    priority: int
    title: str
    description: str
    category: str  # technical | process | documentation | legal
    timeline: str = "before deployment"


class GovernanceReport(BaseModel):
    """The final governance assessment output."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    proposal_id: str
    proposal_title: str

    # Decision
    decision: DecisionType
    overall_risk: RiskLevel
    compliance_confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: EvidenceStrength  # reusing scale: STRONG=low uncertainty

    # Agent outputs
    policy_output: PolicyAgentOutput | None = None
    compliance_output: ComplianceAgentOutput | None = None
    risk_output: RiskAgentOutput | None = None
    ethics_output: EthicsAgentOutput | None = None
    technical_output: TechnicalAgentOutput | None = None

    # Summary
    key_issues: list[str] = Field(default_factory=list)
    required_actions: list[RequiredAction] = Field(default_factory=list)
    evidence_citations: list[str] = Field(default_factory=list)
    governance_reasoning: str = ""

    # Debate outcomes
    debate_rounds: list[dict[str, Any]] = Field(default_factory=list)
    agent_disagreements: list[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_seconds: float = 0.0
    total_tokens_used: int = 0
    agent_messages: list[AgentMessage] = Field(default_factory=list)

    @property
    def is_abstained(self) -> bool:
        return self.decision == DecisionType.ABSTAINED


# ── Pipeline Context ──────────────────────────────────────────────────────────


class AgentContext(BaseModel):
    """Shared context passed through the entire agent pipeline."""

    proposal: Proposal
    retrieved_requirements: list[PolicyRequirement] = Field(default_factory=list)
    policy_output: PolicyAgentOutput | None = None
    risk_output: RiskAgentOutput | None = None
    technical_output: TechnicalAgentOutput | None = None
    compliance_output: ComplianceAgentOutput | None = None
    ethics_output: EthicsAgentOutput | None = None
    messages: list[AgentMessage] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── API Schemas ───────────────────────────────────────────────────────────────


class AssessmentRequest(BaseModel):
    """Request to assess an AI system proposal."""

    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=20)
    organization: str | None = None
    sector: str | None = None
    deployment_context: str | None = None
    technical_details: str | None = None


class AssessmentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AssessmentRecord(BaseModel):
    """A stored assessment record."""

    id: str
    proposal: Proposal
    status: AssessmentStatus = AssessmentStatus.PENDING
    report: GovernanceReport | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


class SSEEvent(BaseModel):
    """A server-sent event for streaming updates."""

    event: str  # agent_start | agent_complete | debate_start | done | error
    agent: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
