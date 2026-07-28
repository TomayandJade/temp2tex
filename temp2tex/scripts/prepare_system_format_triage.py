#!/usr/bin/env python3
"""Prepare a non-binding system-format review queue from a Word format ledger.

The queue helps an agent separate active visible effects from explicit Word
defaults and non-rendering metadata. It intentionally does not write atomic
mapping decisions or mark source fidelity complete.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "temp2tex.system-format-triage.v2"
FINAL_CHILD_STATUSES = {"mapped", "default", "unresolved", "not_observable", "guidance"}

# Work-order ranks only. They deliberately do not assign a disposition or
# change a persisted triage child: models still have to review every item.
REVIEW_PRIORITY_LABELS = {
    0: "critical",
    1: "high",
    2: "normal",
    3: "deferred_instruction",
    4: "deferred_nonrendering",
}

SEMANTIC_STYLE_HINTS = {
    "equation", "equations", "figure", "figures", "table", "tables",
    "caption", "heading", "title", "abstract", "keyword", "reference",
    "appendix", "author", "affiliation",
}

INSTRUCTION_TEXT_HINTS = {
    "example", "examples", "template", "instruction", "instructions",
    "should", "please", "authors", "formatting specifications",
}


def as_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def source_item(objects: dict[str, Any], key: str) -> Any:
    return objects.get(key) if isinstance(objects, dict) else None


def sample_locator(sample: dict[str, Any]) -> dict[str, Any]:
    """Keep only stable source coordinates needed for a later human/LLM review."""
    return {
        key: sample.get(key)
        for key in (
            "scope", "part", "table_index", "row_index", "column_index",
            "paragraph_index", "style_id", "style_name", "start", "end",
        )
        if sample.get(key) is not None
    }


def source_unit_id(ledger: dict[str, Any], sample: dict[str, Any]) -> str:
    """Link a system sample to its ordinary paragraph/run audit unit when safe.

    System evidence is supplementary: it must never replace the primary run or
    paragraph disposition.  A link lets the audit prove that a theme/effect
    record was reviewed with the role that actually renders it.
    """
    scope = str(sample.get("scope") or "")
    paragraph_index = sample.get("paragraph_index")
    start = sample.get("start")
    end = sample.get("end")
    if scope in {"table_cell", "table_header"}:
        # OOXML object samples use a table-local paragraph coordinate, which
        # can collide with a body paragraph index. Resolve table-cell text
        # before considering any body index, and leave ambiguous cells
        # unlinked rather than creating a false ordinary-evidence relation.
        text = str(sample.get("text") or "")
        if text:
            matches = [
                (paragraph, span)
                for paragraph in as_list(ledger.get("paragraphs"))
                if paragraph.get("in_table_cell")
                for span in as_list(paragraph.get("format_spans"))
                if str(span.get("text") or "") == text and text.strip()
            ]
            if len(matches) == 1:
                return str(matches[0][1].get("evidence_id") or "")
        return ""
    if isinstance(paragraph_index, int):
        for paragraph in as_list(ledger.get("paragraphs")):
            if paragraph.get("index") != paragraph_index:
                continue
            if isinstance(start, int) and isinstance(end, int):
                for span in as_list(paragraph.get("format_spans")):
                    if span.get("start") == start and span.get("end") == end:
                        # Whitespace-only spans are intentionally absent from
                        # the ordinary atomic queue. Their font/theme evidence
                        # belongs to the visible parent paragraph instead.
                        if str(span.get("text") or "").strip():
                            return str(span.get("evidence_id") or "")
            return str(paragraph.get("evidence_id") or "")
    part = str(sample.get("part") or "")
    if scope in {"header", "footer"} and part:
        for paragraph in as_list(ledger.get("ancillary_units")):
            context = as_dict(paragraph.get("context"))
            if str(context.get("part") or "") != part:
                continue
            if isinstance(start, int) and isinstance(end, int):
                for span in as_list(paragraph.get("format_spans")):
                    if span.get("start") == start and span.get("end") == end:
                        if str(span.get("text") or "").strip():
                            return str(span.get("evidence_id") or "")
                return str(paragraph.get("evidence_id") or "")
    return ""


def ordinary_evidence_index(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index source-local audit metadata without treating it as a decision."""
    indexed: dict[str, dict[str, Any]] = {}
    for paragraph in as_list(ledger.get("paragraphs")) + as_list(ledger.get("ancillary_units")):
        paragraph_id = str(paragraph.get("evidence_id") or "")
        if paragraph_id:
            indexed[paragraph_id] = paragraph
        for span in as_list(paragraph.get("format_spans")):
            span_id = str(span.get("evidence_id") or "")
            if span_id:
                indexed[span_id] = paragraph
    return indexed


def source_position(child: dict[str, Any]) -> int:
    """Return a deterministic source position for same-priority review cards."""
    locator = as_dict(child.get("source_locator"))
    paragraph_index = locator.get("paragraph_index")
    if isinstance(paragraph_index, int):
        return paragraph_index
    section_index = locator.get("section_index")
    if isinstance(section_index, int):
        return section_index
    return 1_000_000


def child_review_priority(
    record: dict[str, Any],
    child: dict[str, Any],
    evidence_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Give an explainable, non-binding priority to one pending review card.

    The queue must not let long template instructions bury equations, captions,
    tables, and other source-backed visual roles. This uses only existing
    evidence and deliberately labels heuristic instruction cues as *likely*,
    never as a final `guidance` disposition.
    """
    system = str(record.get("system") or "")
    route = str(record.get("suggested_route") or "")
    locator = as_dict(child.get("source_locator"))
    source_text = str(child.get("source_text") or "").strip()
    linked_id = str(child.get("source_unit_evidence_id") or "")
    ordinary = evidence_index.get(linked_id, {})
    roles = [str(item.get("role") or "") for item in as_list(ordinary.get("role_candidates"))]
    style_tokens = " ".join(
        str(locator.get(key) or "").lower()
        for key in ("style_id", "style_name")
    )
    text_lower = source_text.lower()
    semantic_style = any(hint in style_tokens for hint in SEMANTIC_STYLE_HINTS)
    instruction_role = "guidance.instruction" in roles
    structured_role = any(role and role not in {"body.paragraph", "guidance.instruction"} for role in roles)
    likely_instruction = any(hint in text_lower for hint in INSTRUCTION_TEXT_HINTS)
    named_style_only = as_dict(child.get("observed_value")).get("evidence_kind") == "named_style_rule"

    if route in {"non_rendering_default_candidate", "source_disabled_default_candidate"}:
        rank, reason = 4, "The system route is explicitly non-rendering or source-disabled; retain it for audit after visible layout roles."
    elif system == "page.text_grid":
        rank, reason = 0, "Text-grid evidence can affect page geometry and line flow; inspect it before local cosmetic effects."
    elif instruction_role:
        rank, reason = 3, "Its linked ordinary evidence is classified as editorial guidance; keep it pending, but review visible manuscript roles first."
    elif structured_role:
        if system in {"document.theme", "run.script_language"}:
            rank, reason = 1, "Its linked ordinary evidence has a source-classified semantic role, but this theme/language alias follows direct geometry and local effects."
        else:
            rank, reason = 0, "Its linked ordinary evidence has a source-classified semantic role, so it can affect a structural template feature."
    elif semantic_style:
        rank, reason = 0, "Its Word style name identifies a semantic layout role (for example equation, table, caption, or heading)."
    elif linked_id and not named_style_only and source_text:
        if system in {"document.theme", "run.script_language"}:
            rank, reason = 2, "It has linked visible source text, but theme/language aliases follow direct geometry and exercised local effects."
        else:
            rank, reason = 1, "It has linked visible source text and an ordinary audit unit, so it can affect an exercised role."
    elif likely_instruction:
        rank, reason = 3, "Its wording is likely template guidance or an example; this is a review-order hint, not a final guidance decision."
    elif named_style_only:
        rank, reason = 2, "It is a named-style rule without a confirmed visible exercise; review it after source-local visible effects."
    else:
        rank, reason = 2, "It needs bounded role review but has no higher-impact source-local signal."

    return {
        "rank": rank,
        "label": REVIEW_PRIORITY_LABELS[rank],
        "reason": reason,
        # Table-object samples use table-local paragraph coordinates. Prefer
        # the linked ordinary unit's document-wide index when it is available.
        "source_position": ordinary.get("index") if isinstance(ordinary.get("index"), int) else source_position(child),
    }


def child_record(
    system: str,
    evidence_id: str,
    ordinal: int,
    sample: dict[str, Any],
    ledger: dict[str, Any],
) -> dict[str, Any]:
    """Create one deliberately pending, evidence-bounded review item."""
    text = str(sample.get("text") or "")
    observed_value = (
        sample.get("effects")
        or sample.get("tab_stops")
        or sample.get("theme_color")
        or sample.get("theme_font")
        or sample.get("attributes")
        or {}
    )
    return {
        "child_id": f"{evidence_id}.sample-{ordinal:04d}",
        "status": "pending",
        "source_unit_evidence_id": source_unit_id(ledger, sample),
        "source_locator": sample_locator(sample),
        "source_text": text[:500],
        "observed_value": observed_value,
        "reason": "",
        "guidance_kind": "",
        "latex_owner": "",
        "latex_file": "",
        "latex_token": "",
        "verification": "",
    }


def aggregate_child_record(
    evidence_id: str,
    ordinal: int,
    source_text: str,
    observed_value: object,
    locator: dict[str, Any],
    source_unit_evidence_id: str = "",
) -> dict[str, Any]:
    """Create a reviewable child for a bounded system-evidence group.

    Some Word aggregates are intentionally grouped by section or named style,
    rather than represented by an ordinary visible run. They still need a child
    record so the strict audit can distinguish a documented default from an
    active role-local effect instead of leaving a childless system aggregate.
    """
    return {
        "child_id": f"{evidence_id}.sample-{ordinal:04d}",
        "status": "pending",
        "source_unit_evidence_id": source_unit_evidence_id,
        "source_locator": locator,
        "source_text": source_text[:500],
        "observed_value": observed_value,
        "reason": "",
        "guidance_kind": "",
        "latex_owner": "",
        "latex_file": "",
        "latex_token": "",
        "verification": "",
    }


def grid_children(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn text-grid sections and bounded local overrides into audit units."""
    evidence_id = "page.text-grid.system"
    children: list[dict[str, Any]] = []
    for section in as_list(evidence.get("sections")):
        section_index = section.get("section_index")
        children.append(aggregate_child_record(
            evidence_id,
            len(children) + 1,
            f"Word section {section_index if section_index is not None else 'unknown'} text grid",
            as_dict(section.get("text_grid")),
            {"section_index": section_index} if section_index is not None else {},
        ))
    for collection, label in (("paragraphs", "paragraph"), ("styles", "named style"), ("run_groups", "run group")):
        for item in as_list(evidence.get(collection)):
            style_id = item.get("style_id")
            style_name = item.get("style_name")
            examples = as_list(item.get("examples"))
            example = examples[0] if examples else {}
            source_text = str(example.get("text") or "").strip()
            if not source_text:
                identity = " / ".join(str(value) for value in (style_id, style_name) if value)
                source_text = f"Word {label} {identity or 'with text-grid properties'}"
            observed = {
                "direct_properties": as_dict(item.get("direct_properties")),
                "effective_properties": as_dict(item.get("effective_properties")),
            }
            locator = {
                key: value
                for key, value in {
                    "style_id": style_id,
                    "style_name": style_name,
                    "paragraph_index": example.get("paragraph_index"),
                    "scope": example.get("scope"),
                    "part": example.get("part"),
                }.items()
                if value is not None
            }
            children.append(aggregate_child_record(
                evidence_id,
                len(children) + 1,
                source_text,
                observed,
                locator,
            ))
    return children


def script_language_children(evidence: dict[str, Any], ledger: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep every bounded language review group visible to the strict audit."""
    evidence_id = "run.script-language.system"
    children: list[dict[str, Any]] = []
    for group in as_list(evidence.get("review_groups")):
        examples = as_list(group.get("examples"))
        example = examples[0] if examples else {}
        style_id = group.get("style_id")
        style_name = group.get("style_name")
        source_text = str(example.get("text") or "").strip()
        if not source_text:
            identity = " / ".join(str(value) for value in (style_id, style_name) if value)
            source_text = f"Word script/language review group {identity or 'without visible example'}"
        observed = {
            "evidence_kind": group.get("evidence_kind"),
            "direct_properties": as_dict(group.get("direct_properties")),
            "effective_properties": as_dict(group.get("effective_properties")),
            "occurrence_count": group.get("occurrence_count"),
        }
        locator = {
            key: value
            for key, value in {
                "style_id": style_id,
                "style_name": style_name,
                "style_type": group.get("style_type"),
                "paragraph_index": example.get("paragraph_index"),
                "scope": example.get("scope"),
                "part": example.get("part"),
                "start": example.get("start"),
                "end": example.get("end"),
            }.items()
            if value is not None
        }
        children.append(aggregate_child_record(
            evidence_id,
            len(children) + 1,
            source_text,
            observed,
            locator,
            source_unit_id(ledger, example) if example else "",
        ))
    return children


def break_policy_children(evidence: dict[str, Any], ledger: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep each bounded hyphenation/wrap policy group independently auditable."""
    evidence_id = "paragraph.break-policy.system"
    children: list[dict[str, Any]] = []
    for group in as_list(evidence.get("review_groups")):
        examples = as_list(group.get("examples"))
        example = examples[0] if examples else {}
        style_id = group.get("style_id")
        style_name = group.get("style_name")
        source_text = str(example.get("text") or "").strip()
        if not source_text:
            identity = " / ".join(str(value) for value in (style_id, style_name) if value)
            source_text = f"Word paragraph break-policy review group {identity or 'without visible example'}"
        observed = {
            "evidence_kind": group.get("evidence_kind"),
            "direct_properties": as_dict(group.get("direct_properties")),
            "effective_properties": as_dict(group.get("effective_properties")),
            "occurrence_count": group.get("occurrence_count"),
        }
        locator = {
            key: value
            for key, value in {
                "style_id": style_id,
                "style_name": style_name,
                "style_type": group.get("style_type"),
                "paragraph_index": example.get("paragraph_index"),
                "scope": example.get("scope"),
                "part": example.get("part"),
            }.items()
            if value is not None
        }
        children.append(aggregate_child_record(
            evidence_id,
            len(children) + 1,
            source_text,
            observed,
            locator,
            source_unit_id(ledger, example) if example else "",
        ))
    return children


def grid_route(evidence: dict[str, Any]) -> tuple[str, str]:
    local_values: list[bool] = []
    for item in as_list(evidence.get("paragraphs")) + as_list(evidence.get("styles")):
        value = as_dict(item.get("direct_properties")).get("snap_to_grid")
        if isinstance(value, bool):
            local_values.append(value)
    for item in as_list(evidence.get("run_groups")):
        value = as_dict(item.get("effective_properties")).get("snap_to_grid")
        if isinstance(value, bool):
            local_values.append(value)
    if local_values and not any(local_values):
        return (
            "source_disabled_default_candidate",
            "Every captured local snap-to-grid value is false; retain the explicit opt-out and do not enable a global LaTeX grid.",
        )
    return (
        "role_local_render_check",
        "A document grid or active local override may affect line geometry; map confirmed roles only after same-content rendering.",
    )


def effects_route(samples: list[dict[str, Any]]) -> tuple[str, str]:
    visible = [item for item in samples if item.get("evidence_kind") != "named_style_rule"]
    named = [item for item in samples if item.get("evidence_kind") == "named_style_rule"]
    if visible and named:
        return (
            "split_required",
            "Visible spans and unexercised named style rules cannot share one disposition; split by span or style before atomic mapping.",
        )
    if visible:
        return (
            "role_local_render_check",
            "Map each visible effect span only in its confirmed role; glyph-scale, fit-text, and spacing effects require role-matched rendering.",
        )
    return (
        "unused_style_candidate",
        "Only named style rules were observed. Record template-scaffold or not-observable evidence instead of changing document defaults.",
    )


def language_route(evidence: dict[str, Any]) -> tuple[str, str]:
    relevance = str(evidence.get("relevance") or "")
    if relevance in {"observed_default_language_or_disabled_complex_policy", "not_detected"}:
        return (
            "non_rendering_default_candidate",
            "Only inherited/default language or disabled complex-script evidence was found; do not activate a global language or RTL policy from it.",
        )
    return (
        "role_local_render_check",
        "Non-default language, complex-script, or RTL evidence needs a source-text, font, engine, and local direction decision before rendering.",
    )


def break_policy_route(evidence: dict[str, Any]) -> tuple[str, str]:
    groups = as_list(evidence.get("review_groups"))
    visible = [item for item in groups if item.get("evidence_kind") != "named_style_rule"]
    named = [item for item in groups if item.get("evidence_kind") == "named_style_rule"]
    if visible and named:
        return (
            "split_required",
            "Visible paragraph policies and unexercised named style rules require separate child decisions; do not turn a Word hyphenation or wrap setting into a document-wide TeX policy.",
        )
    if visible:
        return (
            "role_local_render_check",
            "A visible hyphenation or word-wrap policy must remain local to its source role and receive a same-content line-break and page-flow check before activation.",
        )
    return (
        "unused_style_candidate",
        "Only named style paragraph policies were observed. Record source evidence without changing document-wide TeX hyphenation or wrapping.",
    )


def theme_route(samples: list[dict[str, Any]]) -> tuple[str, str]:
    visible = [item for item in samples if item.get("evidence_kind") != "named_style_rule"]
    named = [item for item in samples if item.get("evidence_kind") == "named_style_rule"]
    if visible and named:
        return (
            "split_required",
            "Visible theme uses and named-style aliases require separate role decisions; the theme palette alone is not a document-wide font or colour rule.",
        )
    if visible:
        return (
            "role_local_render_check",
            "Resolve only the aliases used by visible spans, preserving the local role and tint/shade where present.",
        )
    return (
        "unused_style_candidate",
        "Only named-style theme aliases were observed. Keep them as source evidence until a visible role exercises them.",
    )


def tab_stop_route(samples: list[dict[str, Any]]) -> tuple[str, str]:
    if len({str(item.get("style_id") or "") for item in samples}) > 1:
        return (
            "split_required",
            "Visible tab stops occur in more than one Word role. Review equation alignment and editorial/reference examples separately; never install a document-wide tab default.",
        )
    return (
        "role_local_render_check",
        "Map a tab stop only through its confirmed local role and verify its line geometry on a same-content render.",
    )


def property_route(node: str, samples: list[dict[str, Any]]) -> tuple[str, str]:
    values = {str(as_dict(sample.get("attributes")).get("val") or "") for sample in samples}
    if node == "noProof":
        return (
            "non_rendering_default_candidate",
            "w:noProof controls Word proofing rather than rendered PDF geometry.",
        )
    if node in {"adjustRightInd", "mirrorIndents"} and values <= {"0", "false", "off", ""}:
        return (
            "source_disabled_default_candidate",
            "The observed OOXML value explicitly disables the Word behavior; record the default without adding a LaTeX geometry change.",
        )
    return (
        "property_level_review_required",
        "This property may affect a visible role or its rendering behavior. Determine its OOXML semantics and source role before mapping or closing it.",
    )


def record(
    system: str,
    evidence_id: str,
    route: str,
    reason: str,
    summary: dict[str, Any],
    questions: list[str],
    children: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "system": system,
        "source_evidence_id": evidence_id,
        "status": "pending_model_decision",
        "suggested_route": route,
        "reason": reason,
        "summary": summary,
        "child_count": len(children),
        "children": children,
        "required_questions": questions,
        "decision_rule": "This is non-binding. Split mixed samples, then write final evidence-bound dispositions in atomic_mapping_decisions.json.",
    }


def build_triage(ledger: dict[str, Any]) -> dict[str, Any]:
    objects = as_dict(ledger.get("objects"))
    records: list[dict[str, Any]] = []

    grid = as_dict(source_item(objects, "text_grid_evidence"))
    if grid.get("present"):
        route, reason = grid_route(grid)
        records.append(record(
            "page.text_grid", "page.text-grid.system", route, reason,
            {
                "sections": len(as_list(grid.get("sections"))),
                "paragraph_overrides": len(as_list(grid.get("paragraphs"))),
                "style_overrides": len(as_list(grid.get("styles"))),
                "run_groups": len(as_list(grid.get("run_groups"))),
            },
            ["Does any visible manuscript role actively use a grid?", "Are all local snap-to-grid values explicit opt-outs?", "Is the source Chinese or mixed-language?"],
            grid_children(grid),
        ))

    tab_stops = as_list(source_item(objects, "tab_stop_evidence"))
    if tab_stops:
        route, reason = tab_stop_route(tab_stops)
        records.append(record(
            "paragraph.tab_stops", "paragraph.tab-stops.system", route, reason,
            {"visible_paragraphs": len(tab_stops), "style_ids": sorted({str(item.get("style_id") or "") for item in tab_stops})},
            ["Which tab-stop samples are live manuscript roles versus editorial examples?", "Does each live role need tab alignment or a semantic LaTeX environment?", "Has the local line geometry been checked on same-content output?"],
            [child_record("paragraph.tab_stops", "paragraph.tab-stops.system", index, item, ledger) for index, item in enumerate(tab_stops, 1)],
        ))

    effects = as_list(source_item(objects, "character_effect_evidence"))
    if effects:
        route, reason = effects_route(effects)
        records.append(record(
            "run.character_effects", "run.character-effects.system", route, reason,
            {
                "visible_spans": sum(item.get("evidence_kind") != "named_style_rule" for item in effects),
                "named_style_rules": sum(item.get("evidence_kind") == "named_style_rule" for item in effects),
                "sample_count": len(effects),
            },
            ["Which samples are manuscript content versus instruction/example text?", "Which visible span owns each effect?", "Does any local effect require same-content glyph rendering?"],
            [child_record("run.character_effects", "run.character-effects.system", index, item, ledger) for index, item in enumerate(effects, 1)],
        ))

    styles = as_list(source_item(objects, "character_style_evidence"))
    if styles:
        unresolved = [item for item in styles if not item.get("character_style_resolved")]
        records.append(record(
            "run.character_styles", "run.character-styles.system",
            "role_local_mapping" if not unresolved else "role_local_resolution_required",
            "Visible Word rStyle references are local spans. Resolve each style before treating its effective font, colour, or underline as a LaTeX rule.",
            {"visible_spans": len(styles), "unresolved_style_ids": sorted({str(item.get("character_style_id")) for item in unresolved})},
            ["What is the exact local span and source role?", "Is the referenced style resolved?", "Is a link target externally safe and present?"],
            [child_record("run.character_styles", "run.character-styles.system", index, item, ledger) for index, item in enumerate(styles, 1)],
        ))

    language = as_dict(source_item(objects, "script_language_evidence"))
    if language.get("observed"):
        route, reason = language_route(language)
        records.append(record(
            "run.script_language", "run.script-language.system", route, reason,
            {"relevance": language.get("relevance"), "raw_occurrence_count": language.get("raw_occurrence_count"), "review_groups": len(as_list(language.get("review_groups")))},
            ["Does the source text itself contain a non-Latin or RTL role?", "Is a value inherited metadata rather than active local behavior?", "Which engine/font/direction decision is required by the actual role?"],
            script_language_children(language, ledger),
        ))

    break_policy = as_dict(source_item(objects, "paragraph_break_policy_evidence"))
    if break_policy.get("observed"):
        route, reason = break_policy_route(break_policy)
        records.append(record(
            "paragraph.break_policy", "paragraph.break-policy.system", route, reason,
            {"relevance": break_policy.get("relevance"), "raw_occurrence_count": break_policy.get("raw_occurrence_count"), "review_groups": len(as_list(break_policy.get("review_groups")))},
            ["Does this child describe visible manuscript flow or an unexercised named style?", "Is automatic hyphenation or wrapping explicitly disabled, and at what role scope?", "Has any active local policy been checked for same-content line breaks and pagination?"],
            break_policy_children(break_policy, ledger),
        ))

    theme = as_dict(source_item(objects, "theme_format_evidence"))
    samples = as_list(theme.get("samples"))
    if theme.get("present") and samples:
        route, reason = theme_route(samples)
        records.append(record(
            "document.theme", "document.theme.system", route, reason,
            {"visible_uses": sum(item.get("evidence_kind") != "named_style_rule" for item in samples), "named_style_rules": sum(item.get("evidence_kind") == "named_style_rule" for item in samples)},
            ["Which aliases occur in a visible source role?", "Does a tint/shade alter the final RGB value?", "Is the font/colour role-local rather than a global body default?"],
            [child_record("document.theme", "document.theme.system", index, item, ledger) for index, item in enumerate(samples, 1)],
        ))

    unmodeled = as_dict(source_item(objects, "unmodeled_format_properties"))
    for item in as_list(unmodeled.get("properties")):
        node = str(item.get("node") or "unknown")
        samples = as_list(item.get("samples"))
        route, reason = property_route(node, samples)
        records.append(record(
            "word.unmodeled_format", f"word.unmodeled-format-properties.{node}", route, reason,
            {"node": node, "scope": item.get("scope"), "occurrence_count": item.get("count"), "sample_attributes": [as_dict(sample.get("attributes")) for sample in samples[:5]]},
            ["Does this node affect rendered output?", "Is the source value explicitly disabled?", "If active, which visible role owns it?"],
            [child_record("word.unmodeled_format", f"word.unmodeled-format-properties.{node}", index, sample, ledger) for index, sample in enumerate(samples, 1)],
        ))

    return {
        "schema_version": SCHEMA_VERSION,
        "purpose": "System-format review queue. Every child remains pending until it has a role-local final disposition; this file alone never approves a LaTeX fidelity claim.",
        "source": ledger.get("source"),
        "ledger_fingerprint": ledger.get("evidence_fingerprint"),
        "records": records,
        "next_action": "Review every child record. Link active visible effects to the ordinary paragraph/run mapping that owns them; keep unlinked or mixed evidence unresolved rather than closing its system aggregate.",
    }


def refresh_pending_source_fields(existing: dict[str, Any], ledger: dict[str, Any]) -> int:
    """Refresh producer-owned fields for pending children from the current ledger.

    This supports helper corrections such as a table-local coordinate collision
    without rewriting a model's final disposition. A final child with changed
    source fields is intentionally rejected: its evidence chain needs an
    explicit rebuild/review rather than an invisible migration.
    """
    fresh = build_triage(ledger)
    fresh_records = {
        str(record.get("source_evidence_id") or ""): record
        for record in as_list(fresh.get("records"))
    }
    existing_records = {
        str(record.get("source_evidence_id") or ""): record
        for record in as_list(existing.get("records"))
    }
    if set(existing_records) != set(fresh_records):
        raise ValueError("--existing has a different system-evidence record set; rebuild the triage queue before continuing.")

    source_keys = ("source_unit_evidence_id", "source_locator", "source_text", "observed_value")
    changed_pending = 0
    changed_final: list[str] = []
    for evidence_id, existing_record in existing_records.items():
        fresh_record = fresh_records[evidence_id]
        existing_children = {
            str(child.get("child_id") or ""): child
            for child in as_list(existing_record.get("children"))
        }
        fresh_children = {
            str(child.get("child_id") or ""): child
            for child in as_list(fresh_record.get("children"))
        }
        if set(existing_children) != set(fresh_children):
            raise ValueError(f"--existing child set differs for {evidence_id}; rebuild the triage queue before continuing.")
        for child_id, existing_child in existing_children.items():
            fresh_child = fresh_children[child_id]
            changed = any(existing_child.get(key) != fresh_child.get(key) for key in source_keys)
            if not changed:
                continue
            status = str(existing_child.get("status") or "pending").strip().lower()
            if status != "pending":
                changed_final.append(child_id)
                continue
            for key in source_keys:
                existing_child[key] = fresh_child.get(key)
            changed_pending += 1
    if changed_final:
        sample = ", ".join(changed_final[:5])
        suffix = " ..." if len(changed_final) > 5 else ""
        raise ValueError(
            "--existing contains final child decisions whose producer-owned source fields changed "
            f"({sample}{suffix}); rebuild/review those decisions explicitly instead of rewriting their evidence links."
        )
    if changed_pending:
        existing["source_refresh"] = {
            "method": "refresh_pending_producer_fields_from_current_ledger",
            "refreshed_pending_children": changed_pending,
            "warning": "Only pending child source fields were refreshed. Final child decisions were not rewritten.",
        }
    return changed_pending


def select_review_children(
    triage: dict[str, Any],
    ledger: dict[str, Any],
    systems: set[str] | None,
    pending_only: bool,
    review_order: str,
) -> list[dict[str, Any]]:
    """Flatten selected evidence into a deterministic model-review worklist."""
    selected: list[dict[str, Any]] = []
    evidence_index = ordinary_evidence_index(ledger)
    for record in as_list(triage.get("records")):
        system = str(record.get("system") or "")
        if systems and system not in systems:
            continue
        for child in as_list(record.get("children")):
            status = str(child.get("status") or "pending").strip().lower()
            if pending_only and status != "pending":
                continue
            selected.append({
                "record": record,
                "child": child,
                "review_priority": child_review_priority(record, child, evidence_index),
                "source_order": len(selected),
            })
    if review_order == "priority":
        def priority_sort_key(item: dict[str, Any]) -> tuple[int, int, str, str]:
            priority = as_dict(item.get("review_priority"))
            rank = priority.get("rank")
            position = priority.get("source_position")
            return (
                rank if isinstance(rank, int) else 9,
                position if isinstance(position, int) else 1_000_000,
                str(as_dict(item.get("record")).get("source_evidence_id") or ""),
                str(as_dict(item.get("child")).get("child_id") or ""),
            )
        selected.sort(key=priority_sort_key)
    return selected


def markdown(
    triage: dict[str, Any],
    review_children: list[dict[str, Any]] | None = None,
    batch: dict[str, Any] | None = None,
    systems: set[str] | None = None,
    pending_only: bool = False,
    review_order: str = "priority",
) -> str:
    lines = [
        "# System-Format Triage Queue",
        "",
        "This queue separates active visual effects from source-disabled, non-rendering, unused-style, and unresolved evidence before atomic mapping. Every child is initially pending and must receive a role-local final disposition before audit can close the related system aggregate.",
        "",
        "| System | Suggested route | Reason |",
        "| --- | --- | --- |",
    ]
    for item in triage["records"]:
        lines.append("| `{}` | `{}` | {} |".format(item["system"], item["suggested_route"], str(item["reason"]).replace("|", "\\|")))
    for item in triage["records"]:
        lines.extend(["", "## `{}`".format(item["source_evidence_id"]), "", "- Suggested route: `{}`".format(item["suggested_route"]), "- Reason: {}".format(item["reason"]), "- Questions:"])
        lines.extend("  - {}".format(question) for question in item["required_questions"])
        lines.append("- Do not copy this route directly into an audit decision. Complete each child with a final disposition and use `references/system-format-triage.md` to justify it.")
    if review_children is not None:
        lines.extend(["", "## Child Review Batch", ""])
        if batch:
            lines.extend([
                f"- Batch: {batch['index']} of {batch['count']}",
                f"- Stable {review_order} queue range: {batch['start']} to {batch['end']}",
                f"- Children in this file: {batch['selected_children']} of {batch['total_children']} selected children",
            ])
        lines.append("- Review order: `priority` places source-backed geometry and semantic roles before likely instructions and non-rendering defaults. It never changes a child status or disposition." if review_order == "priority" else "- Review order: `source-order` preserves the producer order for a forensic source-order recheck.")
        lines.append("- Systems: " + ", ".join(f"`{item}`" for item in sorted(systems)) if systems else "- Systems: all detected systems")
        if pending_only:
            lines.append("- Status filter: pending children only. Final children remain in the JSON queue for audit and must not be reopened without a concrete conflict.")
        lines.append("- Edit only the matching child record in `system_format_triage.json`, preserve its child ID and source values, then rerun the strict atomic audit. This review view never approves a disposition automatically.")
        for item in review_children:
            record = item["record"]
            child = item["child"]
            priority = as_dict(item.get("review_priority"))
            locator = json.dumps(as_dict(child.get("source_locator")), ensure_ascii=False, sort_keys=True)
            observed = json.dumps(child.get("observed_value"), ensure_ascii=False, sort_keys=True)
            source_text = str(child.get("source_text") or "").replace("|", r"\|").replace("\n", " ")
            lines.extend([
                "",
                f"### `{child.get('child_id')}`",
                "",
                f"- System: `{record.get('system')}`; route: `{record.get('suggested_route')}`",
                f"- Current status: `{child.get('status')}`; linked ordinary evidence: `{child.get('source_unit_evidence_id') or 'none'}`",
                f"- Review priority: `{priority.get('label')}` (rank {priority.get('rank')}); {priority.get('reason')}",
                f"- Source locator: `{locator}`",
                f"- Source text: {source_text}",
                f"- Observed value: `{observed}`",
                f"- Required question: {record.get('required_questions', ['Classify the role-local effect.'])[0]}",
            ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("format_ledger", help="word_format_ledger.json")
    parser.add_argument("--existing", help="Existing ledger-matched system_format_triage.json to review without resetting final child decisions")
    parser.add_argument("--output", required=True, help="Output system_format_triage.json")
    parser.add_argument("--markdown-output", help="Optional system_format_triage.md")
    parser.add_argument("--systems", help="Comma-separated system names to expose in the child review view")
    parser.add_argument("--pending-only", action="store_true", help="Expose only pending child decisions in the child review view")
    parser.add_argument("--batch-size", type=int, help="Stable number of selected child decisions to expose")
    parser.add_argument("--batch-index", type=int, default=1, help="One-based child batch index when --batch-size is set")
    parser.add_argument("--review-order", choices=("priority", "source-order"), default="priority", help="Deterministic work order for child cards; priority is non-binding and source-order is available for forensic review")
    args = parser.parse_args()

    ledger = json.loads(Path(args.format_ledger).read_text(encoding="utf-8"))
    if args.existing:
        triage = json.loads(Path(args.existing).read_text(encoding="utf-8"))
        if triage.get("schema_version") != SCHEMA_VERSION:
            raise SystemExit(f"--existing must use {SCHEMA_VERSION}.")
        if triage.get("ledger_fingerprint") != ledger.get("evidence_fingerprint"):
            raise SystemExit("--existing belongs to a different Word ledger; rebuild triage before reviewing children.")
        try:
            refresh_pending_source_fields(triage, ledger)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    else:
        triage = build_triage(ledger)
    systems = {item.strip() for item in (args.systems or "").split(",") if item.strip()} or None
    available_systems = {str(item.get("system") or "") for item in as_list(triage.get("records"))}
    unknown_systems = sorted((systems or set()) - available_systems)
    if unknown_systems:
        raise SystemExit("Unknown --systems value(s): " + ", ".join(unknown_systems))
    review_children = None
    batch = None
    if args.systems or args.pending_only or args.batch_size is not None:
        review_children = select_review_children(triage, ledger, systems, args.pending_only, args.review_order)
        if not review_children:
            raise SystemExit("No matching child decisions remain in this review scope. Remove --pending-only only to audit final child records.")
        total_selected_children = len(review_children)
        if args.batch_size is not None:
            if args.batch_size <= 0:
                raise SystemExit("--batch-size must be positive")
            batch_count = max(1, (len(review_children) + args.batch_size - 1) // args.batch_size)
            if args.batch_index < 1 or args.batch_index > batch_count:
                raise SystemExit(f"--batch-index must be between 1 and {batch_count}")
            start = (args.batch_index - 1) * args.batch_size
            end = min(start + args.batch_size, len(review_children))
            review_children = review_children[start:end]
            batch = {
                "index": args.batch_index,
                "count": batch_count,
                "start": start + 1,
                "end": end,
                "selected_children": len(review_children),
                "total_children": total_selected_children,
            }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(triage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown_output:
        markdown_output = Path(args.markdown_output)
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(markdown(triage, review_children, batch, systems, args.pending_only, args.review_order), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
