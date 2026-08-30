"""Demo script — run a full governance assessment from the command line."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DEMO_PROPOSAL = {
    "title": "Employee Productivity Monitoring AI",
    "description": (
        "A company wants to deploy an AI system that analyzes all employee "
        "communications (Slack messages, emails) to automatically compute daily "
        "productivity scores and flag underperforming employees to HR managers. "
        "The system uses NLP to detect sentiment, topic frequency, and response "
        "times to compute a composite productivity metric that feeds directly into "
        "performance reviews."
    ),
    "organization": "Acme Corp",
    "sector": "enterprise",
    "deployment_context": (
        "Internal HR system deployed to 2,000 employees across EU offices in "
        "Germany, France, and Netherlands."
    ),
    "technical_details": (
        "BERT-based NLP model fine-tuned on communication metadata. Daily batch "
        "processing pipeline. Scores stored in HR database accessible to managers. "
        "No explainability layer currently implemented."
    ),
}


async def main() -> None:
    from govagents.core.config import get_settings
    from govagents.core.logging import configure_logging
    from govagents.core.models import Proposal
    from govagents.orchestration.coordinator import Coordinator
    from govagents.policies.ingestion import ingest_policies

    settings = get_settings()
    configure_logging(level="INFO", format="console")

    print("GovAgents — Governance Assessment Demo")
    print("=" * 60)
    print(f"Proposal: {DEMO_PROPOSAL['title']}")
    print()

    # Ingest policies
    print("📚 Loading policy corpus...")
    await ingest_policies()

    # Build proposal
    proposal = Proposal(**DEMO_PROPOSAL)

    # Run assessment
    print("🏃 Running multi-agent assessment pipeline...")
    print()

    coordinator = Coordinator()
    report = await coordinator.assess(proposal)

    # Print report
    print()
    print("=" * 60)
    print("GOVERNANCE ASSESSMENT REPORT")
    print("=" * 60)
    print(f"\nProposal:  {report.proposal_title}")
    print(f"Decision:  {report.decision.value}")
    print(f"Risk:      {report.overall_risk.value}")
    print(f"Confidence:{report.compliance_confidence:.0%}")
    print(f"Tokens:    {report.total_tokens_used:,}")
    print(f"Time:      {report.processing_time_seconds:.1f}s")

    print("\n─── KEY ISSUES ─────────────────────────────────────────")
    for i, issue in enumerate(report.key_issues, 1):
        print(f"  {i}. {issue}")

    print("\n─── REQUIRED ACTIONS ────────────────────────────────────")
    for action in report.required_actions:
        print(f"  [P{action.priority}] {action.title}")
        print(f"       {action.description[:100]}...")

    print("\n─── EVIDENCE CITATIONS ──────────────────────────────────")
    for citation in report.evidence_citations:
        print(f"  • {citation}")

    if report.agent_disagreements:
        print("\n─── AGENT DISAGREEMENTS ─────────────────────────────────")
        for d in report.agent_disagreements:
            print(f"  ⚡ {d}")

    print("\n─── GOVERNANCE REASONING ─────────────────────────────────")
    print(f"  {report.governance_reasoning[:400]}...")
    print()


if __name__ == "__main__":
    asyncio.run(main())
