"""Cross-module logical gates.

Individual modules (Policy, Compliance, Risk, Ethics, Technical, Privacy,
Security, Bias, Guardrail) each judge their own slice of the proposal. Left
alone, nothing forces them to reason about each other — a module can reach a
locally-sound conclusion that is globally incoherent (e.g. Compliance says
"satisfied" while Technical found CRITICAL gaps in the very mechanism that
requirement depends on). The `LogicGateEngine` runs a set of declarative
gates over the whole context once every module has reported, each one
either:

- VETO      — hard override, forces a specific outcome, not up for debate
- ESCALATE  — forces a debate round between the disagreeing modules
- FLAG      — surfaced to the Governance Agent as something to weigh
- CLEAR     — condition did not fire

This is what makes the modules "in relation with each other in a logical
way": every gate is an explicit AND/OR condition spanning two or more
modules' structured outputs (not free-text vibes), so contradictions are
caught mechanically before the LLM ever gets to paper over them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from govagents.core.logging import get_logger
from govagents.core.models import (
    AgentContext,
    AgentRole,
    ComplianceStatus,
    GateFinding,
    GateVerdict,
    RiskLevel,
)

log = get_logger(__name__)

_RISK_RANK = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}


@dataclass
class GateRule:
    id: str
    description: str
    condition: Callable[[AgentContext], bool]
    verdict: GateVerdict
    severity: RiskLevel
    involved_agents: list[AgentRole]
    rationale: Callable[[AgentContext], str]


class LogicGateEngine:
    """Evaluates every registered gate against the shared context and returns findings."""

    def __init__(self) -> None:
        self.rules: list[GateRule] = [
            self._guardrail_veto(),
            self._risk_vs_compliance(),
            self._compliance_vs_technical(),
            self._ethics_vs_compliance(),
            self._security_vs_technical(),
            self._privacy_vs_compliance(),
            self._bias_vs_ethics(),
            self._evidence_sufficiency(),
        ]

    def evaluate(self, context: AgentContext) -> list[GateFinding]:
        findings: list[GateFinding] = []
        for rule in self.rules:
            try:
                fired = rule.condition(context)
            except Exception as e:  # a gate must never crash the pipeline
                log.error("gate_evaluation_error", gate=rule.id, error=str(e))
                continue
            if not fired:
                continue
            finding = GateFinding(
                gate_id=rule.id,
                description=rule.description,
                verdict=rule.verdict,
                severity=rule.severity,
                involved_agents=rule.involved_agents,
                rationale=rule.rationale(context),
            )
            findings.append(finding)
            log.info(
                "gate_triggered",
                gate=rule.id,
                verdict=rule.verdict.value,
                severity=rule.severity.value,
            )

        # Correlated-concern gate needs the full picture of what already fired,
        # so it runs last and is appended separately rather than as a GateRule.
        correlated = self._correlated_concern_escalation(context)
        if correlated:
            findings.append(correlated)

        return findings

    # ── Individual gates ────────────────────────────────────────────────

    def _guardrail_veto(self) -> GateRule:
        return GateRule(
            id="guardrail_veto",
            description="An absolute governance red line was triggered.",
            condition=lambda c: bool(c.guardrail_output and c.guardrail_output.triggered),
            verdict=GateVerdict.VETO,
            severity=RiskLevel.CRITICAL,
            involved_agents=[AgentRole.GUARDRAIL, AgentRole.GOVERNANCE],
            rationale=lambda c: (
                "Guardrail Agent flagged red-line violation(s): "
                + "; ".join(c.guardrail_output.violations[:5])
                if c.guardrail_output and c.guardrail_output.violations
                else "Guardrail Agent triggered without itemized violations."
            ),
        )

    def _risk_vs_compliance(self) -> GateRule:
        return GateRule(
            id="risk_vs_compliance",
            description="Risk assessed CRITICAL while Compliance assessed full satisfaction — contradictory.",
            condition=lambda c: bool(
                c.risk_output
                and c.compliance_output
                and c.risk_output.overall_risk_level == RiskLevel.CRITICAL
                and c.compliance_output.overall_status == ComplianceStatus.SATISFIED
            ),
            verdict=GateVerdict.ESCALATE,
            severity=RiskLevel.CRITICAL,
            involved_agents=[AgentRole.RISK, AgentRole.COMPLIANCE],
            rationale=lambda c: (
                f"Risk Agent: {c.risk_output.overall_risk_level.value} "
                f"(score {c.risk_output.risk_score:.2f}) vs. Compliance Agent: SATISFIED "
                f"(score {c.compliance_output.overall_compliance_score:.2f})."
            ),
        )

    def _compliance_vs_technical(self) -> GateRule:
        def fired(c: AgentContext) -> bool:
            if not (c.compliance_output and c.technical_output):
                return False
            critical = [f for f in c.technical_output.findings if f.severity == RiskLevel.CRITICAL]
            return c.compliance_output.overall_compliance_score > 0.7 and len(critical) > 0

        return GateRule(
            id="compliance_vs_technical",
            description="High compliance score despite CRITICAL technical findings.",
            condition=fired,
            verdict=GateVerdict.ESCALATE,
            severity=RiskLevel.HIGH,
            involved_agents=[AgentRole.COMPLIANCE, AgentRole.TECHNICAL],
            rationale=lambda c: (
                f"Compliance score {c.compliance_output.overall_compliance_score:.2f} but "
                f"{sum(1 for f in c.technical_output.findings if f.severity == RiskLevel.CRITICAL)} "
                "CRITICAL technical finding(s) exist that the compliance requirements depend on."
            ),
        )

    def _ethics_vs_compliance(self) -> GateRule:
        return GateRule(
            id="ethics_vs_compliance",
            description="Ethics scored poorly while Compliance scored well — ethical weight may be under-counted.",
            condition=lambda c: bool(
                c.ethics_output
                and c.compliance_output
                and c.ethics_output.overall_score < 0.4
                and c.compliance_output.overall_compliance_score > 0.65
            ),
            verdict=GateVerdict.ESCALATE,
            severity=RiskLevel.MEDIUM,
            involved_agents=[AgentRole.ETHICS, AgentRole.COMPLIANCE],
            rationale=lambda c: (
                f"Ethics score {c.ethics_output.overall_score:.2f} vs. Compliance score "
                f"{c.compliance_output.overall_compliance_score:.2f}."
            ),
        )

    def _security_vs_technical(self) -> GateRule:
        def fired(c: AgentContext) -> bool:
            if not (c.security_output and c.technical_output):
                return False
            critical_vulns = [v for v in c.security_output.vulnerabilities if v.severity == RiskLevel.CRITICAL]
            return bool(critical_vulns) and c.technical_output.architecture_compliant

        return GateRule(
            id="security_vs_technical",
            description="Technical Agent called the architecture compliant despite CRITICAL security vulnerabilities.",
            condition=fired,
            verdict=GateVerdict.ESCALATE,
            severity=RiskLevel.HIGH,
            involved_agents=[AgentRole.SECURITY, AgentRole.TECHNICAL],
            rationale=lambda c: (
                f"{sum(1 for v in c.security_output.vulnerabilities if v.severity == RiskLevel.CRITICAL)} "
                "CRITICAL security vulnerabilit(y/ies) found, but Technical Agent marked the architecture compliant."
            ),
        )

    def _privacy_vs_compliance(self) -> GateRule:
        def fired(c: AgentContext) -> bool:
            if not (c.privacy_output and c.compliance_output):
                return False
            high_privacy = [f for f in c.privacy_output.findings if f.severity in (RiskLevel.HIGH, RiskLevel.CRITICAL)]
            return bool(high_privacy) and c.compliance_output.overall_status == ComplianceStatus.SATISFIED

        return GateRule(
            id="privacy_vs_compliance",
            description="Compliance assessed SATISFIED despite HIGH/CRITICAL privacy findings.",
            condition=fired,
            verdict=GateVerdict.ESCALATE,
            severity=RiskLevel.HIGH,
            involved_agents=[AgentRole.PRIVACY, AgentRole.COMPLIANCE],
            rationale=lambda c: (
                f"{sum(1 for f in c.privacy_output.findings if f.severity in (RiskLevel.HIGH, RiskLevel.CRITICAL))} "
                "HIGH/CRITICAL privacy finding(s), but Compliance Agent assessed SATISFIED."
            ),
        )

    def _bias_vs_ethics(self) -> GateRule:
        def fired(c: AgentContext) -> bool:
            if not (c.bias_output and c.ethics_output):
                return False
            fairness_dim = next((d for d in c.ethics_output.dimensions if d.dimension == "fairness"), None)
            if not fairness_dim:
                return False
            return c.bias_output.fairness_score < 0.4 and fairness_dim.score > 0.65

        return GateRule(
            id="bias_vs_ethics",
            description="Bias Agent found low fairness while Ethics Agent's fairness dimension scored well.",
            condition=fired,
            verdict=GateVerdict.FLAG,
            severity=RiskLevel.MEDIUM,
            involved_agents=[AgentRole.BIAS, AgentRole.ETHICS],
            rationale=lambda c: (
                f"Bias Agent fairness_score={c.bias_output.fairness_score:.2f} vs. Ethics Agent "
                "fairness dimension score — the two specialist views on fairness disagree."
            ),
        )

    def _evidence_sufficiency(self) -> GateRule:
        """AND-gate: every module's own specialist team must show reasonable aggregate
        certainty before we let the pipeline proceed to a clean approval path."""

        def fired(c: AgentContext) -> bool:
            from govagents.core.config import get_settings

            all_findings = [f for team in c.mini_agent_findings.values() for f in team]
            if not all_findings:
                return False
            avg_certainty = sum(f.certainty_score for f in all_findings) / len(all_findings)
            return avg_certainty < get_settings().evidence_sufficiency_threshold

        def rationale(c: AgentContext) -> str:
            all_findings = [f for team in c.mini_agent_findings.values() for f in team]
            avg_certainty = sum(f.certainty_score for f in all_findings) / max(len(all_findings), 1)
            return (
                f"Average certainty across {len(all_findings)} mini-agent findings from "
                f"{len(c.mini_agent_findings)} module(s) was only {avg_certainty:.2f} — evidence is too thin "
                "for a confident clean approval; uncertainty should be reflected in the final decision."
            )

        return GateRule(
            id="evidence_sufficiency",
            description="Aggregate specialist-team certainty is below the sufficiency threshold.",
            condition=fired,
            verdict=GateVerdict.FLAG,
            severity=RiskLevel.MEDIUM,
            involved_agents=[AgentRole.GOVERNANCE],
            rationale=rationale,
        )

    def _correlated_concern_escalation(self, context: AgentContext) -> GateFinding | None:
        """OR-of-ANDs style gate: if several *independent* modules each raise a
        high-concern mini-agent finding whose focus/tags cluster around the same
        theme (e.g. "human oversight" surfacing from Risk, Ethics, and Technical
        independently), that convergence is stronger signal than any one module's
        opinion and is escalated even if no single pairwise gate above fired."""

        from govagents.core.config import get_settings

        theme_to_modules: dict[str, set[str]] = {}
        for module, findings in context.mini_agent_findings.items():
            for f in findings:
                if f.concern_level not in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                    continue
                theme = f.focus.split(".")[0]
                theme_to_modules.setdefault(theme, set()).add(module)

        min_modules = get_settings().correlated_concern_min_modules
        converged = {theme: mods for theme, mods in theme_to_modules.items() if len(mods) >= min_modules}
        if not converged:
            return None

        top_theme, top_modules = max(converged.items(), key=lambda kv: len(kv[1]))
        return GateFinding(
            gate_id="correlated_concern_convergence",
            description=(
                f"{len(top_modules)} independent modules each raised HIGH/CRITICAL concern "
                f"clustered around '{top_theme}'."
            ),
            verdict=GateVerdict.ESCALATE,
            severity=RiskLevel.HIGH,
            involved_agents=[AgentRole(m) for m in top_modules if m in AgentRole._value2member_map_],
            rationale=(
                f"Modules {sorted(top_modules)} independently flagged high concern on '{top_theme}' "
                "through their mini-agent teams. Independent convergence is stronger evidence than any "
                "single module's assessment and should weigh heavily on the final decision."
            ),
        )
