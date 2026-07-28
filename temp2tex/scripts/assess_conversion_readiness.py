#!/usr/bin/env python3
"""Summarize Temp2TeX evidence, mapping, build, and visual-verification gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from prepare_front_matter_confirmation import validation_errors as front_matter_confirmation_errors


SCHEMA_VERSION = "temp2tex.conversion-readiness.v2"
WORD_SUFFIXES = {".doc", ".docm", ".docx", ".dot", ".dotm", ".dotx", ".rtf"}
VALIDATION_SCHEMA_VERSION = "temp2tex.package-validation.v1"
FINGERPRINT_EXCLUDED_NAMES = {
    "package_validation.json",
    "compile_report.json",
    "render_compare_report.json",
    "conversion_readiness.json",
    # The validator records the final handoff fingerprint inside this file.
    # It must not invalidate the report merely because that status is updated.
    "HANDOFF_STATUS.md",
}
FINGERPRINT_EXCLUDED_SUFFIXES = {".aux", ".log", ".out", ".pdf", ".dvi", ".ps"}


def package_contract_fingerprint(package: Path) -> str:
    """Match the validator's editable-input identity for stale-report checks."""
    digest = hashlib.sha256()
    if not package.is_dir():
        return digest.hexdigest()[:16]
    for path in sorted((item for item in package.rglob("*") if item.is_file()), key=lambda item: item.relative_to(package).as_posix()):
        relative = path.relative_to(package).as_posix()
        if path.name in FINGERPRINT_EXCLUDED_NAMES or path.suffix.lower() in FINGERPRINT_EXCLUDED_SUFFIXES:
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def system_triage_fingerprint(triage: dict[str, Any] | None) -> str | None:
    if not isinstance(triage, dict):
        return None
    payload = json.dumps(triage, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]

# A continuation should advance one meaningful layout concern, not ask the
# next model to rediscover a useful ordering from hundreds of pending units.
# These names mirror the review queue's dependency-aware role order.
SEMANTIC_MAPPING_SLICES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("front_matter", (
        "front_matter.article_type", "front_matter.title", "front_matter.author", "front_matter.affiliation",
        "front_matter.metadata", "front_matter.abstract", "front_matter.keywords",
        "front_matter.english_title", "front_matter.english_author",
        "front_matter.english_affiliation", "front_matter.english_abstract",
        "front_matter.english_keywords", "front_matter.metadata_table",
    )),
    ("page_and_furniture", (
        "cover.structure", "toc.structure", "toc.layout", "running_furniture", "page.frame",
        "page.columns", "page.text_grid", "page.numbering", "line.numbering", "paragraph.tab_stops", "paragraph.drop_cap", "run.character_effects", "run.character_styles", "document.theme", "word.unmodeled_format", "floating_text",
    )),
    ("headings_and_body", (
        "heading.level0", "heading.level1", "heading.level2", "body.list_system",
        "body.list_item", "body.paragraph",
    )),
    ("notes", ("footnote.system", "footnote.content", "endnote.system", "endnote.content")),
    ("equations", ("equation.system", "equation.instance")),
    ("block_decorations", ("block.decoration",)),
    ("tables", ("table.structure", "table.caption")),
    ("figures", ("figure.placement", "figure.caption")),
    ("back_matter", (
        "references.system", "references.heading", "references.entry",
        "appendix.system", "appendix.heading",
    )),
    ("guidance", ("guidance.instruction",)),
)

# Visual diagnostics identify where the rendered result diverges; they cannot
# by themselves identify a Word rule to change.  Each repair concern therefore
# has a deliberately bounded set of Word roles that must be reread before an
# agent edits the class or materializes a render probe.
VISUAL_REPAIR_ROLES: dict[str, tuple[str, ...]] = {
    "structural_flow": (
        "page.frame", "page.columns", "page.text_grid", "body.paragraph", "paragraph.break_policy",
        "front_matter.title", "front_matter.author", "front_matter.affiliation", "front_matter.metadata",
        "front_matter.abstract", "front_matter.keywords", "table.structure", "table.caption",
        "figure.placement", "figure.caption", "references.system", "appendix.system",
    ),
    "local_page_furniture": ("running_furniture", "page.numbering", "floating_text", "page.frame"),
    "front_matter_spacing": (
        "front_matter.article_type", "front_matter.title", "front_matter.author", "front_matter.affiliation",
        "front_matter.metadata", "front_matter.abstract", "front_matter.keywords", "page.columns",
    ),
    "object_caption_flow": ("table.structure", "table.caption", "figure.placement", "figure.caption", "floating_text", "body.paragraph"),
    "page_frame": ("page.frame", "page.columns", "body.paragraph", "paragraph.break_policy"),
    "body_density": ("body.paragraph", "paragraph.break_policy", "page.text_grid", "run.script_language"),
    "running_furniture": ("running_furniture", "page.numbering", "floating_text", "page.frame"),
}

STRUCTURAL_FLOW_ANCHOR_ROLES: dict[str, tuple[str, ...]] = {
    "title": ("front_matter.title",),
    "abstract": ("front_matter.abstract",),
    "keywords": ("front_matter.keywords",),
    "introduction": ("page.columns", "body.paragraph"),
    "methods": ("body.paragraph",),
    "table": ("table.structure", "table.caption"),
    "figure": ("figure.placement", "figure.caption"),
    "references": ("references.system", "references.entry"),
    "appendix": ("appendix.system", "appendix.heading"),
    "acknowledgements": ("back_matter.declaration", "body.paragraph"),
    "data_availability": ("back_matter.declaration", "body.paragraph"),
}


def load(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def word_source_present(inventory: dict[str, Any] | None) -> bool:
    for entry in (inventory or {}).get("files") or []:
        if not isinstance(entry, dict):
            continue
        suffix = str(entry.get("suffix") or Path(str(entry.get("name") or "")).suffix).lower()
        if suffix in WORD_SUFFIXES and isinstance(entry.get("inspection"), dict):
            return True
    return False


def system_format_triage_required(ledger: dict[str, Any] | None) -> bool:
    """Return whether the Word ledger contains system-level format evidence."""
    objects = (ledger or {}).get("objects")
    if not isinstance(objects, dict):
        return False
    return bool(
        (isinstance(objects.get("text_grid_evidence"), dict) and objects["text_grid_evidence"].get("present"))
        or (isinstance(objects.get("tab_stop_evidence"), list) and objects["tab_stop_evidence"])
        or (isinstance(objects.get("paragraph_break_policy_evidence"), dict) and objects["paragraph_break_policy_evidence"].get("observed"))
        or (isinstance(objects.get("character_effect_evidence"), list) and objects["character_effect_evidence"])
        or (isinstance(objects.get("character_style_evidence"), list) and objects["character_style_evidence"])
        or (isinstance(objects.get("script_language_evidence"), dict) and objects["script_language_evidence"].get("observed"))
        or (isinstance(objects.get("theme_format_evidence"), dict) and objects["theme_format_evidence"].get("present"))
        or (isinstance(objects.get("unmodeled_format_properties"), dict) and objects["unmodeled_format_properties"].get("properties"))
    )


def next_batch_template_path(package: Path | None, name: str) -> str:
    """Return a non-overwriting, role-scoped review-template filename."""
    stem = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "mapping"
    prefix = f"atomic_mapping_{stem}_"
    if package is None:
        return f"{prefix}001_draft.json"
    highest = 0
    for candidate in package.glob(f"{prefix}*_draft.json"):
        match = re.fullmatch(rf"{re.escape(prefix)}(\d+)_draft\.json", candidate.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"{prefix}{highest + 1:03d}_draft.json"


def review_output_path(template_path: str) -> str:
    """Pair each decision draft with a readable review sheet of the same scope."""
    if template_path.endswith("_draft.json"):
        return template_path.removesuffix("_draft.json") + "_review.md"
    return template_path + ".review.md"


def recommended_mapping_slice(audit: dict[str, Any] | None, package: Path | None = None) -> dict[str, Any] | None:
    """Return the first pending semantic work slice from immutable audit units."""
    pending_role_counts: dict[str, int] = {}
    for unit in (audit or {}).get("units") or []:
        if not isinstance(unit, dict) or str(unit.get("status") or "") != "needs_decision":
            continue
        for candidate in unit.get("role_candidates") or []:
            if not isinstance(candidate, dict):
                continue
            role = str(candidate.get("role") or "").strip()
            if role:
                pending_role_counts[role] = pending_role_counts.get(role, 0) + 1
    if not pending_role_counts:
        return None

    for name, roles in SEMANTIC_MAPPING_SLICES:
        selected = [role for role in roles if pending_role_counts.get(role)]
        if selected:
            template_path = next_batch_template_path(package, name)
            review_path = review_output_path(template_path)
            return {
                "name": name,
                "roles": selected,
                "pending_evidence_units": sum(pending_role_counts[role] for role in selected),
                "role_counts": {role: pending_role_counts[role] for role in selected},
                "batch_template_output": template_path,
                "review_output": review_path,
                "command_hint": "Run from the package directory: python <temp2tex-skill>/scripts/prepare_atomic_mapping_review.py word_format_ledger.json --decisions atomic_mapping_decisions.json --package . --roles " + ",".join(selected) + " --pending-only --batch-size 20 --batch-index 1 --output " + review_path + " --batch-template-output " + template_path,
                "reason": "This is the earliest dependency-ordered semantic concern with pending Word evidence. It narrows only the next review packet; all other pending groups remain in the strict audit. The role-scoped output name avoids overwriting a prior review packet.",
            }

    selected = sorted(pending_role_counts)
    template_path = next_batch_template_path(package, "other_source_roles")
    review_path = review_output_path(template_path)
    return {
        "name": "other_source_roles",
        "roles": selected,
        "pending_evidence_units": sum(pending_role_counts.values()),
        "role_counts": {role: pending_role_counts[role] for role in selected},
        "batch_template_output": template_path,
        "review_output": review_path,
        "command_hint": "Run from the package directory: python <temp2tex-skill>/scripts/prepare_atomic_mapping_review.py word_format_ledger.json --decisions atomic_mapping_decisions.json --package . --roles " + ",".join(selected) + " --pending-only --batch-size 20 --batch-index 1 --output " + review_path + " --batch-template-output " + template_path,
        "reason": "Pending source roles are outside the built-in semantic groups. Review them as an explicit bounded packet without changing other evidence. The role-scoped output name avoids overwriting a prior review packet.",
    }


def positive_number(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) and float(value) > 0 else 0.0


def anchor_evidence_ids(diagnostics: dict[str, Any], anchor_names: set[str]) -> list[str]:
    """Return explicit Word evidence IDs attached to the relevant PDF anchors.

    A visual label such as ``table`` is only a diagnosis category.  A custom
    anchor may additionally bind that label to a concrete immutable Word
    evidence ID, allowing the next agent to inspect one source object rather
    than every table or figure in a large template.
    """
    raw = diagnostics.get("anchor_source_evidence_ids")
    if not isinstance(raw, dict):
        return []
    evidence_ids: set[str] = set()
    for anchor_name in anchor_names:
        values = raw.get(anchor_name)
        if isinstance(values, str):
            values = [values]
        if isinstance(values, list):
            evidence_ids.update(str(value).strip() for value in values if isinstance(value, str) and value.strip())
    return sorted(evidence_ids)


def visual_repair_evidence_scope(
    audit: dict[str, Any] | None,
    concern: str,
    package: Path | None,
    ledger: dict[str, Any] | None = None,
    system_triage: dict[str, Any] | None = None,
    roles_override: list[str] | None = None,
    evidence_ids_override: list[str] | None = None,
) -> dict[str, Any]:
    """Return the exact Word audit units an agent must reread for one repair.

    This is a readback scope, not a permission to modify every returned unit.
    The model still has to select one visible source-backed boundary and keep
    all unrelated evidence unchanged.  Keeping the evidence IDs in readiness
    makes a PDF diagnosis traceable back to a paragraph/run or ancillary Word
    unit instead of inviting visual guesswork.
    """
    roles = list(roles_override if roles_override is not None else VISUAL_REPAIR_ROLES.get(concern, ()))
    requested_evidence_ids = sorted({str(value).strip() for value in evidence_ids_override or [] if str(value).strip()})
    if not roles:
        return {
            "status": "not_applicable",
            "roles": [],
            "requested_evidence_ids": requested_evidence_ids,
            "matched_units": 0,
            "evidence_units": [],
            "reason": "This concern must be repaired at the comparison-fixture level before selecting a Word format rule.",
        }
    if not isinstance(audit, dict) or not isinstance(audit.get("units"), list):
        return {
            "status": "audit_unavailable",
            "roles": roles,
            "requested_evidence_ids": requested_evidence_ids,
            "matched_units": 0,
            "evidence_units": [],
            "reason": "No ledger-matched atomic audit is available. Rebuild or complete it before using a visual diagnosis to choose a Word rule.",
        }
    if isinstance(ledger, dict) and audit.get("ledger_fingerprint") != ledger.get("evidence_fingerprint"):
        return {
            "status": "audit_mismatch",
            "roles": roles,
            "requested_evidence_ids": requested_evidence_ids,
            "matched_units": 0,
            "evidence_units": [],
            "reason": "The atomic audit is not bound to the current Word ledger. Refresh the audit before using its evidence IDs for a visual repair.",
        }
    if system_format_triage_required(ledger) and audit.get("system_triage_fingerprint") != system_triage_fingerprint(system_triage):
        return {
            "status": "audit_triage_mismatch",
            "roles": roles,
            "requested_evidence_ids": requested_evidence_ids,
            "matched_units": 0,
            "evidence_units": [],
            "reason": "The atomic audit is stale relative to the current system-format child queue. Rerun strict audit before using its evidence IDs for a visual repair.",
        }

    selected = []
    wanted = set(roles)
    wanted_evidence_ids = set(requested_evidence_ids)
    for unit in audit.get("units") or []:
        if not isinstance(unit, dict):
            continue
        candidates = unit.get("role_candidates") or []
        unit_roles = {
            str(candidate.get("role") or "").strip()
            for candidate in candidates
            if isinstance(candidate, dict) and str(candidate.get("role") or "").strip()
        }
        final_role = str(unit.get("role") or "").strip()
        if final_role:
            unit_roles.add(final_role)
        matched_roles = sorted(unit_roles & wanted)
        evidence_id = str(unit.get("evidence_id") or "")
        if wanted_evidence_ids and evidence_id not in wanted_evidence_ids:
            continue
        if not wanted_evidence_ids and not matched_roles:
            continue
        selected.append({
            "evidence_id": evidence_id,
            "kind": str(unit.get("kind") or ""),
            "source_scope": str(unit.get("source_scope") or ""),
            "container": str(unit.get("container") or ""),
            "roles": matched_roles or sorted(unit_roles),
            "status": str(unit.get("status") or ""),
            "latex_file": str(unit.get("latex_file") or ""),
            "latex_token": str(unit.get("latex_token") or ""),
        })
    selected.sort(key=lambda item: (min((roles.index(role) for role in item["roles"] if role in roles), default=len(roles)), item["evidence_id"]))
    command_hint = None
    if package is not None:
        selection_flag = (
            " --evidence-ids " + ",".join(requested_evidence_ids)
            if requested_evidence_ids else
            " --roles " + ",".join(roles)
        )
        command_hint = (
            "Run from the package directory: python <temp2tex-skill>/scripts/prepare_atomic_mapping_review.py "
            "word_format_ledger.json --decisions atomic_mapping_decisions.json --package ."
            + selection_flag
            + " --output visual_repair_source_review.md"
        )
    return {
        "status": "ready" if selected else "no_matching_evidence_ids" if requested_evidence_ids else "no_matching_units",
        "roles": roles,
        "requested_evidence_ids": requested_evidence_ids,
        "matched_units": len(selected),
        "evidence_units": selected,
        "command_hint": command_hint,
        "reason": (
            (
                "Reread these ledger-matched Word units and the immediately adjacent ledger paragraphs at each shifted boundary before selecting one source-backed repair; do not modify every listed role."
                if concern == "structural_flow" else
                "Reread these ledger-matched Word units before selecting one source-backed repair; do not modify every listed role."
            ) if selected else
            "The explicit PDF-anchor evidence IDs are absent from the ledger-matched atomic audit. Rebuild the anchor map from current Word evidence; do not fall back to every object of the same role."
            if requested_evidence_ids else
            "The atomic audit contains no unit for the expected roles. Inspect the ledger capture and record the missing source evidence instead of deriving a visual rule."
        ),
    }


def structural_flow_roles(anchor_shifts: dict[str, Any], cause_scores: dict[str, Any]) -> list[str]:
    """Narrow structural-flow readback to the actual shifted role boundary."""
    roles = ["page.frame", "page.columns"]
    for anchor in anchor_shifts:
        roles.extend(STRUCTURAL_FLOW_ANCHOR_ROLES.get(str(anchor), ()))
    if len(roles) == 2:
        # Page-count divergence without a stable shifted anchor still needs a
        # bounded front-matter/body boundary readback, not every Word role.
        roles.extend(("front_matter.abstract", "front_matter.keywords", "body.paragraph", "paragraph.break_policy"))
        if positive_number(cause_scores.get("table_figure_caption_or_float")) >= 0.5:
            roles.extend(("table.structure", "table.caption", "figure.placement", "figure.caption"))
    return list(dict.fromkeys(roles))


def visual_repair_plan(
    compare_report: dict[str, Any] | None,
    audit: dict[str, Any] | None = None,
    package: Path | None = None,
    ledger: dict[str, Any] | None = None,
    system_triage: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Choose one evidence-bound visual concern before any calibration probe.

    PDF diagnostics often expose several causes at once. This planner encodes
    the dependency order so a continuation agent does not tune margins, body
    size, or page furniture while the fixture or document flow is still wrong.
    It proposes a *review target*, never an automatic source-spec edit.
    """
    if not isinstance(compare_report, dict):
        return None
    comparability = compare_report.get("layout_comparability")
    diagnostics = compare_report.get("layout_diagnostics")
    if not isinstance(comparability, dict) or not isinstance(diagnostics, dict):
        return None

    def with_evidence(plan: dict[str, Any]) -> dict[str, Any]:
        plan["evidence_review_scope"] = visual_repair_evidence_scope(
            audit,
            str(plan["concern"]),
            package,
            ledger,
            system_triage,
            plan.get("evidence_roles") if isinstance(plan.get("evidence_roles"), list) else None,
            plan.get("evidence_ids") if isinstance(plan.get("evidence_ids"), list) else None,
        )
        return plan
    summary = diagnostics.get("summary") if isinstance(diagnostics.get("summary"), dict) else {}
    status = str(comparability.get("status") or "unavailable").lower()
    reference_pages = compare_report.get("reference_pages") or []
    generated_pages = compare_report.get("generated_pages") or []
    page_count_matches = bool(reference_pages and generated_pages and len(reference_pages) == len(generated_pages))
    anchor_shifts = summary.get("anchor_page_shifts") if isinstance(summary.get("anchor_page_shifts"), dict) else {}
    cause_scores = summary.get("cause_scores") if isinstance(summary.get("cause_scores"), dict) else {}
    local_gate_failed = summary.get("local_zone_gate_status") == "failed"

    if status != "comparable" or summary.get("semantic_comparable") is not True:
        return with_evidence({
            "concern": "same_content_fixture",
            "priority": 1,
            "reason": "The PDF pair is not a full-document same-content comparison, so geometry and visual scores cannot select a class change.",
            "next_action": "Repair the fixture, unique anchor map, source renderer, or comparison route before any layout calibration.",
            "blocked_actions": ["page-frame calibration", "body-density calibration", "render-probe promotion", "visual-fidelity claim"],
        })
    if not page_count_matches or anchor_shifts or positive_number(cause_scores.get("pagination_or_structural_flow")) >= 0.5:
        shifted_anchor_evidence_ids = anchor_evidence_ids(diagnostics, set(anchor_shifts))
        return with_evidence({
            "concern": "structural_flow",
            "evidence_roles": structural_flow_roles(anchor_shifts, cause_scores),
            "evidence_ids": shifted_anchor_evidence_ids,
            "priority": 1,
            "reason": "Page count, anchor pages, or the structural-flow diagnostic differ; this precedes any global geometry adjustment.",
            "next_action": "Inspect source-backed section breaks, front-matter/body column transition, float policy, caption flow, and back-matter/appendix boundaries. Repair one identified flow boundary, then rerender the same fixture.",
            "blocked_actions": ["page-frame calibration", "global body-font adjustment", "unrelated furniture tuning"],
        })
    if local_gate_failed:
        return with_evidence({
            "concern": "local_page_furniture",
            "priority": 1,
            "reason": "A declared local page-furniture placement gate failed even though the full fixture is comparable.",
            "next_action": "Repair only the named page-fixed or flow-relative furniture candidate and rerun its local contract. Keep body and margin settings unchanged.",
            "blocked_actions": ["global page-margin calibration", "body-density calibration", "promotion of the failed furniture candidate"],
        })
    if positive_number(cause_scores.get("front_matter_spacing")) >= 0.5:
        return with_evidence({
            "concern": "front_matter_spacing",
            "priority": 1,
            "reason": "Front-matter spacing is the leading remaining source-backed layout cause.",
            "next_action": "Recheck title, author, affiliation, abstract, keyword, and first-body-boundary evidence; repair one role boundary or column-transition decision before changing page geometry.",
            "blocked_actions": ["page-frame calibration from the first-page text box", "global body-density adjustment"],
        })
    if positive_number(cause_scores.get("table_figure_caption_or_float")) >= 0.5:
        object_anchor_names = {
            str(name) for name in (diagnostics.get("document_anchor_deltas") or {})
            if str(name) == "table" or str(name) == "figure" or str(name).startswith(("table.", "table_", "figure.", "figure_"))
        }
        return with_evidence({
            "concern": "object_caption_flow",
            "evidence_ids": anchor_evidence_ids(diagnostics, object_anchor_names),
            "priority": 1,
            "reason": "Table, figure, caption, note, or float flow remains the leading visual cause.",
            "next_action": "Audit the selected object, external caption relation, facing paragraph gaps, table geometry, and source inline/anchor evidence. Use at most one isolated placement or spacing probe.",
            "blocked_actions": ["global page-margin calibration", "global body-font adjustment", "combined parameter search"],
        })
    if positive_number(cause_scores.get("page_frame_or_body_box")) >= 0.5:
        return with_evidence({
            "concern": "page_frame",
            "priority": 1,
            "reason": "The remaining diagnostics point to a stable page-frame or body-box mismatch after higher-order flow checks passed.",
            "next_action": "Run suggest_page_calibration.py. Materialize a probe only when it returns candidate_available=true; otherwise follow its rejection reason instead of adjusting margins manually.",
            "blocked_actions": ["manual margin edits", "body-font probe before page-frame eligibility"],
        })
    if positive_number(cause_scores.get("body_density")) >= 0.5:
        return with_evidence({
            "concern": "body_density",
            "priority": 1,
            "reason": "The remaining diagnostics point to body font/baseline density rather than page frame or structural flow.",
            "next_action": "Run suggest_body_calibration.py and materialize at most one evidence-bounded candidate only when its preconditions pass.",
            "blocked_actions": ["manual global font-size search", "page-count repair without the body-calibration gate"],
        })
    if positive_number(cause_scores.get("header_footer")) >= 0.5:
        return with_evidence({
            "concern": "running_furniture",
            "priority": 1,
            "reason": "The remaining diagnostics point to header/footer occupancy or running-furniture geometry.",
            "next_action": "Create or refine a first/default/even local furniture contract and repair only its source-backed candidate.",
            "blocked_actions": ["global margin calibration", "treating furniture text presence as placement acceptance"],
        })
    return with_evidence({
        "concern": "visual_review",
        "priority": 1,
        "reason": "No diagnostic cause crossed the automatic review threshold.",
        "next_action": "Inspect diff previews against the source ledger and choose one role-local discrepancy; do not start a parameter search.",
        "blocked_actions": ["global multi-parameter tuning", "render-verified promotion without a measured candidate"],
    })


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Temp2TeX Conversion Readiness",
        "",
        f"- Current phase: `{report['phase']}`",
        f"- Continuation checkpoint: `{report['checkpoint_handoff']['status']}`",
        f"- Ordinary handoff: `{report['ordinary_handoff']['status']}`",
        f"- Full source fidelity: `{report['full_source_fidelity']['status']}`",
        "",
        "## Next Actions",
        "",
    ]
    lines.extend(f"- {item}" for item in report["next_actions"])
    mapping_slice = report.get("recommended_mapping_slice")
    if isinstance(mapping_slice, dict):
        lines.extend([
            "", "## Recommended Mapping Slice", "",
            f"- Concern: `{mapping_slice['name']}`",
            f"- Roles: {', '.join(f'`{role}`' for role in mapping_slice['roles'])}",
            f"- Pending evidence units in this slice: `{mapping_slice['pending_evidence_units']}`",
            f"- Readable review sheet: `{mapping_slice['review_output']}`",
            f"- Decision-draft output: `{mapping_slice['batch_template_output']}`",
            f"- Command hint: `{mapping_slice['command_hint']}`",
            f"- Scope: {mapping_slice['reason']}",
        ])
    repair_plan = report.get("visual_repair_plan")
    if isinstance(repair_plan, dict):
        lines.extend([
            "", "## Visual Repair Order", "",
            f"- First concern: `{repair_plan['concern']}`",
            f"- Reason: {repair_plan['reason']}",
            f"- Next action: {repair_plan['next_action']}",
            "- Do not: " + "; ".join(repair_plan.get("blocked_actions") or []),
        ])
        evidence_scope = repair_plan.get("evidence_review_scope")
        if isinstance(evidence_scope, dict):
            lines.extend([
                f"- Word evidence scope: `{evidence_scope.get('status')}`; roles: " + ", ".join(f"`{role}`" for role in evidence_scope.get("roles") or []),
                f"- Matched atomic evidence units: `{evidence_scope.get('matched_units', 0)}`. {evidence_scope.get('reason', '')}",
            ])
            if evidence_scope.get("command_hint"):
                lines.append(f"- Readback command: `{evidence_scope['command_hint']}`")
    lines.extend(["", "## Blocked Actions", ""])
    lines.extend(f"- {item}" for item in report["blocked_actions"])
    lines.extend(["", "## Evidence", ""])
    for key, value in report["components"].items():
        lines.append(f"- `{key}`: `{value['status']}` - {value['reason']}")
    progress = report.get("mapping_progress")
    if isinstance(progress, dict):
        lines.extend(["", "## Atomic Mapping Progress", ""])
        lines.append(
            "- Required units: `{required_units}`; mapped/default/guidance/not-observable/unresolved/needs-decision: `{mapped}`/`{default}`/`{guidance}`/`{not_observable}`/`{unresolved}`/`{needs_decision}`.".format(**progress)
        )
    return "\n".join(lines) + "\n"


def assess(package: Path, compile_report: dict[str, Any] | None, compare_report: dict[str, Any] | None, validation: dict[str, Any] | None) -> dict[str, Any]:
    inventory = load(package / "source_inventory.json")
    ledger = load(package / "word_format_ledger.json")
    front_matter_confirmation = load(package / "front_matter_semantic_confirmation.json")
    system_triage = load(package / "system_format_triage.json")
    audit = load(package / "atomic_mapping_audit.json")
    coverage = load(package / "source_feature_coverage.json")
    has_word = word_source_present(inventory)
    components: dict[str, dict[str, Any]] = {}
    mapping_progress: dict[str, int] | None = None
    mapping_slice: dict[str, Any] | None = None
    sequence_confirmation_required = False
    word_source_unavailable = False
    system_triage_ready = True
    system_triage_audit_stale = False

    if has_word:
        ledger_coverage = ledger.get("coverage") if isinstance(ledger, dict) else None
        capture_complete = bool(isinstance(ledger_coverage, dict) and ledger_coverage.get("all_visible_text_units_captured") and not ledger_coverage.get("capture_limitations"))
        source_input = ledger.get("source_input") if isinstance(ledger, dict) else None
        source_unavailable = bool(isinstance(source_input, dict) and source_input.get("status") == "unavailable")
        word_source_unavailable = source_unavailable
        components["word_ledger"] = {
            "status": "unavailable" if source_unavailable else "complete" if capture_complete else "missing_or_incomplete",
            "reason": (
                str(source_input.get("reason") or "Word payload is unavailable.")
                if source_unavailable else
                "Every observable Word paragraph/run was captured." if capture_complete
                else "Build or repair word_format_ledger.json before mapping decisions."
            ),
        }
        sequence_review = ledger.get("front_matter_sequence_review") if isinstance(ledger, dict) else None
        sequence_review_requires_confirmation = bool(
            isinstance(sequence_review, dict) and sequence_review.get("requires_semantic_confirmation")
        )
        sequence_confirmation_errors = (
            front_matter_confirmation_errors(ledger, front_matter_confirmation)
            if sequence_review_requires_confirmation else []
        )
        sequence_confirmation_required = bool(sequence_review_requires_confirmation and sequence_confirmation_errors)
        components["front_matter_sequence"] = {
            "status": "not_available" if source_unavailable else "requires_semantic_confirmation" if sequence_confirmation_required else "complete",
            "reason": (
                str(source_input.get("reason") or "Word payload is unavailable; no front-matter sequence can be inferred.")
                if source_unavailable else
                "Resolve ordered front-matter roles before class generation or approval: " + "; ".join(sequence_confirmation_errors) + "."
                if sequence_confirmation_required
                else "Ledger-bound front-matter semantic confirmation is complete."
                if sequence_review_requires_confirmation
                else "No blocking front-matter role-order conflict was detected in the Word ledger."
            ),
        }
        triage_required = system_format_triage_required(ledger)
        triage_matches = bool(
            isinstance(system_triage, dict)
            and system_triage.get("schema_version") == "temp2tex.system-format-triage.v2"
            and system_triage.get("ledger_fingerprint") == ledger.get("evidence_fingerprint")
            and isinstance(system_triage.get("records"), list)
            and system_triage.get("records")
        )
        system_triage_ready = not triage_required or triage_matches
        system_triage_audit_stale = bool(
            triage_required
            and isinstance(audit, dict)
            and audit.get("system_triage_fingerprint") != system_triage_fingerprint(system_triage)
        )
        components["system_format_triage"] = {
            "status": "not_available" if source_unavailable else "complete" if system_triage_ready else "missing_or_invalid",
            "reason": (
                str(source_input.get("reason") or "Word payload is unavailable; no system-format triage can be completed.")
                if source_unavailable else
                "No Word text-grid, tab-stop, paragraph-break, character-effect/style, language/RTL, theme, or unmodeled-property evidence requires triage."
                if not triage_required else
                "System-format triage is bound to this Word ledger and ready for role-level decisions."
                if triage_matches else
                "Create or repair system_format_triage.json before starting atomic mapping; split disabled/non-rendering settings from active local effects."
            ),
        }
        matching_audit = bool(
            isinstance(ledger, dict)
            and isinstance(audit, dict)
            and audit.get("ledger_fingerprint") == ledger.get("evidence_fingerprint")
            and not system_triage_audit_stale
        )
        audit_complete = bool(isinstance(audit, dict) and audit.get("audit_complete") and matching_audit)
        fidelity_complete = bool(isinstance(audit, dict) and audit.get("fidelity_complete") and matching_audit)
        audit_summary = audit.get("summary") if isinstance(audit, dict) else None
        if isinstance(audit_summary, dict):
            mapping_progress = {
                key: int(audit_summary.get(key) or 0)
                for key in ("required_units", "mapped", "default", "guidance", "not_observable", "unresolved", "needs_decision")
            }
        # A mapping slice is a model work-order, so it must never bypass an
        # earlier source-interpretation phase that the same readiness report
        # marks as blocking. Otherwise a continuation agent receives mutually
        # inconsistent instructions: triage system evidence and map prose at
        # the same time.
        mapping_slice = (
            recommended_mapping_slice(audit, package)
            if capture_complete and not source_unavailable and not sequence_confirmation_required and system_triage_ready and not system_triage_audit_stale
            else None
        )
        components["atomic_mapping"] = {
            "status": "complete" if audit_complete else "pending_or_invalid",
            "reason": "Strict atomic audit is complete and bound to this ledger and child triage." if audit_complete else "Rerun strict atomic audit against the current system triage before mapping or calibration." if system_triage_audit_stale else "Review batches and rerun audit_atomic_mapping.py --strict before calibration.",
        }
        summary = coverage.get("summary") if isinstance(coverage, dict) else None
        coverage_complete = bool(isinstance(summary, dict) and summary.get("ledger_source_capture_complete") is True and summary.get("atomic_mapping_audit_complete") is True and summary.get("atomic_mapping_audit_matches_ledger") is True)
        components["coverage"] = {
            "status": "complete" if coverage_complete else "pending_refresh_or_gaps",
            "reason": "Coverage confirms the completed ledger-matched atomic audit." if coverage_complete else "Refresh source_feature_coverage.json after strict audit and resolve priority gaps.",
        }
    else:
        audit_complete = fidelity_complete = coverage_complete = True
        components["word_ledger"] = {"status": "not_applicable", "reason": "No inspectable Word source is recorded in this package."}
        components["front_matter_sequence"] = {"status": "not_applicable", "reason": "No Word front-matter sequence applies."}
        components["system_format_triage"] = {"status": "not_applicable", "reason": "No Word system-format evidence applies."}
        components["atomic_mapping"] = {"status": "not_applicable", "reason": "No Word paragraph/run audit applies."}
        components["coverage"] = {"status": "not_applicable", "reason": "No Word ledger coverage gate applies."}

    required = [
        "main.tex",
        "journal-template.cls",
        "references.bib",
        "template_spec.json",
        "format_gap_log.md",
        "HANDOFF_STATUS.md",
        "README.md",
    ]
    missing = [name for name in required if not (package / name).is_file()]
    components["package_files"] = {
        "status": "complete" if not missing else "missing",
        "reason": "Required editable package files are present." if not missing else f"Missing: {', '.join(missing)}.",
    }
    expected_validation_fingerprint = package_contract_fingerprint(package)
    if validation is None:
        components["package_validation"] = {"status": "pending", "reason": "Run validate_latex_package.py before ordinary handoff when tools are available."}
    elif validation.get("schema_version") != VALIDATION_SCHEMA_VERSION:
        components["package_validation"] = {
            "status": "stale",
            "reason": "Package validation report has an unsupported or missing schema_version; rerun validate_latex_package.py for the current contract.",
        }
    elif validation.get("package_contract_fingerprint") != expected_validation_fingerprint:
        components["package_validation"] = {
            "status": "stale",
            "reason": "Package validation report does not match the current editable package fingerprint; rerun validate_latex_package.py after the latest edits.",
        }
    else:
        components["package_validation"] = {"status": "complete" if validation.get("valid") else "failed", "reason": "Package validator passed." if validation.get("valid") else "; ".join(validation.get("errors") or ["Package validation failed."])}
    if compile_report is None:
        components["compile"] = {"status": "pending", "reason": "Compile main.tex when a TeX engine is available; otherwise retain reproducible commands in README."}
    else:
        components["compile"] = {"status": "complete" if compile_report.get("success") else "failed", "reason": "LaTeX compile succeeded." if compile_report.get("success") else "Repair fatal TeX errors before handoff."}

    comparable = False
    visual_pass = False
    repair_plan = visual_repair_plan(compare_report, audit, package, ledger, system_triage)
    if compare_report is None:
        components["visual_comparison"] = {"status": "pending", "reason": "No same-content PDF comparison was supplied."}
    else:
        layout = compare_report.get("layout_comparability") or {}
        comparable = str(layout.get("status") or "").lower() == "comparable" and bool(layout.get("semantic_comparable"))
        comparisons = compare_report.get("comparisons") or []
        issues = compare_report.get("issues") or []
        visual_pass = comparable and bool(comparisons) and not issues
        components["visual_comparison"] = {
            "status": "complete" if visual_pass else "not_comparable" if not comparable else "needs_repair",
            "reason": "Same-content PDF comparison is structurally and visually accepted." if visual_pass else "Repair fixture anchors before calibration." if not comparable else "Inspect source-backed layout differences; do not tune unrelated settings.",
        }

    evidence_ready = components["word_ledger"]["status"] in {"complete", "not_applicable"}
    mapping_ready = (
        components["atomic_mapping"]["status"] in {"complete", "not_applicable"}
        and components["coverage"]["status"] in {"complete", "not_applicable"}
        and components["front_matter_sequence"]["status"] in {"complete", "not_applicable"}
        and components["system_format_triage"]["status"] in {"complete", "not_applicable"}
    )
    package_contract_failed = components["package_files"]["status"] != "complete" or components["package_validation"]["status"] in {"failed", "stale"}
    package_ready = not package_contract_failed
    compile_ready = components["compile"]["status"] == "complete"
    checkpoint_status = "blocked"
    checkpoint_reason = "Build the evidence ledger and required editable package files before handing work to another model."
    if evidence_ready and components["package_files"]["status"] == "complete":
        if has_word and not mapping_ready:
            if sequence_confirmation_required:
                checkpoint_status = "ready_for_front_matter_confirmation"
                checkpoint_reason = "Resolve the blocking front-matter sequence from visible Word context before any atomic mapping batch."
            elif not system_triage_ready:
                checkpoint_status = "ready_for_system_format_triage"
                checkpoint_reason = "Create or repair the ledger-matched system-format triage before selecting an ordinary Word mapping batch."
            elif system_triage_audit_stale:
                checkpoint_status = "ready_for_system_triage_audit_refresh"
                checkpoint_reason = "The child triage changed after its atomic audit; rerun strict audit before selecting another mapping batch."
            else:
                checkpoint_status = "ready_for_next_mapping_batch"
                checkpoint_reason = "The editable package and source ledger are present; continue only with the next bounded atomic-mapping batch and preserve the strict-audit gate."
        elif not compile_ready:
            checkpoint_status = "ready_for_local_compile_verification"
            checkpoint_reason = "Source mapping is complete enough to continue; compile locally or retain the exact unavailable-tool command."
        else:
            checkpoint_status = "ready_for_next_verification_phase"
            checkpoint_reason = "The package has passed the current structural gate; follow the reported phase rather than restarting source extraction."
    if word_source_unavailable:
        phase = "word_source_recovery"
        next_actions = [
            "Preserve the unavailable original download and obtain a valid official Word payload; do not retry the same malformed file as a template source.",
            "Until a replacement is available, use official PDF/web guidance, record Word-specific gaps, and keep the editable package explicitly default-backed rather than source-faithful.",
        ]
    elif not evidence_ready:
        phase = "evidence_capture"
        next_actions = ["Build or repair the Word evidence ledger; preserve original-source provenance."]
    elif sequence_confirmation_required:
        phase = "front_matter_semantic_confirmation"
        next_actions = [
            "Complete front_matter_semantic_confirmation.json from visible Word context, then rerun readiness before mapping or layout calibration.",
            "Keep article type, manuscript title, author, affiliation, editorial metadata, and bilingual/subtitle fields as separate editable interfaces.",
        ]
    elif not system_triage_ready:
        phase = "system_format_triage"
        next_actions = [
            "Create or repair system_format_triage.json from the current Word ledger before atomic mapping.",
            "Split source-disabled/non-rendering settings, unused style scaffolds, instruction examples, and active role-local visual effects; do not activate a global policy from aggregate Word evidence.",
        ]
    elif system_triage_audit_stale:
        phase = "system_triage_audit_refresh"
        next_actions = [
            "Rerun audit_atomic_mapping.py --strict with the current system_format_triage.json before selecting another mapping batch or calibrating layout.",
            "Do not reuse a ledger-matched but child-stale audit result for package validation, coverage refresh, or fidelity claims.",
        ]
    elif not mapping_ready:
        phase = "atomic_mapping"
        next_actions = []
        if mapping_slice:
            next_actions.append(
                "Review the recommended semantic mapping slice first; generate its fingerprint-bound batch draft, merge only final dispositions, then refresh readiness."
            )
        next_actions.append("Review atomic mapping batches, merge only fingerprint-bound decisions, rerun strict atomic audit, then refresh coverage.")
    elif package_contract_failed:
        phase = "package_contract"
        next_actions = ["Repair package contract errors and rerun validate_latex_package.py."]
    elif not compile_ready:
        phase = "compile_verification"
        next_actions = ["Compile main.tex or record the unavailable local engine and reproducible command in README."]
    elif compare_report is None:
        phase = "optional_visual_verification"
        next_actions = ["Deliver the editable package with pending visual-verification commands, or create a same-content reference pair when rendering is available."]
    elif not comparable:
        phase = "same_content_fixture_repair"
        next_actions = ["Repair the same-content fixture and unique anchors before any layout calibration."]
    elif not visual_pass:
        phase = "source_backed_visual_repair"
        next_actions = [
            str(repair_plan.get("next_action"))
            if isinstance(repair_plan, dict)
            else "Repair one source-backed layout difference at a time; use render probes only under the promotion gate."
        ]
    else:
        phase = "verified_handoff"
        next_actions = ["Deliver the editable package and retain comparison artifacts with the evidence record."]

    blocked = []
    if not mapping_ready:
        blocked.extend(["PDF micro-calibration", "render-probe promotion", "strict regression pass", "full Word-format fidelity claim"])
    elif not compile_ready:
        blocked.extend(["PDF comparison claim", "strict regression pass"])
    elif not comparable:
        blocked.extend(["layout calibration", "render-probe promotion", "visual-match claim"])
    elif not visual_pass:
        blocked.append("render-verified promotion without a successful candidate comparison")
        if isinstance(repair_plan, dict):
            blocked.extend(str(item) for item in repair_plan.get("blocked_actions") or [])
    ordinary_status = "ready" if package_ready and components["compile"]["status"] != "failed" and mapping_ready else "blocked"
    if ordinary_status == "ready" and (not compile_ready or components["package_validation"]["status"] == "pending"):
        ordinary_status = "ready_with_pending_local_verification"
    full_status = "eligible" if fidelity_complete and coverage_complete and compile_ready and visual_pass else "not_yet_eligible"
    return {
        "schema_version": SCHEMA_VERSION,
        "package": str(package),
        "phase": phase,
        "components": components,
        "mapping_progress": mapping_progress,
        "recommended_mapping_slice": mapping_slice,
        "visual_repair_plan": repair_plan,
        "checkpoint_handoff": {
            "status": checkpoint_status,
            "reason": checkpoint_reason,
            "requires": [
                "preserve source_inventory.json, word_format_ledger.json, system_format_triage.json, decisions, audit, and readiness artifacts",
                "state the current phase and the next bounded action",
                "preserve the recommended_mapping_slice when one is present; it is a work-order hint, not a completion claim",
                "do not upgrade a checkpoint into a Word-format fidelity claim",
            ],
        },
        "ordinary_handoff": {"status": ordinary_status, "requires": ["complete Word mapping when a Word source exists", "valid package contract", "compile result or explicit unavailable-tool handoff"]},
        "full_source_fidelity": {"status": full_status, "requires": ["ledger-matched strict atomic audit", "coverage refresh", "successful compile", "comparable same-content visual verification"]},
        "next_actions": next_actions,
        "blocked_actions": blocked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", help="Temp2TeX package directory")
    parser.add_argument("--compile-report", help="Optional compile_report.json")
    parser.add_argument("--compare-report", help="Optional render_compare_report.json")
    parser.add_argument("--package-validation", help="Optional package_validation.json")
    parser.add_argument("--output", required=True, help="Output conversion_readiness.json")
    parser.add_argument("--markdown-output", help="Optional conversion_readiness.md")
    args = parser.parse_args()
    package = Path(args.package).resolve()
    report = assess(package, load(Path(args.compile_report)) if args.compile_report else load(package / "compile_report.json"), load(Path(args.compare_report)) if args.compare_report else None, load(Path(args.package_validation)) if args.package_validation else load(package / "package_validation.json"))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown_output:
        markdown_output = Path(args.markdown_output)
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(markdown(report), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
