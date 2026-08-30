"""Tests for core data models."""

import pytest
from govagents.core.models import (
    ComplianceStatus,
    DecisionType,
    EvidenceStrength,
    GovernanceReport,
    PolicyRequirement,
    Proposal,
    RiskItem,
    RiskLevel,
)


def test_proposal_creation():
    p = Proposal(
        title="Test AI System",
        description="A test description long enough to pass validation.",
    )
    assert p.id is not None
    assert p.title == "Test AI System"


def test_risk_item_severity():
    risk = RiskItem(
        title="High Risk",
        description="A high-severity risk.",
        category="technical",
        likelihood=0.9,
        impact=0.9,
        severity=RiskLevel.CRITICAL,
    )
    assert risk.severity == RiskLevel.CRITICAL
    assert risk.likelihood * risk.impact == pytest.approx(0.81)


def test_compliance_status_enum():
    assert ComplianceStatus.SATISFIED.value == "SATISFIED"
    assert ComplianceStatus.NOT_SATISFIED != ComplianceStatus.SATISFIED


def test_policy_requirement():
    req = PolicyRequirement(
        id="test-001",
        source_id="gdpr",
        source_name="GDPR",
        title="Test Requirement",
        text="The system shall...",
        requirement_type="transparency",
        relevance_score=0.85,
    )
    assert req.id == "test-001"
    assert req.relevance_score == pytest.approx(0.85)


def test_governance_report_abstained():
    report = GovernanceReport(
        proposal_id="test",
        proposal_title="Test",
        decision=DecisionType.ABSTAINED,
        overall_risk=RiskLevel.HIGH,
        compliance_confidence=0.3,
        uncertainty=EvidenceStrength.WEAK,
    )
    assert report.is_abstained is True
