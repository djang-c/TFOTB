"""T10 action cards, built from recorded facts only (docs/implementation/07, sections 1-3).

Pattern: facts (code) -> template (plain string formatting, no LLM) -> ActionCard, whose validator
checks that every footnote resolves to a cited claim, that a responsible human is named and that no
dosing / eligibility language is present. Nothing here invents an asset, a contact or a claim:
a card that needs one raises CardError instead.

Not built (P1): variant_evidence,
aso_checklist, repurposing_paths, phenopacket_example. Plain f-strings replace the spec's Jinja2
(an unreviewed package); the output is the same Markdown.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

from atlas.connections import REVIEWER_ROLE, QueryOutcome, RankedConnection
from atlas.graph import find_paths
from atlas.schemas import (
    ActionCard,
    AssetResult,
    Claim,
    ClaimStatus,
    GapResult,
    ReviewState,
    SourceType,
)

MAX_CONNECTIONS = 10  # the brief lists the top of the ranking, not everything
Label = Callable[[str], str]


class CardError(ValueError):
    """The facts a card needs are missing. Raised instead of filling the gap with invented content."""


def _card_id(*parts: str) -> str:
    return "CARD:" + hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]


def _name(label_of: Label, entity_id: str) -> str:
    label = label_of(entity_id)
    return f"{label} ({entity_id})" if label else entity_id


def _cite(claim_ids: list[str]) -> str:
    return " ".join(f"[^c:{i}]" for i in claim_ids)


def _claim_line(
    c: Claim, label_of: Label, claims: dict[str, Claim] | None = None, cited: list[str] | None = None
) -> str:
    """One claim as a readable line. Says where it came from: an AI reading of a named paper, or an AI
    hypothesis built from stored claims. Neither has been reviewed by a human unless the state says so."""
    state = f"{c.status.value.replace('_', ' ')}, {c.review_state.value}"
    hedge = " **hypothesis only**" if c.status is ClaimStatus.inference else ""
    origin = ""
    if c.source_type is SourceType.ai_generated:
        origin = "; **AI hypothesis, not a finding**"
        built = [i for i in c.derived_from if claims and i in claims]
        if built and cited is not None:
            cited.extend(built)
            origin += f"; built from {_cite(built)}"
    elif (c.extraction_method or "").startswith("llm:") and c.source_url.startswith("http"):
        origin = f"; found by AI in {c.source_url}"
    return (
        f"- {_name(label_of, c.subject_id)} `{c.predicate}` {_name(label_of, c.object_id)} "
        f"({state}{origin}){hedge} [^c:{c.claim_id}]"
    )


def evidence_brief(
    outcome: QueryOutcome,
    claims: dict[str, Claim],
    *,
    label_of: Label = lambda _id: "",
    audience: str = "science",
    now: datetime | None = None,
) -> ActionCard:
    """The 'evidence_brief': what is connected, how strong the evidence is, what is missing."""
    now = now or datetime.now(UTC)
    shown = outcome.ranked[:MAX_CONNECTIONS]
    cited: list[str] = []
    lines = [f"# Evidence brief: {_name(label_of, outcome.query_id)}", ""]
    lines.append(
        "Research support only. Not a diagnosis or a treatment recommendation. Every claim below is "
        "`unreviewed` unless it says otherwise; no expert has checked it."
    )
    lines.append("")
    if not shown:
        lines += ["No connected candidates were found by any channel in the indexed evidence.", ""]
    lines += _known_about_query(outcome.query_id, claims, label_of, cited)
    for i, rc in enumerate(shown, 1):
        lines += _connection_section(i, rc, claims, label_of, cited, outcome.query_id)
    lines += ["## What is missing", ""]
    missing = _missing_lines(outcome)
    lines += missing or ["- Nothing recorded as missing for the channels that ran."]
    lines += ["", f"Coverage manifest: `{outcome.coverage.manifest_id}` (dataset `{outcome.coverage.dataset_version}`)."]
    if len(outcome.ranked) > len(shown):
        lines.append(f"Showing {len(shown)} of {len(outcome.ranked)} candidates.")
    unreviewed = sum(1 for i in dict.fromkeys(cited) if claims[i].review_state is not ReviewState.reviewed)
    if not cited:  # e.g. phenotype-only candidates: similarities, no claim to review yet
        step = "Ask a domain expert whether these symptom similarities are meaningful; no claim is cited in this brief yet."
    elif unreviewed:
        step = f"Ask a domain expert to review the {unreviewed} unreviewed claim(s) cited in this brief."
    else:
        step = "Ask a domain expert to confirm the reviewed claims still reflect the sources."
    return ActionCard(
        card_id=_card_id("evidence_brief", outcome.query_id, outcome.coverage.manifest_id, audience),
        kind="evidence_brief",
        audience=audience,  # type: ignore[arg-type]
        entity_id=outcome.query_id,
        this_week=step,
        responsible_human=outcome.gap.reviewer_role if outcome.gap else REVIEWER_ROLE,
        body_markdown="\n".join(lines),
        claim_ids=tuple(dict.fromkeys(cited)),
        coverage_manifest_id=outcome.coverage.manifest_id,
        limitations=(
            ("Ranking uses the evidence category and evidence tie-breakers first; symptom similarity only orders "
             "candidates that tie on all of those. No probability is computed."),
            "Missing data is reported as missing, never as zero.",
            "No claim here has been reviewed by an expert unless its line says reviewed.",
        ),
        generated_by="template",
        created_at=now,
    )


def _known_about_query(query_id: str, claims: dict[str, Claim], label_of: Label, cited: list[str]) -> list[str]:
    """Stored claims that name the query entity itself, whether or not they lead to a connection."""
    about = sorted(i for i, c in claims.items() if query_id in (c.subject_id, c.object_id))
    if not about:
        return []
    lines = [f"## Known claims about {_name(label_of, query_id)}", ""]
    for i in about:
        lines.append(_claim_line(claims[i], label_of, claims, cited))
        cited.append(i)
    return [*lines, ""]


def _route_lines(claims: dict[str, Claim], a: str, b: str, label_of: Label, cited: list[str]) -> list[str]:
    """Readable claim-graph routes between the query and a candidate (explanation, not a score)."""
    out = find_paths(claims, a, b)
    if not out.paths:
        return ["", "Routes in stored claims: none of up to 4 steps (a gap in the indexed evidence, not proof of absence)."]
    lines = ["", "Routes in stored claims (explanation only; each step is one or more claims):"]
    for p in out.paths:
        chain = " → ".join(_name(label_of, n) for n in p.nodes)
        tag = "**hypothesis only**" if p.hypothesis_only else "observed or reported steps"
        ids = list(p.claim_ids)
        cited.extend(ids)
        lines.append(f"- {chain} ({tag}) {_cite(ids)}")
    return lines


def _connection_section(
    n: int, rc: RankedConnection, claims: dict[str, Claim], label_of: Label, cited: list[str], query_id: str
) -> list[str]:
    r = rc.result
    lines = [f"## {n}. {_name(label_of, r.candidate_id)}", "", f"Evidence category: **{r.category.value}**"]
    background = (
        f" (also restated as known background in {rc.background_citations} other paper(s))" if rc.background_citations else ""
    )
    lines.append(
        f"Direct link: {'yes' if rc.direct else 'no'}; independent studies behind it: {rc.independent_lineages}"
        f"{background}; reviewed supporting claims: {rc.reviewed_support}."
    )
    if r.compatibility_flags:
        lines.append(f"Context mismatches: {', '.join(r.compatibility_flags)}.")
    if not r.shared_treatment_inference_allowed:
        lines.append("A shared-treatment inference is **not** allowed from this evidence.")
    lines += ["", "Per channel:"]
    for c in r.comparisons:
        parts = [c.availability.value]
        if c.score is not None:
            parts.append(f"similarity {c.score:.3f} ({c.score_definition or 'definition not recorded'}; not a probability)")
        if c.context_matches:
            parts.append("matches: " + "; ".join(c.context_matches))
        if c.missing_fields:
            parts.append("missing: " + ", ".join(c.missing_fields))
        lines.append(f"- {c.channel_id}: " + " | ".join(parts))
    lines += _route_lines(claims, query_id, r.candidate_id, label_of, cited)
    path = [i for i in r.path_claim_ids if i in claims]
    if path:
        lines += ["", "Supporting claims:"]
        for i in path:
            lines.append(_claim_line(claims[i], label_of, claims, cited))
            cited.append(i)
    lines.append("")
    return lines


def _missing_lines(outcome: QueryOutcome) -> list[str]:
    out = []
    for ch in outcome.coverage.per_channel:
        if ch.availability.value != "available":
            out.append(f"- Channel `{ch.channel_id}`: {ch.availability.value}. {ch.note}".rstrip())
    for s in outcome.coverage.per_source:
        if s.status.value == "failed":
            out.append(f"- Source `{s.source}` failed: {s.error}")
    return out


def gap_followup(
    gap: GapResult,
    *,
    label_of: Label = lambda _id: "",
    audience: str = "family",
    now: datetime | None = None,
) -> ActionCard:
    """The 'gap_followup': scoped absence, what could change it, who should review. No invented experiment."""
    now = now or datetime.now(UTC)
    lines = [f"# {gap.statement}", ""]
    if gap.entity_id:
        lines += [f"About: {_name(label_of, gap.entity_id)}", ""]
    if audience == "family":
        lines += [
            (
                "We didn't find a supported connection yet. That's an answer too: here's what's missing and "
                "who could help check."
            ),
            "",
        ]
    lines += [f"Gap kind: **{gap.kind.replace('_', ' ')}**.", "", "Information that could change this result:"]
    lines += [f"- {m}" for m in gap.missing_information]
    if gap.failed_sources:
        lines += ["", "Sources that failed during this check:"] + [f"- {s}" for s in gap.failed_sources]
    if gap.known_claim_ids:
        lines += ["", "What is already known (all unreviewed unless stated):"]
        lines += [f"- claim [^c:{i}]" for i in gap.known_claim_ids]
    lines += ["", f"Coverage manifest: `{gap.coverage_manifest_id}`.", "", gap.scope_note]
    return ActionCard(
        card_id=_card_id("gap_followup", gap.entity_id or "", gap.coverage_manifest_id, audience),
        kind="gap_followup",
        audience=audience,  # type: ignore[arg-type]
        entity_id=gap.entity_id,
        this_week=f"Share this gap report with: {gap.reviewer_role}.",
        responsible_human=gap.reviewer_role,
        body_markdown="\n".join(lines),
        claim_ids=gap.known_claim_ids,
        coverage_manifest_id=gap.coverage_manifest_id,
        limitations=(
            "Absence is scoped to the indexed evidence and the date above; it does not mean nothing exists.",
            "The list of information that could change the result does not promise that any assay will resolve it.",
        ),
        generated_by="template",
        created_at=now,
    )


def _asset_facts(asset: AssetResult, claims: dict[str, Claim]) -> list[str]:
    missing = [i for i in asset.relevance_claim_ids if i not in claims]
    if missing:
        raise CardError(f"asset {asset.asset_id} cites relevance claims that are not in the store: {missing}")
    return list(asset.relevance_claim_ids)


def asset_reuse(
    asset: AssetResult,
    claims: dict[str, Claim],
    *,
    label_of: Label = lambda _id: "",
    audience: str = "science",
    now: datetime | None = None,
) -> ActionCard:
    """The 'asset_reuse' card: scope, access, what differs, what needs expert review."""
    now = now or datetime.now(UTC)
    cite_ids = _asset_facts(asset, claims)
    lines = [f"# Asset: {asset.label}", "", f"Kind: {asset.asset_kind.value.replace('_', ' ')}. Source: {asset.source_url}", ""]
    lines += ["Why it is relevant:"] + [_claim_line(claims[i], label_of) for i in cite_ids] + [""]
    lines.append(f"Access conditions: {asset.access_conditions or 'not recorded'}.")
    if asset.status:
        lines.append(
            f"Status (verbatim from source): {asset.status}; checked {asset.status_checked_at} at {asset.status_source_url}."
        )
    else:
        lines.append("Status: not recorded.")
    if asset.reuse_limits:
        lines += ["", "What differs from the question (reuse limits):"] + [f"- {x}" for x in asset.reuse_limits]
    if asset.needs_expert_review:
        lines += ["", "Needs expert review before reuse:"] + [f"- {x}" for x in asset.needs_expert_review]
    return ActionCard(
        card_id=_card_id("asset_reuse", asset.asset_id, audience),
        kind="asset_reuse",
        audience=audience,  # type: ignore[arg-type]
        this_week="Ask the asset owner to confirm whether this asset suits the research question.",
        responsible_human="asset owner",
        body_markdown="\n".join(lines),
        claim_ids=tuple(cite_ids),
        asset_ids=(asset.asset_id,),
        reuse_limits=asset.reuse_limits,
        contact=asset.contact,
        limitations=("Asset relevance comes from the cited claims only; suitability is for the asset owner to confirm.",),
        generated_by="template",
        created_at=now,
    )


def outreach_note(
    asset: AssetResult,
    claims: dict[str, Claim],
    *,
    label_of: Label = lambda _id: "",
    now: datetime | None = None,
) -> ActionCard:
    """The 'outreach_note' (family audience): a draft for the user to review and send themselves.
    Needs a VERIFIED PUBLIC contact on the asset; without one it refuses (no invented contacts)."""
    if asset.contact is None:
        raise CardError(f"asset {asset.asset_id} has no verified public contact; an outreach note cannot be drafted")
    now = now or datetime.now(UTC)
    cite_ids = _asset_facts(asset, claims)
    c = asset.contact
    lines = [
        f"# Draft note to {c.label}",
        "",
        f"Public contact route: {c.url} (verified {c.verified_at}, source {c.source_url}).",
        "",
        f"Why this may be relevant to your question about {asset.label}:",
    ]
    lines += [_claim_line(claims[i], label_of) for i in cite_ids]
    lines += [
        "",
        "Questions you could ask:",
        "- Does this asset cover the situation described above, and what differs?",
        "- What are the access conditions, and who decides?",
        "",
        "Nothing is shared automatically. You review this draft and decide what to send.",
    ]
    return ActionCard(
        card_id=_card_id("outreach_note", asset.asset_id),
        kind="outreach_note",
        audience="family",
        this_week="Read the draft, decide what you are comfortable sharing, and send it yourself.",
        responsible_human="the user (reviews and sends)",
        body_markdown="\n".join(lines),
        claim_ids=tuple(cite_ids),
        asset_ids=(asset.asset_id,),
        contact=c,
        reuse_limits=asset.reuse_limits,
        limitations=("A draft only. The relevance is stated by unreviewed claims where marked.",),
        generated_by="template",
        created_at=now,
    )


_REPORT_KEYS = (
    "run_id", "experiment_spec_hash", "scene_hash", "simulator_name", "simulator_version", "random_seed",
    "review_state", "overall", "checks", "failures", "scope_label",
)
_ALWAYS_NOT_MODELED = ("biology", "physical_execution")
SIM_REVIEWER = "lab-automation engineer (unassigned)"


def simulation_report(
    report: dict, claims: dict[str, Claim], *, source_claim_ids: tuple[str, ...] = (),
    audience: str = "science", now: datetime | None = None,
) -> ActionCard:
    """Readable card for one recorded simulation run (an engineering check, never biological evidence).

    The report is the dict `robotics/simulate.py` writes. The card restates it; it never reruns
    anything, and it refuses a report that does not mark biology and physical execution `not_modeled`.
    """
    now = now or datetime.now(UTC)
    missing = [k for k in _REPORT_KEYS if k not in report]
    if missing:
        raise CardError(f"simulation report is missing {missing}")
    status = {c["check_name"]: c["status"] for c in report["checks"]}
    wrong = [n for n in _ALWAYS_NOT_MODELED if status.get(n) != "not_modeled"]
    if wrong:
        raise CardError(f"report does not mark {wrong} as not_modeled; refusing to present it")
    absent = [i for i in source_claim_ids if i not in claims]
    if absent:
        raise CardError(f"source claims not in the store: {absent}")
    lines = [
        f"# Simulation report: run `{report['run_id']}`",
        "",
        f"> {report['scope_label']}",
        "",
        (
            "This is an engineering check of a proposed liquid-handling workflow in a simplified model. It is "
            "not an experiment result. It does not show that any biological idea is right and it does not "
            "raise any similarity, claim or ranking."
        ),
        "",
        f"- Overall: **{str(report['overall']).upper()}**",
        f"- Specification hash: `{report['experiment_spec_hash']}`; scene hash: `{report['scene_hash']}`",
        f"- Simulator: {report['simulator_name']} {report['simulator_version']}; seed {report['random_seed']}",
        f"- Review state of the specification: {report['review_state']}",
        "",
        "## Checks",
        "",
        "| check | status | reason |",
        "|---|---|---|",
    ]
    lines += [f"| {c['check_name']} | {c['status']} | {c.get('reason', '')} |" for c in report["checks"]]
    lines += ["", "## Failures", ""]
    lines += [
        f"- operation {f['op_index']}: **{f['check']}**: {f['reason']}" for f in report["failures"]
    ] or ["- none recorded"]
    if source_claim_ids:
        lines += ["", "## Claims the specification traces to (unreviewed unless marked)", ""]
        lines += [_claim_line(claims[i], lambda _id: "") for i in source_claim_ids]
    lines += [
        "",
        (
            "Not modelled: biological outcomes (`biology`) and real-world execution (`physical_execution`: "
            "no hardware, calibration or real-liquid validation)."
        ),
    ]
    failed = report["overall"] != "pass"
    return ActionCard(
        card_id=_card_id("simulation_report", str(report["run_id"]), audience),
        kind="simulation_report",
        audience=audience,  # type: ignore[arg-type]
        this_week=(
            "Have a lab-automation engineer read the failed checks and fix or reject the specification."
            if failed
            else "Have a lab-automation engineer and the protocol author review the specification before any real use."
        ),
        responsible_human=SIM_REVIEWER,
        body_markdown="\n".join(lines),
        claim_ids=tuple(source_claim_ids),
        limitations=(
            "Simplified kinematic model; no liquid dynamics, calibration or hardware validation.",
            "A pass is not evidence for any biological claim; a fail is reported, never clipped or hidden.",
        ),
        generated_by="template",
        created_at=now,
    )
