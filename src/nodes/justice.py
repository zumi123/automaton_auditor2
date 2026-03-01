"""Chief Justice - Synthesis engine with hardcoded conflict resolution rules."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.state import AuditReport, CriterionResult, JudicialOpinion


def _load_rubric() -> Dict[str, Any]:
    with open(Path(__file__).resolve().parents[2] / "rubric.json") as f:
        return json.load(f)


def _get_opinions_by_criterion(opinions: List[JudicialOpinion]) -> Dict[str, List[JudicialOpinion]]:
    by_crit: Dict[str, List[JudicialOpinion]] = {}
    for o in opinions:
        if hasattr(o, "criterion_id"):
            cid = o.criterion_id
        elif isinstance(o, dict):
            cid = o.get("criterion_id", "unknown")
        else:
            continue
        by_crit.setdefault(cid, []).append(o)
    return by_crit


def _get_judge_opinion(opinions: List[JudicialOpinion], judge: str) -> Optional[JudicialOpinion]:
    for o in opinions:
        j = getattr(o, "judge", None) or (o.get("judge") if isinstance(o, dict) else None)
        if j == judge:
            return o
    return None


def _resolve_score(
    opinions: List[JudicialOpinion],
    evidences: Dict[str, List],
    synthesis_rules: Dict[str, str],
    dimension_id: str,
) -> tuple[int, str, Optional[str]]:
    """
    Hardcoded deterministic conflict resolution.
    Returns (final_score, remediation, dissent_summary).
    """
    prosecutor = _get_judge_opinion(opinions, "Prosecutor")
    defense = _get_judge_opinion(opinions, "Defense")
    tech_lead = _get_judge_opinion(opinions, "TechLead")

    def score(o: Optional[JudicialOpinion]) -> int:
        if o is None:
            return 3
        return getattr(o, "score", None) or (o.get("score") if isinstance(o, dict) else 3)

    p_score = score(prosecutor)
    d_score = score(defense)
    t_score = score(tech_lead)

    # Rule of Security: Prosecutor-identified security flaw caps at 3
    if prosecutor and p_score <= 2:
        proc_arg = getattr(prosecutor, "argument", "") or ""
        if any(kw in proc_arg.lower() for kw in ["os.system", "security", "injection", "unsanitized", "sandbox"]):
            final = min(3, t_score)
            dissent = "Prosecutor identified security concerns; score capped per Rule of Security."
            remediation = "Address security: use subprocess with sanitized inputs, tempfile for cloning."
            return (final, remediation, dissent)

    # Rule of Evidence: Defense overruled if evidence contradicts
    if defense and d_score >= 4:
        def_arg = getattr(defense, "argument", "") or ""
        if "metacognition" in def_arg.lower() or "deep" in def_arg.lower():
            # Check if evidence supports it
            ev_list = list(evidences.get("theoretical_depth") or []) + list(evidences.get("repo_general") or [])
            has_support = any(
                getattr(e, "found", False) if not isinstance(e, dict) else e.get("found", False)
                for e in (ev_list or [])
            )
            if not ev_list or not has_support:
                final = t_score
                dissent = "Defense argued for depth but Detective evidence did not support; overruled per Rule of Evidence."
                remediation = "Add concrete evidence in report (file paths, code snippets) to support claims."
                return (final, remediation, dissent)

    # Rule of Functionality: Tech Lead carries highest weight for architecture
    if dimension_id in ("graph_orchestration", "state_management_rigor", "chief_justice_synthesis"):
        if tech_lead and t_score >= 4:
            final = t_score
            dissent = None if abs(p_score - d_score) <= 2 else f"Prosecutor: {p_score}, Defense: {d_score}; Tech Lead verdict adopted."
            remediation = getattr(tech_lead, "argument", "")[:300] if tech_lead else ""
            return (final, remediation or "See Tech Lead advice.", dissent)

    # Variance > 2: re-evaluate
    if max(p_score, d_score, t_score) - min(p_score, d_score, t_score) > 2:
        # Prefer Tech Lead as tie-breaker
        final = t_score
        dissent = f"Score variance: Prosecutor={p_score}, Defense={d_score}, Tech Lead={t_score}. Tech Lead adopted per variance rule."
        remediation = getattr(tech_lead, "argument", "")[:300] if tech_lead else "Address gaps between judge opinions."
        return (final, remediation, dissent)

    # Default: median-ish, prefer Tech Lead
    final = t_score
    dissent = None
    remediation = getattr(tech_lead, "argument", "")[:300] if tech_lead else "Review judge opinions."
    return (final, remediation, dissent)


def ChiefJusticeNode(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synthesis engine. Applies hardcoded rules to produce AuditReport.
    Output is a structured Markdown-serializable report.
    """
    print("  ChiefJustice: synthesizing report...", flush=True)
    rubric = _load_rubric()
    synthesis_rules = rubric.get("synthesis_rules", {})
    dimensions = {d["id"]: d for d in rubric.get("dimensions", [])}

    opinions = state.get("opinions") or []
    evidences = state.get("evidences") or {}
    repo_url = state.get("repo_url", "unknown")

    by_crit = _get_opinions_by_criterion(opinions)

    criteria_results: List[CriterionResult] = []
    for dim_id, dim in dimensions.items():
        crit_opinions = by_crit.get(dim_id, [])
        final_score, remediation, dissent_summary = _resolve_score(
            crit_opinions, evidences, synthesis_rules, dim_id
        )
        criteria_results.append(
            CriterionResult(
                dimension_id=dim_id,
                dimension_name=dim.get("name", dim_id),
                final_score=final_score,
                judge_opinions=crit_opinions,
                dissent_summary=dissent_summary,
                remediation=remediation,
            )
        )

    overall = sum(c.final_score for c in criteria_results) / max(len(criteria_results), 1)
    exec_summary = (
        f"Audit of {repo_url}. Overall score: {overall:.1f}/5. "
        f"Criteria assessed: {len(criteria_results)}. "
        "See criterion breakdown and remediation plan below."
    )
    remediation_plan = "\n\n".join(
        f"**{c.dimension_name}:** {c.remediation}" for c in criteria_results
    )

    report = AuditReport(
        repo_url=repo_url,
        executive_summary=exec_summary,
        overall_score=round(overall, 1),
        criteria=criteria_results,
        remediation_plan=remediation_plan,
    )

    return {"final_report": report}


def report_to_markdown(report: AuditReport) -> str:
    """Serialize AuditReport to Markdown file format."""
    lines = [
        "# Automaton Auditor Report",
        "",
        f"**Repository:** {report.repo_url}",
        "",
        "## Executive Summary",
        "",
        report.executive_summary,
        "",
        f"**Overall Score:** {report.overall_score}/5",
        "",
        "## Criterion Breakdown",
        "",
    ]
    for c in report.criteria:
        lines.append(f"### {c.dimension_name} ({c.dimension_id})")
        lines.append(f"**Final Score:** {c.final_score}/5")
        if c.dissent_summary:
            lines.append(f"*Dissent:* {c.dissent_summary}")
        lines.append("")
        for o in c.judge_opinions:
            j = getattr(o, "judge", "?")
            s = getattr(o, "score", "?")
            a = getattr(o, "argument", "")[:200]
            lines.append(f"- **{j}** (score {s}): {a}")
        lines.append("")
        lines.append(f"**Remediation:** {c.remediation}")
        lines.append("")

    lines.extend([
        "## Remediation Plan",
        "",
        report.remediation_plan,
    ])
    return "\n".join(lines)
