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
    PRIVACY = "privacy"
    SECURITY = "security"
    BIAS = "bias"
    GUARDRAIL = "guardrail"
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


class PolicyConfig(BaseModel):
    enabled: bool = True
    max_requirements: int = 20

class ComplianceConfig(BaseModel):
    enabled: bool = True
    strictness: str = "normal"  # lenient, normal, strict

class RiskConfig(BaseModel):
    enabled: bool = True
    risk_tolerance: str = "medium"  # low, medium, high

class EthicsConfig(BaseModel):
    enabled: bool = True
    focus_areas: list[str] = Field(default_factory=list)

class TechnicalConfig(BaseModel):
    enabled: bool = True
    deep_scan: bool = False

class PrivacyConfig(BaseModel):
    enabled: bool = True
    strict_gdpr: bool = True

class SecurityConfig(BaseModel):
    enabled: bool = True
    threat_model: str = "standard"

class BiasConfig(BaseModel):
    enabled: bool = True
    fairness_metric: str = "demographic_parity"

class GuardrailConfig(BaseModel):
    enabled: bool = True
    strictness: str = "absolute"

class PipelineConfig(BaseModel):
    """Configuration for which pipeline paths to execute and their parameters."""
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    compliance: ComplianceConfig = Field(default_factory=ComplianceConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    ethics: EthicsConfig = Field(default_factory=EthicsConfig)
    technical: TechnicalConfig = Field(default_factory=TechnicalConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    bias: BiasConfig = Field(default_factory=BiasConfig)
    guardrail: GuardrailConfig = Field(default_factory=GuardrailConfig)


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
    pipeline_config: PipelineConfig = Field(default_factory=PipelineConfig)


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
    title: str
    severity: RiskLevel
    description: str
    implication: str
    recommendation: str

class PrivacyFinding(BaseModel):
    data_type: str
    issue: str
    severity: RiskLevel
    gdpr_article: str | None = None

class SecurityVulnerability(BaseModel):
    component: str
    vulnerability: str
    severity: RiskLevel
    cvss_estimate: float | None = None

class BiasFinding(BaseModel):
    affected_group: str
    bias_type: str
    severity: RiskLevel
    description: str
    implication: str
    recommendation: str


# ── Agent Output Models ───────────────────────────────────────────────────────

class ResearchReport(BaseModel):
    query: str
    findings: list[str]
    certainty_score: float = Field(ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)


class MiniAgentTask(BaseModel):
    """A single, narrow assignment handed to one mini-agent within a module's swarm.

    Every governance module (Policy, Compliance, Risk, Ethics, ...) decomposes its
    section of the assessment into several of these — one mini-agent per task — and
    runs them concurrently, the same way a team lead would dispatch several analysts
    to each dig into one specific angle before reporting back.
    """

    id: str
    focus: str
    instruction: str
    use_web_search: bool = True


class MiniAgentFinding(BaseModel):
    """The structured brief a mini-agent reports back to its parent module."""

    task_id: str = ""
    focus: str = ""
    summary: str = ""
    findings: list[str] = Field(default_factory=list)
    certainty_score: float = Field(ge=0.0, le=1.0, default=0.0)
    concern_level: RiskLevel = RiskLevel.LOW
    sources: list[str] = Field(default_factory=list)
    recommendation: str = ""

    # Recursive micro-agent spawning: a mini-agent that surfaces something
    # concerning but under-investigated can request ONE narrower follow-up
    # agent rather than guessing. Depth is capped by the swarm, not here.
    needs_followup: bool = False
    followup_question: str = ""
    depth: int = 0

    def as_research_report(self) -> "ResearchReport":
        """Adapt this finding into the legacy ResearchReport shape used by the UI."""
        return ResearchReport(
            query=f"[{self.focus}] {self.summary}" if self.summary else self.focus,
            findings=self.findings,
            certainty_score=self.certainty_score,
            sources=self.sources,
        )

class PolicyAgentOutput(BaseModel):
    requirements: list[PolicyRequirement]
    search_queries: list[str] = Field(default_factory=list)
    total_policies_searched: int = 0
    reasoning: str = ""
    research: list[ResearchReport] = Field(default_factory=list)


class ComplianceAgentOutput(BaseModel):
    requirement_assessments: list[RequirementAssessment]
    overall_compliance_score: float = Field(ge=0.0, le=1.0, default=0.0)
    overall_status: ComplianceStatus = ComplianceStatus.UNKNOWN
    reasoning: str = ""
    research: list[ResearchReport] = Field(default_factory=list)


class RiskAgentOutput(BaseModel):
    risks: list[RiskItem]
    overall_risk_level: RiskLevel = RiskLevel.MEDIUM
    risk_score: float = Field(ge=0.0, le=1.0, default=0.5)
    reasoning: str = ""
    research: list[ResearchReport] = Field(default_factory=list)


class EthicsAgentOutput(BaseModel):
    dimensions: list[EthicsDimension]
    overall_score: float = Field(ge=0.0, le=1.0, default=0.0)
    sovereignty_concerns: list[str] = Field(default_factory=list)
    reasoning: str = ""
    research: list[ResearchReport] = Field(default_factory=list)


class TechnicalAgentOutput(BaseModel):
    findings: list[TechnicalFinding]
    architecture_compliant: bool = False
    technical_debt: list[str] = Field(default_factory=list)
    reasoning: str = ""
    research: list[ResearchReport] = Field(default_factory=list)

class PrivacyAgentOutput(BaseModel):
    findings: list[PrivacyFinding]
    pii_handled: bool = False
    data_minimization_score: float = Field(ge=0.0, le=1.0, default=0.5)
    reasoning: str = ""
    research: list[ResearchReport] = Field(default_factory=list)

class SecurityAgentOutput(BaseModel):
    vulnerabilities: list[SecurityVulnerability]
    overall_security_posture: str = "unknown"
    reasoning: str = ""
    research: list[ResearchReport] = Field(default_factory=list)

class BiasAgentOutput(BaseModel):
    findings: list[BiasFinding]
    fairness_score: float = Field(ge=0.0, le=1.0, default=0.5)
    reasoning: str = ""
    research: list[ResearchReport] = Field(default_factory=list)

class GuardrailAgentOutput(BaseModel):
    triggered: bool = False
    violations: list[str] = Field(default_factory=list)
    reasoning: str = ""
    research: list[ResearchReport] = Field(default_factory=list)


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


# ── Cross-Module Logical Gates ────────────────────────────────────────────────


class GateVerdict(str, Enum):
    """The action a cross-module logic gate demands once its condition fires."""

    VETO = "VETO"  # hard stop — forces a specific final decision, no override
    ESCALATE = "ESCALATE"  # forces a debate round / deeper reasoning pass
    FLAG = "FLAG"  # informational — surfaced to the Governance Agent, not binding
    CLEAR = "CLEAR"  # gate evaluated, condition did not fire


class GateFinding(BaseModel):
    """The result of evaluating one cross-module logical gate against the full
    body of module outputs and mini-agent evidence. Gates are how modules are
    forced to reason about *each other*, not just their own narrow slice."""

    gate_id: str
    description: str
    verdict: GateVerdict
    severity: RiskLevel = RiskLevel.MEDIUM
    involved_agents: list[AgentRole] = Field(default_factory=list)
    rationale: str = ""


# ── Shared Knowledge Pool ─────────────────────────────────────────────────────


class KnowledgeScope(str, Enum):
    """Who is allowed to read a knowledge pool entry."""

    MODULE_PRIVATE = "module_private"  # only the module (and its own mini-agents) that wrote it
    SHARED = "shared"  # any module or mini-agent across the whole pipeline
    GOVERNANCE_ONLY = "governance_only"  # only the final Governance Agent synthesis


class KnowledgeEntry(BaseModel):
    """One deposit into the shared knowledge pool.

    Mini-agents, micro-agents, and modules all deposit what they learn here.
    Reads are never a blind dump of the whole pool — `query_knowledge` scores
    entries by scope + tag/topic relevance to the reader before returning
    anything, so access is deliberately attention-filtered rather than open.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_agent: AgentRole
    source_kind: str = "module"  # "module" | "mini_agent" | "micro_agent"
    topic: str = ""
    tags: list[str] = Field(default_factory=list)
    content: str
    certainty_score: float = Field(ge=0.0, le=1.0, default=0.5)
    scope: KnowledgeScope = KnowledgeScope.SHARED
    created_at: datetime = Field(default_factory=datetime.utcnow)


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
    privacy_output: PrivacyAgentOutput | None = None
    security_output: SecurityAgentOutput | None = None
    bias_output: BiasAgentOutput | None = None
    guardrail_output: GuardrailAgentOutput | None = None

    # Summary
    key_issues: list[str] = Field(default_factory=list)
    required_actions: list[RequiredAction] = Field(default_factory=list)
    evidence_citations: list[str] = Field(default_factory=list)
    governance_reasoning: str = ""

    # Debate outcomes
    debate_rounds: list[dict[str, Any]] = Field(default_factory=list)
    agent_disagreements: list[str] = Field(default_factory=list)

    # Cross-module logic gates
    gate_findings: list[GateFinding] = Field(default_factory=list)
    guardrail_veto: bool = False

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
    privacy_output: PrivacyAgentOutput | None = None
    security_output: SecurityAgentOutput | None = None
    bias_output: BiasAgentOutput | None = None
    guardrail_output: GuardrailAgentOutput | None = None
    messages: list[AgentMessage] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Mini-agent swarms: role.value -> the findings its parallel specialist team produced
    mini_agent_findings: dict[str, list[MiniAgentFinding]] = Field(default_factory=dict)
    # Cross-module logic gate results, populated after the DAG phase completes
    gate_findings: list[GateFinding] = Field(default_factory=list)
    # Shared knowledge pool: every mini-agent, micro-agent, and module deposits what it
    # learns here; reads go through attention-filtered access control, never a raw dump.
    knowledge_pool: list[KnowledgeEntry] = Field(default_factory=list)


# ── API Schemas ───────────────────────────────────────────────────────────────


class AssessmentRequest(BaseModel):
    """Request to assess an AI system proposal."""

    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=20)
    organization: str | None = None
    sector: str | None = None
    deployment_context: str | None = None
    technical_details: str | None = None
    pipeline_config: PipelineConfig = Field(default_factory=PipelineConfig)


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
