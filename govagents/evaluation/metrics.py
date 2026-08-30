"""Evaluation metrics for GovAgents assessments."""

from __future__ import annotations

from govagents.core.models import GovernanceReport, RiskLevel, ComplianceStatus, DecisionType


def compute_confidence_score(report: GovernanceReport) -> float:
    """Compute an aggregate confidence score from agent outputs."""
    scores = []

    if report.compliance_output:
        assessments = report.compliance_output.requirement_assessments
        if assessments:
            avg_conf = sum(a.confidence for a in assessments) / len(assessments)
            scores.append(avg_conf)

    if report.risk_output:
        # Risk confidence: inverse of risk score
        scores.append(1.0 - report.risk_output.risk_score)

    if report.ethics_output:
        scores.append(report.ethics_output.overall_score)

    return sum(scores) / len(scores) if scores else 0.0


def summarize_report(report: GovernanceReport) -> dict:
    """Produce a flat summary dict of a governance report for evaluation."""
    return {
        "proposal_title": report.proposal_title,
        "decision": report.decision.value,
        "overall_risk": report.overall_risk.value,
        "compliance_confidence": round(report.compliance_confidence, 3),
        "uncertainty": report.uncertainty.value,
        "key_issues_count": len(report.key_issues),
        "required_actions_count": len(report.required_actions),
        "evidence_citations_count": len(report.evidence_citations),
        "requirements_assessed": len(
            report.compliance_output.requirement_assessments
        ) if report.compliance_output else 0,
        "risks_identified": len(report.risk_output.risks) if report.risk_output else 0,
        "ethics_dimensions": len(
            report.ethics_output.dimensions
        ) if report.ethics_output else 0,
        "technical_findings": len(
            report.technical_output.findings
        ) if report.technical_output else 0,
        "debate_rounds": len(report.debate_rounds),
        "tokens_used": report.total_tokens_used,
        "processing_time_s": round(report.processing_time_seconds, 2),
    }
