#!/usr/bin/env python3
"""Audit one explicit disposition for every visible Word paragraph and run."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "temp2tex.atomic-mapping-decisions.v1"
FINAL_STATUSES = {"mapped", "default", "unresolved", "not_observable", "guidance"}
SYSTEM_AGGREGATE_EVIDENCE_IDS = {
    "page.text-grid.system",
    "paragraph.tab-stops.system",
    "paragraph.break-policy.system",
    "run.character-effects.system",
    "run.character-styles.system",
    "run.script-language.system",
    "document.theme.system",
}
SYSTEM_AGGREGATE_EVIDENCE_PREFIXES = ("word.unmodeled-format-properties.",)
GUIDANCE_KINDS = {
    "author_instruction",
    "editorial_note",
    "placeholder_example",
    "template_scaffold",
    "non_manuscript_furniture",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def visible_text(item: dict[str, Any]) -> str:
    return str(item.get("text") or item.get("format_span_text") or "").strip()


def layout_only_run_kind(item: dict[str, Any]) -> str | None:
    """Classify a non-glyph run that can still carry Word layout evidence.

    A tab, line break, non-breaking space, or directly formatted ordinary
    whitespace is not manuscript wording, but it can govern a header field,
    table cell, inline separator, or local run boundary. It needs an explicit
    disposition rather than disappearing because `strip()` is empty. Plain
    inherited spaces remain covered by their parent paragraph.
    """
    raw = str(item.get("text") or item.get("format_span_text") or "")
    if raw.strip() or not raw:
        return None
    if "\t" in raw:
        return "tab"
    if "\r" in raw or "\n" in raw:
        return "line_break"
    if "\u00a0" in raw:
        return "nonbreaking_space"
    if has_direct_format(item):
        return "formatted_whitespace"
    return None


def is_system_aggregate_evidence_id(evidence_id: str) -> bool:
    """Return whether an object record must be decided through child triage.

    These records summarize heterogeneous Word spans, named styles, or OOXML
    properties. A normal atomic mapping decision would collapse them into one
    apparent role and can silently create a document-wide LaTeX policy.
    """
    return evidence_id in SYSTEM_AGGREGATE_EVIDENCE_IDS or evidence_id.startswith(SYSTEM_AGGREGATE_EVIDENCE_PREFIXES)


def system_triage_fingerprint(triage: dict[str, Any] | None) -> str | None:
    """Bind an atomic-audit result to the exact child queue it reviewed."""
    if not isinstance(triage, dict):
        return None
    payload = json.dumps(triage, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def has_direct_format(item: dict[str, Any]) -> bool:
    direct = item.get("direct_format")
    if not isinstance(direct, dict):
        return False
    return any(bool(value) for value in direct.values())


def format_leaf_values(value: object, prefix: str = "direct_format") -> dict[str, object]:
    """Return scalar direct-format values that require an explicit owner.

    Effective style inheritance is reviewed at role level. Direct Word
    formatting is different: it is a local override and cannot be certified by
    merely naming a generic class macro. Every observed scalar override must
    point to an executable token in the editable package or remain a gap.
    """
    if isinstance(value, dict):
        values: dict[str, object] = {}
        for key, child in sorted(value.items()):
            values.update(format_leaf_values(child, f"{prefix}.{key}"))
        return values
    if isinstance(value, list):
        values = {}
        for index, child in enumerate(value):
            values.update(format_leaf_values(child, f"{prefix}[{index}]"))
        return values
    return {prefix: value}


def direct_format_paths(unit: dict[str, Any]) -> list[str]:
    return sorted(direct_format_values(unit))


def direct_format_values(unit: dict[str, Any]) -> dict[str, object]:
    signature = unit.get("format_signature") if isinstance(unit.get("format_signature"), dict) else {}
    direct = signature.get("direct_format") if isinstance(signature.get("direct_format"), dict) else {}
    return format_leaf_values(direct) if direct else {}


def object_format_values(unit: dict[str, Any]) -> dict[str, object]:
    """Return observable object-layout fields that need an editable owner.

    Tables, drawings, page frames, and furniture are not ordinary paragraph
    formatting.  Their geometry is recorded under `format_signature`, so a
    generic float or geometry macro must not silently certify dimensions,
    anchoring, wrapping, grid widths, borders, cell padding, or section frame.
    Relationship IDs and source-part bookkeeping identify an asset but do not
    themselves describe a visible format.
    """
    if str(unit.get("source_scope") or "") != "object":
        return {}
    signature = unit.get("format_signature") if isinstance(unit.get("format_signature"), dict) else {}
    values = format_leaf_values(signature, "format_signature")
    non_layout_suffixes = {
        ".relationship_id",
        ".part",
        ".source_section_index",
        ".paragraph_index",
        ".drawing_ordinal",
        ".id",
    }
    filtered = {
        path: value
        for path, value in values.items()
        if value is not None
        and ".paragraph_effective_format." not in path
        and not any(path.endswith(suffix) for suffix in non_layout_suffixes)
    }
    # Word drawing records duplicate native width/height next to their geometry
    # payload. Retain the geometry occurrence as the editable placement source
    # and avoid asking the model to bind the same measurement twice.
    for dimension in ("width_emu", "height_emu"):
        outer = f"format_signature.drawing_placement.{dimension}"
        geometry = f"format_signature.drawing_placement.geometry.{dimension}"
        if outer in filtered and geometry in filtered and filtered[outer] == filtered[geometry]:
            filtered.pop(outer)
    return filtered


def source_units(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    """Return body and ancillary paragraph-format and local-run units."""
    units: list[dict[str, Any]] = []
    for collection, source_scope in (("paragraphs", "body_or_table"), ("ancillary_units", "ancillary")):
        for paragraph in ledger.get(collection) or []:
            if not isinstance(paragraph, dict):
                continue
            paragraph_id = str(paragraph.get("evidence_id") or "")
            layout_only = bool(paragraph.get("layout_only"))
            if not paragraph_id or (not visible_text(paragraph) and not layout_only):
                continue
            candidates = paragraph.get("role_candidates") or []
            common = {
                "source_scope": source_scope,
                "container": str(paragraph.get("container") or "document_flow"),
                "context": paragraph.get("context") if isinstance(paragraph.get("context"), dict) else {},
                "role_candidates": candidates if isinstance(candidates, list) else [],
            }
            units.append({
                "evidence_id": paragraph_id,
                "kind": "paragraph_layout" if layout_only else "paragraph",
                "text": visible_text(paragraph) or "[empty paragraph layout]",
                "layout_only": layout_only,
                "has_direct_format": has_direct_format(paragraph),
                "format_signature": {
                    "direct_format": paragraph.get("direct_format") or {},
                    "effective_format": paragraph.get("effective_format") or {},
                },
                **common,
            })
            for span in paragraph.get("format_spans") or []:
                if not isinstance(span, dict):
                    continue
                span_id = str(span.get("evidence_id") or "")
                if not span_id:
                    continue
                span_text = visible_text(span)
                layout_kind = layout_only_run_kind(span)
                if not span_text and not layout_kind:
                    continue
                span_candidates = span.get("role_candidates")
                span_common = {
                    **common,
                    "role_candidates": span_candidates if isinstance(span_candidates, list) else common["role_candidates"],
                }
                if isinstance(span_candidates, list) and span_candidates != common["role_candidates"]:
                    span_common["parent_role_candidates"] = common["role_candidates"]
                units.append({
                    "evidence_id": span_id,
                    "kind": "run_layout" if layout_kind else "run",
                    "text": span_text or f"[{layout_kind}]",
                    "layout_only_kind": layout_kind,
                    "raw_text": str(span.get("text") or span.get("format_span_text") or "") if layout_kind else None,
                    "has_direct_format": has_direct_format(span),
                    "format_signature": {
                        "direct_format": span.get("direct_format") or {},
                        "effective_format": span.get("effective_format") or {},
                    },
                    **span_common,
                })
    for item in ledger.get("object_evidence") or []:
        if not isinstance(item, dict):
            continue
        evidence_id = str(item.get("evidence_id") or "")
        # These records summarize many distinct Word spans or properties. They
        # are audited through system_format_triage.json, never as one generic
        # decision that could conceal mixed roles.
        if is_system_aggregate_evidence_id(evidence_id):
            continue
        if not evidence_id or not visible_text(item):
            continue
        candidates = item.get("role_candidates") if isinstance(item.get("role_candidates"), list) else []
        units.append({
            "evidence_id": evidence_id,
            "kind": str(item.get("kind") or "object"),
            "text": visible_text(item),
            "has_direct_format": bool(item.get("has_direct_format")),
            "format_signature": item.get("format_signature") if isinstance(item.get("format_signature"), dict) else {},
            "source_scope": "object",
            "container": str(item.get("kind") or "object"),
            "context": item.get("context") if isinstance(item.get("context"), dict) else {},
            "role_candidates": candidates,
        })
    return units


def source_capture(ledger: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    coverage = ledger.get("coverage")
    if not isinstance(coverage, dict):
        return False, [{
            "area": "ledger_scope",
            "reason": "Ledger has no coverage record. Rebuild it with the current build_word_format_ledger.py before strict atomic audit.",
        }]
    if ledger.get("schema_version") != "temp2tex.word-format-ledger.v3":
        return False, [{
            "area": "object_geometry",
            "reason": "Rebuild the Word ledger with v3 before strict audit so observable table structure and drawing placement are included.",
        }]
    limitations = coverage.get("capture_limitations")
    if not isinstance(limitations, list):
        limitations = [{
            "area": "ledger_scope",
            "reason": "Ledger coverage has no capture-limitations list; rebuild it before strict atomic audit.",
        }]
    objects_complete = coverage.get("all_observable_object_units_captured")
    if objects_complete is False:
        limitations = [*limitations, {
            "area": "object_geometry",
            "reason": "Ledger did not capture every observable Word table/drawing structure unit.",
        }]
    return bool(coverage.get("all_visible_text_units_captured")) and objects_complete is not False and not limitations, limitations


def candidate_role_names(unit: dict[str, Any]) -> set[str]:
    """Return the source-backed role names that a mapping decision may claim."""
    return {
        str(candidate.get("role") or "")
        for candidate in unit.get("role_candidates") or []
        if isinstance(candidate, dict) and str(candidate.get("role") or "")
    }


def decision_group_key(unit: dict[str, Any]) -> str:
    """Group only evidence that can share one semantic disposition safely."""
    roles = [
        {"role": item.get("role"), "confidence": item.get("confidence")}
        for item in unit.get("role_candidates", []) if isinstance(item, dict)
    ]
    payload = {
        "kind": unit["kind"],
        "source_scope": unit.get("source_scope"),
        "container": unit.get("container"),
        "roles": roles,
        "format_signature": unit["format_signature"],
    }
    # A generic candidate role is intentionally conservative. Equal default
    # formatting is not proof that two paragraphs share a semantic role: a
    # declaration, author bio, editorial instruction, and ordinary body prose
    # often inherit the same Word style. Local layout units need the same
    # isolation even when their role is source-confirmed: two blank paragraphs
    # with matching spacing can sit between entirely different semantic blocks.
    local_layout = str(unit.get("kind") or "") in {"paragraph_layout", "run_layout"}
    if local_layout or any(
        str(item.get("confidence") or "") != "source"
        for item in unit.get("role_candidates", [])
        if isinstance(item, dict)
    ):
        evidence_id = str(unit.get("evidence_id") or "")
        payload["local_parent_evidence"] = evidence_id.split(".r", 1)[0]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def starter(ledger: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for unit in source_units(ledger):
        groups.setdefault(decision_group_key(unit), []).append(unit)
    return {
        "schema_version": SCHEMA_VERSION,
        "source": ledger.get("source"),
        "instructions": (
            "Review every group before deciding it. Split a group whenever its "
            "text samples do not have the same semantic status. Mapped/default decisions need a named "
            "editable LaTeX owner. When a package is supplied, mapped/default decisions also need "
            "a package-relative latex_file and an executable latex_token in that exact file. For any direct Word formatting, "
            "format_bindings must cover every listed direct_format path with its own package-local LaTeX token. For an observable object-layout unit, "
            "object_format_bindings must cover every listed geometry/structure path with its own package-local LaTeX token. Guidance decisions also need "
            "a guidance_kind: author_instruction, editorial_note, placeholder_example, template_scaffold, or "
            "non_manuscript_furniture, plus a concise reason. Unresolved and not_observable decisions need a concise reason."
        ),
        "decisions": [
            {
                "evidence_ids": [unit["evidence_id"] for unit in group],
                "status": "pending",
                "role": "",
                "latex_owner": "",
                "latex_file": "",
                "latex_token": "",
                "required_format_binding_paths": sorted({path for unit in group for path in direct_format_paths(unit)}),
                "required_format_binding_values": direct_format_values(group[0]),
                "format_bindings": [],
                "required_object_format_binding_paths": sorted({path for unit in group for path in object_format_values(unit)}),
                "required_object_format_binding_values": object_format_values(group[0]),
                "object_format_bindings": [],
                "guidance_kind": "",
                "reason": "",
                "group_key": group_key,
                "source_scope": group[0].get("source_scope"),
                "container": group[0].get("container"),
                "kind": group[0]["kind"],
                "role_candidates": group[0]["role_candidates"],
                "text_samples": [unit["text"][:240] for unit in group[:5]],
                "context_samples": [unit.get("context") or {} for unit in group[:3]],
            }
            for group_key, group in sorted(groups.items())
        ],
    }


def strip_tex_comments(text: str) -> str:
    """Remove unescaped TeX comments before searching for executable tokens."""
    output = []
    for line in text.splitlines():
        slash_count = 0
        visible = []
        for character in line:
            if character == "\\":
                slash_count += 1
                visible.append(character)
                continue
            if character == "%" and slash_count % 2 == 0:
                break
            visible.append(character)
            slash_count = 0
        output.append("".join(visible))
    return "\n".join(output)


def package_file_text(package: Path, relative_file: str) -> tuple[str | None, str | None]:
    """Return uncommented text only from a declared package-local LaTeX file."""
    requested = Path(relative_file)
    if not relative_file or requested.is_absolute() or ".." in requested.parts:
        return None, "latex_file must be a package-relative .tex or .cls path."
    resolved_package = package.resolve()
    candidate = (resolved_package / requested).resolve()
    try:
        candidate.relative_to(resolved_package)
    except ValueError:
        return None, "latex_file escapes the audited package directory."
    if candidate.suffix.lower() not in {".tex", ".cls"} or not candidate.is_file():
        return None, "latex_file does not name an existing package .tex or .cls file."
    return strip_tex_comments(candidate.read_text(encoding="utf-8", errors="replace")), None


def bare_macro_usage_errors(package: Path | None, relative_file: str, latex_token: str, field: str = "latex_token") -> list[str]:
    """Reject a mapped bare macro that is only declared, never used.

    A class definition is not formatting evidence by itself. This inexpensive
    guard intentionally applies only to a bare control-sequence token in a
    class file; compound declarations such as ``\\setlength{...}`` are active
    at class load and require role-level rendering rather than a text-use
    heuristic. It is still traceability evidence, not a render-fidelity proof.
    """
    if package is None or Path(relative_file).suffix.lower() != ".cls":
        return []
    token = latex_token.strip()
    if not re.fullmatch(r"\\[A-Za-z@]+", token):
        return []
    definition_text, file_error = package_file_text(package, relative_file)
    if file_error or definition_text is None:
        return []
    token_pattern = re.escape(token) + r"(?![A-Za-z@])"
    definition_patterns = (
        r"\\(?:newcommand|renewcommand|providecommand)\s*\*?\s*\{\s*" + re.escape(token) + r"\s*\}",
        r"\\def\s*" + re.escape(token) + r"(?![A-Za-z@])",
    )
    declaration_count = sum(len(re.findall(pattern, definition_text)) for pattern in definition_patterns)
    if not declaration_count:
        return []
    use_count = 0
    for candidate in package.rglob("*"):
        if candidate.suffix.lower() not in {".tex", ".cls"} or not candidate.is_file():
            continue
        try:
            text = strip_tex_comments(candidate.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        use_count += len(re.findall(token_pattern, text))
    if use_count <= declaration_count:
        return [
            f"{field} names a bare macro declared in {relative_file} but no non-declaration package use was found; map the active invocation or leave the role unresolved."
        ]
    return []


def format_binding_errors(
    required_values: dict[str, object],
    bindings: object,
    package: Path | None,
    binding_field: str = "format_bindings",
    source_label: str = "direct Word formatting",
) -> list[str]:
    """Validate direct-Word-format to editable-LaTeX binding declarations."""
    if not required_values:
        return []
    if not isinstance(bindings, list) or not bindings:
        return [f"Mapped/default evidence with {source_label} requires {binding_field} for every recorded source path."]
    expected = set(required_values)
    seen: set[str] = set()
    errors: list[str] = []
    for index, binding in enumerate(bindings, start=1):
        if not isinstance(binding, dict):
            errors.append(f"{binding_field}[{index}] must be an object.")
            continue
        source_path = str(binding.get("source_path") or "")
        if source_path not in expected:
            errors.append(f"{binding_field}[{index}].source_path is not a recorded {source_label} path for this unit.")
            continue
        if source_path in seen:
            errors.append(f"{binding_field} duplicates {source_path}.")
            continue
        seen.add(source_path)
        if binding.get("source_value") != required_values[source_path]:
            errors.append(f"{binding_field}[{index}].source_value does not match the Word value for {source_path}.")
        if not str(binding.get("mapping_reason") or "").strip():
            errors.append(f"{binding_field}[{index}] needs mapping_reason for {source_path}.")
        latex_file = str(binding.get("latex_file") or "")
        latex_token = str(binding.get("latex_token") or "")
        if not latex_file or not latex_token:
            errors.append(f"{binding_field}[{index}] needs latex_file and latex_token for {source_path}.")
            continue
        if package is not None:
            file_text, file_error = package_file_text(package, latex_file)
            if file_error:
                errors.append(f"{binding_field}[{index}]: {file_error}")
            elif latex_token not in str(file_text):
                errors.append(f"{binding_field}[{index}].latex_token was not found outside comments for {source_path}.")
            else:
                errors.extend(
                    bare_macro_usage_errors(
                        package,
                        latex_file,
                        latex_token,
                        f"{binding_field}[{index}].latex_token",
                    )
                )
    missing = sorted(expected - seen)
    if missing:
        errors.append(f"{binding_field} is missing recorded {source_label} paths: " + ", ".join(missing))
    return errors


def system_aggregate_ids(ledger: dict[str, Any]) -> set[str]:
    """Return the system-triage record IDs required by this ledger.

    Most system aggregates have one ledger evidence ID and one triage record.
    Unmodeled OOXML properties are deliberately different: the ledger records
    their aggregate presence as ``...properties.system``, while triage creates
    an independently reviewable record for every concrete XML node.  Strict
    audit must therefore require those node records, never a synthetic
    aggregate record that the triage producer cannot emit.
    """
    expected: set[str] = set()
    for item in ledger.get("object_evidence") or []:
        if not isinstance(item, dict):
            continue
        evidence_id = str(item.get("evidence_id") or "")
        if evidence_id != "word.unmodeled-format-properties.system":
            if is_system_aggregate_evidence_id(evidence_id):
                expected.add(evidence_id)
            continue

        objects = ledger.get("objects") if isinstance(ledger.get("objects"), dict) else {}
        unmodeled = objects.get("unmodeled_format_properties")
        properties = unmodeled.get("properties") if isinstance(unmodeled, dict) else []
        nodes = {
            str(property_item.get("node") or "").strip()
            for property_item in properties or []
            if isinstance(property_item, dict) and str(property_item.get("node") or "").strip()
        }
        if nodes:
            expected.update(f"word.unmodeled-format-properties.{node}" for node in nodes)
        else:
            # Preserve a conservative failure for malformed ledgers instead of
            # silently treating an aggregate with no inspectable nodes as done.
            expected.add(evidence_id)
    return expected


def audit_system_triage(
    ledger: dict[str, Any],
    triage: dict[str, Any] | None,
    normal_results: list[dict[str, Any]],
    package: Path | None,
) -> dict[str, Any]:
    """Validate that system aggregates were split into reviewable child evidence.

    The ordinary paragraph/run audit owns document content.  A system child may
    cite that ordinary unit but cannot replace it.  This guard blocks a common
    failure mode: mapping an entire Word theme or character-effect collection
    to one no-op global macro.
    """
    expected_ids = system_aggregate_ids(ledger)
    if not expected_ids:
        return {"required": 0, "complete": True, "unresolved": 0, "gaps": []}
    if not isinstance(triage, dict):
        return {
            "required": len(expected_ids),
            "complete": False,
            "unresolved": len(expected_ids),
            "gaps": [{"area": "system_format_triage", "reason": "System aggregate evidence exists but no system_format_triage.json was supplied."}],
        }
    if triage.get("schema_version") != "temp2tex.system-format-triage.v2":
        return {
            "required": len(expected_ids),
            "complete": False,
            "unresolved": len(expected_ids),
            "gaps": [{"area": "system_format_triage", "reason": "Rebuild system_format_triage.json with prepare_system_format_triage.py v2 before strict audit."}],
        }
    if triage.get("ledger_fingerprint") != ledger.get("evidence_fingerprint"):
        return {
            "required": len(expected_ids),
            "complete": False,
            "unresolved": len(expected_ids),
            "gaps": [{"area": "system_format_triage", "reason": "System triage belongs to a different Word ledger; rebuild it before audit."}],
        }

    result_by_id = {str(item.get("evidence_id") or ""): item for item in normal_results}
    records = {
        str(item.get("source_evidence_id") or ""): item
        for item in triage.get("records") or []
        if isinstance(item, dict)
    }
    gaps: list[dict[str, Any]] = []
    unresolved = 0
    child_total = 0
    for evidence_id in sorted(expected_ids):
        record = records.get(evidence_id)
        if not isinstance(record, dict):
            gaps.append({"area": evidence_id, "reason": "No matching system-triage record was supplied."})
            unresolved += 1
            continue
        children = record.get("children") if isinstance(record.get("children"), list) else []
        declared_count = record.get("child_count")
        if not children or declared_count != len(children):
            gaps.append({"area": evidence_id, "reason": "System triage must contain every explicit child record with an accurate child_count."})
            unresolved += 1
            continue
        child_total += len(children)
        for child in children:
            if not isinstance(child, dict):
                gaps.append({"area": evidence_id, "reason": "A system-triage child is not a JSON object."})
                unresolved += 1
                continue
            child_id = str(child.get("child_id") or evidence_id)
            status = str(child.get("status") or "pending").strip().lower()
            reason = str(child.get("reason") or "").strip()
            if status not in FINAL_STATUSES:
                gaps.append({"area": child_id, "reason": "System child has no final disposition."})
                unresolved += 1
                continue
            if not reason:
                gaps.append({"area": child_id, "reason": "This system-child disposition needs a concise reason."})
                unresolved += 1
                continue
            if status == "guidance" and str(child.get("guidance_kind") or "").strip().lower() not in GUIDANCE_KINDS:
                gaps.append({"area": child_id, "reason": "Guidance system evidence requires a recognized guidance_kind."})
                unresolved += 1
                continue
            link = str(child.get("source_unit_evidence_id") or "")
            if status in {"mapped", "default"}:
                owner = str(child.get("latex_owner") or "")
                latex_file = str(child.get("latex_file") or "")
                latex_token = str(child.get("latex_token") or "")
                if not owner or not latex_file or not latex_token:
                    gaps.append({"area": child_id, "reason": "Mapped/default system child needs a named local LaTeX owner, file, and token even when it links to an ordinary Word unit."})
                    unresolved += 1
                    continue
                if link:
                    linked = result_by_id.get(link)
                    if not linked or linked.get("status") not in {"mapped", "default"}:
                        gaps.append({"area": child_id, "reason": "Mapped/default system child must link to a mapped/default ordinary Word unit."})
                        unresolved += 1
                        continue
                if package:
                    file_text, file_error = package_file_text(package, latex_file)
                    if file_error or latex_token not in str(file_text):
                        gaps.append({"area": child_id, "reason": file_error or "System-child latex_token was not found outside comments."})
                        unresolved += 1
                        continue
                    usage_errors = bare_macro_usage_errors(package, latex_file, latex_token)
                    if usage_errors:
                        gaps.append({"area": child_id, "reason": "; ".join(usage_errors)})
                        unresolved += 1
                        continue
            if status == "unresolved":
                unresolved += 1
    return {
        "required": len(expected_ids),
        "child_records": child_total,
        "complete": not gaps,
        "unresolved": unresolved,
        "gaps": gaps,
    }


def audit(
    ledger: dict[str, Any],
    decisions_file: dict[str, Any] | None,
    package: Path | None,
    system_triage: dict[str, Any] | None,
) -> dict[str, Any]:
    units = source_units(ledger)
    capture_complete, capture_limitations = source_capture(ledger)
    decisions = decisions_file.get("decisions", []) if isinstance(decisions_file, dict) else []
    legacy_system_aggregate_groups = 0
    decision_by_id: dict[str, dict[str, Any]] = {}
    duplicate_ids: set[str] = set()
    for item in decisions:
        if not isinstance(item, dict):
            continue
        raw_ids = item.get("evidence_ids") if isinstance(item.get("evidence_ids"), list) else [item.get("evidence_id")]
        if raw_ids and all(is_system_aggregate_evidence_id(str(raw_id or "")) for raw_id in raw_ids):
            legacy_system_aggregate_groups += 1
            continue
        for raw_id in raw_ids:
            evidence_id = str(raw_id or "")
            if not evidence_id:
                continue
            if evidence_id in decision_by_id:
                duplicate_ids.add(evidence_id)
            else:
                decision_by_id[evidence_id] = item
    results: list[dict[str, Any]] = []
    for unit in units:
        decision = decision_by_id.get(unit["evidence_id"])
        priority = "critical" if unit["has_direct_format"] else "high" if unit["kind"] == "paragraph" else "medium"
        if not isinstance(decision, dict):
            results.append({**unit, "status": "needs_decision", "priority": priority, "reason": "No explicit disposition was supplied."})
            continue
        status = str(decision.get("status") or "pending").strip().lower()
        base = {
            **unit,
            "status": status,
            "priority": priority,
            "role": str(decision.get("role") or ""),
            "latex_owner": str(decision.get("latex_owner") or ""),
            "latex_file": str(decision.get("latex_file") or ""),
            "latex_token": str(decision.get("latex_token") or ""),
            "format_bindings": decision.get("format_bindings") if isinstance(decision.get("format_bindings"), list) else [],
            "object_format_bindings": decision.get("object_format_bindings") if isinstance(decision.get("object_format_bindings"), list) else [],
            "guidance_kind": str(decision.get("guidance_kind") or "").strip().lower(),
            "reason": str(decision.get("reason") or ""),
        }
        if unit["evidence_id"] in duplicate_ids:
            results.append({**base, "status": "invalid_decision", "reason": "More than one decision covers this evidence ID."})
            continue
        if status not in FINAL_STATUSES:
            results.append({**base, "status": "needs_decision", "reason": base["reason"] or "Decision is missing or still pending."})
            continue
        if status in {"mapped", "default"} and not base["latex_owner"]:
            results.append({**base, "status": "invalid_decision", "reason": "Mapped/default evidence requires a named editable LaTeX owner."})
            continue
        if status in {"mapped", "default"} and not base["role"]:
            results.append({**base, "status": "invalid_decision", "reason": "Mapped/default evidence requires a declared role."})
            continue
        if status in {"mapped", "default"} and base["role"] not in candidate_role_names(unit):
            results.append({
                **base,
                "status": "invalid_decision",
                "reason": "Mapped/default role is not one of this Word unit's source-backed role candidates.",
            })
            continue
        if status in {"mapped", "default"} and package:
            if not base["latex_file"]:
                results.append({**base, "status": "invalid_decision", "reason": "Mapped/default evidence requires latex_file when a package is audited."})
                continue
            if not base["latex_token"]:
                results.append({**base, "status": "invalid_decision", "reason": "Mapped/default evidence requires latex_token when a package is audited."})
                continue
            file_text, file_error = package_file_text(package, base["latex_file"])
            if file_error:
                results.append({**base, "status": "invalid_decision", "reason": file_error})
                continue
            if base["latex_token"] not in str(file_text):
                results.append({**base, "status": "invalid_decision", "reason": "latex_token was not found outside comments in latex_file."})
                continue
            usage_errors = bare_macro_usage_errors(package, base["latex_file"], base["latex_token"])
            if usage_errors:
                results.append({**base, "status": "invalid_decision", "reason": "; ".join(usage_errors)})
                continue
        if status in {"mapped", "default"}:
            binding_errors = format_binding_errors(direct_format_values(unit), base["format_bindings"], package)
            if binding_errors:
                results.append({**base, "status": "invalid_decision", "reason": "; ".join(binding_errors)})
                continue
            object_binding_errors = format_binding_errors(
                object_format_values(unit),
                base["object_format_bindings"],
                package,
                "object_format_bindings",
                "observable Word object layout",
            )
            if object_binding_errors:
                results.append({**base, "status": "invalid_decision", "reason": "; ".join(object_binding_errors)})
                continue
        if status == "guidance" and base["guidance_kind"] not in GUIDANCE_KINDS:
            results.append({**base, "status": "invalid_decision", "reason": "Guidance evidence requires a recognized guidance_kind."})
            continue
        if status in {"guidance", "unresolved", "not_observable"} and not base["reason"]:
            results.append({**base, "status": "invalid_decision", "reason": "This disposition requires a concise reason."})
            continue
        results.append(base)
    pending = [item for item in results if item["status"] in {"needs_decision", "invalid_decision"}]
    unresolved = [item for item in results if item["status"] == "unresolved"]
    system_audit = audit_system_triage(ledger, system_triage, results, package)
    return {
        "schema_version": "temp2tex.atomic-mapping-audit.v1",
        "purpose": "Verify one explicit disposition for every captured visible Word paragraph and contiguous run-format span, including ancillary layout text.",
        "source": ledger.get("source"),
        "ledger_fingerprint": ledger.get("evidence_fingerprint"),
        "system_triage_fingerprint": system_triage_fingerprint(system_triage),
        "package_checked": str(package) if package else None,
        "decision_file_present": decisions_file is not None,
        "summary": {
            "required_units": len(results),
            "mapped": sum(item["status"] == "mapped" for item in results),
            "default": sum(item["status"] == "default" for item in results),
            "guidance": sum(item["status"] == "guidance" for item in results),
            "guidance_by_kind": {
                kind: sum(item["status"] == "guidance" and item.get("guidance_kind") == kind for item in results)
                for kind in sorted(GUIDANCE_KINDS)
            },
            "not_observable": sum(item["status"] == "not_observable" for item in results),
            "unresolved": len(unresolved),
            "needs_decision": len(pending),
            "direct_format_units": sum(item["has_direct_format"] for item in results),
            "layout_only_run_units": sum(item["kind"] == "run_layout" for item in results),
            "decision_groups": len(decisions) - legacy_system_aggregate_groups,
            "legacy_system_aggregate_groups_ignored": legacy_system_aggregate_groups,
            "source_capture_complete": capture_complete,
            "capture_limitations": len(capture_limitations),
            "system_triage_required": system_audit["required"],
            "system_triage_child_records": system_audit.get("child_records", 0),
            "system_triage_unresolved": system_audit["unresolved"],
        },
        "system_triage": system_audit,
        "audit_complete": capture_complete and not pending and system_audit["complete"],
        "fidelity_complete": capture_complete and not pending and not unresolved and system_audit["complete"] and not system_audit["unresolved"],
        "priority_gaps": capture_limitations + pending + unresolved + system_audit["gaps"],
        "units": results,
        "next_action": (
            "Rebuild or complete source capture before treating this audit as complete."
            if not capture_complete else
            "Complete the missing unit dispositions before changing class-wide formatting or interpreting PDF geometry."
            if pending else
            "Complete the role-local system-format child review before closing aggregate Word formatting evidence."
            if not system_audit["complete"] else
            "Resolve the remaining explicit gaps before claiming full fidelity."
            if unresolved else
            "Use the role-level same-content contract before promoting render calibration."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("format_ledger", help="word_format_ledger.json")
    parser.add_argument("--decisions", help="Completed atomic_mapping_decisions.json")
    parser.add_argument("--package", help="Generated LaTeX package to check mapped tokens against")
    parser.add_argument("--system-triage", help="system_format_triage.json with child-level system evidence dispositions")
    parser.add_argument("--starter", help="Write a complete pending decision file for the supplied ledger")
    parser.add_argument("--output", required=True, help="atomic_mapping_audit.json")
    parser.add_argument("--strict", action="store_true", help="Return non-zero unless all units have a valid final disposition")
    args = parser.parse_args()
    ledger = load_json(Path(args.format_ledger))
    decisions = None
    if args.starter:
        starter_path = Path(args.starter)
        starter_path.parent.mkdir(parents=True, exist_ok=True)
        decisions = starter(ledger)
        starter_path.write_text(json.dumps(decisions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.decisions:
        decisions = load_json(Path(args.decisions))
    system_triage = load_json(Path(args.system_triage)) if args.system_triage else None
    package = Path(args.package).resolve() if args.package else None
    report = audit(ledger, decisions, package, system_triage)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if args.strict and not report["audit_complete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
