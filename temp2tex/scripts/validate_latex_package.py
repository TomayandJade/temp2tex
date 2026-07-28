#!/usr/bin/env python3
"""Validate the ordinary Temp2TeX package contract without requiring PDF tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from prepare_front_matter_confirmation import validation_errors as front_matter_confirmation_errors


REQUIRED_FILES = (
    "main.tex",
    "journal-template.cls",
    "references.bib",
    "template_spec.json",
    "format_gap_log.md",
    "HANDOFF_STATUS.md",
    "README.md",
)
REQUIRED_DIRECTORIES = ("figures", "assets")
REQUIRED_SPEC_SECTIONS = (
    "journal",
    "document",
    "page",
    "front_matter",
    "abstracts",
    "body",
    "tables",
    "figures",
    "references",
    "footnotes",
    "appendices",
    "statements",
    "assets",
    "fallbacks",
)

WORD_SOURCE_SUFFIXES = {".doc", ".docm", ".docx", ".dot", ".dotm", ".dotx", ".rtf"}
MANUAL_LEDGER_FIELDS = (
    "source_ref",
    "excerpt_or_object",
    "observed_format",
    "role",
    "status",
    "latex_owner",
    "reason_and_next_check",
)
MANUAL_AUDIT_FIELDS = ("zone", "status", "ledger", "pending")
VALIDATION_SCHEMA_VERSION = "temp2tex.package-validation.v1"
FINGERPRINT_EXCLUDED_NAMES = {
    "package_validation.json",
    "compile_report.json",
    "render_compare_report.json",
    "conversion_readiness.json",
    "HANDOFF_STATUS.md",
}
FINGERPRINT_EXCLUDED_SUFFIXES = {".aux", ".log", ".out", ".pdf", ".dvi", ".ps"}
CITATION_COMMAND_RE = re.compile(r"\\(?:cite[a-zA-Z*]*|autocite|textcite|parencite)\s*(?:\[[^]]*\]\s*)*\{")
BIB_ENTRY_RE = re.compile(r"(?m)^\s*@\w+\s*\{")
DOCUMENT_CLASS_RE = re.compile(
    r"\\documentclass\s*(?:\[[^\]]*\]\s*)?\{(?:\./)?journal-template(?:\.cls)?\}",
    re.IGNORECASE,
)
TITLE_DECLARATION_RE = re.compile(r"\\[A-Za-z@]*title[A-Za-z@]*\s*\{", re.IGNORECASE)
TITLE_MAKING_RE = re.compile(r"\\(?:maketitle|journalmaketitle)\b", re.IGNORECASE)
ABSTRACT_FIXTURE_RE = re.compile(r"\\(?:begin\s*\{abstract\*?\}|[A-Za-z@]*abstract[A-Za-z@]*\s*\{)", re.IGNORECASE)
HEADING_FIXTURE_RE = re.compile(r"\\(?:section|subsection|subsubsection|paragraph|journalheading)\*?\s*(?:\[[^]]*\]\s*)*\{", re.IGNORECASE)
TABLE_FIXTURE_RE = re.compile(r"\\(?:begin\s*\{(?:journaltable|table\*?|longtable)\}|journaltable\b)", re.IGNORECASE)
FIGURE_FIXTURE_RE = re.compile(r"\\(?:begin\s*\{(?:journalfigure|figure\*?)\}|journalfigure\b)", re.IGNORECASE)
EQUATION_FIXTURE_RE = re.compile(r"\\(?:begin\s*\{(?:equation\*?|align\*?|gather\*?|multline\*?)\}|\[)", re.IGNORECASE)
NOTE_FIXTURE_RE = re.compile(r"\\(?:footnote|thanks|journalauthornote|journalfootnote)\s*\{", re.IGNORECASE)
AUTHOR_FIXTURE_RE = re.compile(r"\\(?:author|[A-Za-z@]*author[A-Za-z@]*)\s*\{", re.IGNORECASE)
AFFILIATION_FIXTURE_RE = re.compile(r"\\(?:affiliation|institute|address|[A-Za-z@]*(?:affiliation|institute)[A-Za-z@]*)\s*\{", re.IGNORECASE)
KEYWORD_FIXTURE_RE = re.compile(r"\\(?:keywords|keyword|indexterms|[A-Za-z@]*(?:keywords|keyword|indexterms)[A-Za-z@]*)\s*\{", re.IGNORECASE)
HANDOFF_STATUS_FIELDS = (
    "current state",
    "ordinary handoff",
    "package validation",
    "package fingerprint",
    "verification environment",
    "required next action",
)
HANDOFF_ORDINARY_RE = re.compile(r"(?im)^\s*-\s*ordinary handoff\s*:\s*(ready_with_pending_local_verification|ready|blocked)\b")
HANDOFF_VALIDATION_RE = re.compile(r"(?im)^\s*-\s*package validation\s*:\s*(valid|pending)\b")
HANDOFF_FINGERPRINT_RE = re.compile(r"(?im)^\s*-\s*package fingerprint\s*:\s*([0-9a-f]{16}|pending)\b")
HANDOFF_ENVIRONMENT_RE = re.compile(r"(?im)^\s*-\s*verification environment\s*:\s*(available|unavailable|pending)\b")


def package_contract_fingerprint(package: Path) -> str:
    """Hash editable package inputs while excluding generated verification output.

    A successful validation report is evidence only for the exact editable
    package it inspected. Compile/render products and the report itself must
    not change that identity, but a class, fixture, evidence, asset, or spec
    edit must force validation to run again.
    """
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


def system_triage_fingerprint(triage: dict | None) -> str | None:
    if not isinstance(triage, dict):
        return None
    payload = json.dumps(triage, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def has_word_source(inventory: dict) -> bool:
    """Return whether the inventory supports a structured Word format ledger.

    A file extension or a legacy-conversion attempt does not establish that
    paragraph/run formatting was readable. Only an inspection that recorded a
    Word paragraph-evidence mode can enter the JSON ledger/atomic-audit path.
    Other inventoried inputs use the manual evidence contract instead.
    """
    files = inventory.get("files") if isinstance(inventory, dict) else None
    if not isinstance(files, list):
        return False
    for entry in files:
        if not isinstance(entry, dict):
            continue
        suffix = str(entry.get("suffix") or Path(str(entry.get("name") or "")).suffix).lower()
        inspection = entry.get("inspection")
        if suffix not in WORD_SOURCE_SUFFIXES or not isinstance(inspection, dict):
            continue
        if str(inspection.get("paragraph_evidence_mode") or "").strip():
            return True
        # Older Temp2TeX inventories predate paragraph_evidence_mode but still
        # record the complete OpenXML inspection shape. Keep them on the
        # structured path while rejecting invalid-word and plain-text fallbacks.
        kind = str(inspection.get("kind") or "").lower()
        has_openxml_shape = all(isinstance(inspection.get(key), list) for key in ("paragraph_samples", "styles", "sections"))
        if kind in {"docx", "docm", "dotx", "dotm"} and has_openxml_shape:
            return True
        conversion = inspection.get("conversion")
        if kind in {"doc", "dot", "rtf"} and isinstance(conversion, dict) and conversion.get("ok") and has_openxml_shape:
            return True
    return False


def inventory_has_recorded_sources(inventory: dict | None) -> bool:
    files = inventory.get("files") if isinstance(inventory, dict) else None
    return isinstance(files, list) and bool(files)


def validate_manual_evidence_contract(package: Path, errors: list[str]) -> None:
    """Require the tool-independent audit records for non-structured inputs."""
    artifacts = (
        ("manual_evidence_ledger.md", MANUAL_LEDGER_FIELDS, "source-located evidence fields"),
        ("manual_mapping_audit.md", MANUAL_AUDIT_FIELDS, "zone-audit fields"),
    )
    for name, fields, label in artifacts:
        path = package / name
        if not path.is_file():
            errors.append(f"Non-structured source evidence requires {name}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{name} could not be read as UTF-8: {exc}")
            continue
        if not text.strip():
            errors.append(f"{name} must not be empty")
            continue
        lower = text.lower()
        missing = [field for field in fields if field not in lower]
        if missing:
            errors.append(f"{name} is missing required {label}: " + ", ".join(missing))


def validate_handoff_status(package: Path, errors: list[str]) -> None:
    """Require an explicit continuation boundary for every generated package."""
    path = package / "HANDOFF_STATUS.md"
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"HANDOFF_STATUS.md could not be read as UTF-8: {exc}")
        return
    if not text.strip():
        errors.append("HANDOFF_STATUS.md must not be empty")
        return
    lower = text.lower()
    missing = [field for field in HANDOFF_STATUS_FIELDS if field not in lower]
    if missing:
        errors.append("HANDOFF_STATUS.md is missing required status fields: " + ", ".join(missing))
        return
    ordinary = HANDOFF_ORDINARY_RE.search(text)
    validation = HANDOFF_VALIDATION_RE.search(text)
    fingerprint = HANDOFF_FINGERPRINT_RE.search(text)
    environment = HANDOFF_ENVIRONMENT_RE.search(text)
    if ordinary is None:
        errors.append("HANDOFF_STATUS.md ordinary handoff must be ready, ready_with_pending_local_verification, or blocked")
        return
    if validation is None or fingerprint is None or environment is None:
        errors.append("HANDOFF_STATUS.md must use machine-readable package validation, fingerprint, and verification-environment fields")
        return
    state = ordinary.group(1).lower()
    validation_state = validation.group(1).lower()
    fingerprint_value = fingerprint.group(1).lower()
    environment_state = environment.group(1).lower()
    if state == "blocked":
        errors.append("HANDOFF_STATUS.md marks ordinary handoff blocked; retain it as a continuation checkpoint")
        return
    if state == "ready_with_pending_local_verification":
        if environment_state != "unavailable":
            errors.append("HANDOFF_STATUS.md pending-local-verification handoff requires verification environment: unavailable")
        if validation_state != "pending" or fingerprint_value != "pending":
            errors.append("HANDOFF_STATUS.md pending-local-verification handoff requires package validation and fingerprint to be pending")
        return
    if environment_state != "available":
        errors.append("HANDOFF_STATUS.md ready ordinary handoff requires verification environment: available")
    if validation_state != "valid":
        errors.append("HANDOFF_STATUS.md marks ordinary handoff ready without package validation: valid")
    expected = package_contract_fingerprint(package)
    if fingerprint_value != expected:
        errors.append("HANDOFF_STATUS.md package fingerprint is stale; refresh status after the latest package edit")


def safe_asset_filename(value: object) -> str | None:
    """Accept one relative filename inside assets/, never an external path."""
    normalized = str(value or "").strip().replace("\\", "/")
    candidate = Path(normalized)
    if not normalized or candidate.is_absolute() or len(candidate.parts) != 1 or candidate.name != normalized:
        return None
    return candidate.name


def validate_asset_contract(package: Path, spec: dict, errors: list[str], warnings: list[str]) -> None:
    """Verify copied Word media without forcing manuscript art into main.tex."""
    assets = spec.get("assets") if isinstance(spec.get("assets"), dict) else {}
    if not assets.get("extraction_required"):
        return

    manifest_value = str(assets.get("extracted_manifest") or "assets/word_asset_manifest.json").strip().replace("\\", "/")
    manifest_relative = Path(manifest_value)
    if (
        not manifest_value
        or manifest_relative.is_absolute()
        or ".." in manifest_relative.parts
        or not manifest_relative.parts
        or manifest_relative.parts[0].lower() != "assets"
    ):
        errors.append("assets.extracted_manifest must be a relative path under assets/")
        return
    manifest_path = package / manifest_relative
    gap_path = package / "format_gap_log.md"
    gap_text = gap_path.read_text(encoding="utf-8", errors="replace").lower() if gap_path.is_file() else ""
    if not manifest_path.is_file():
        if "asset" not in gap_text:
            errors.append("assets.extraction_required needs assets/word_asset_manifest.json or an explicit asset-extraction gap")
        else:
            warnings.append("Word asset extraction remains an explicit gap; retain the rerun action before visual verification")
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Word asset manifest is not valid UTF-8 JSON: {exc}")
        return
    records = manifest.get("assets") if isinstance(manifest, dict) else None
    if not isinstance(records, list):
        errors.append("Word asset manifest must contain an assets list")
        return

    expected_sources = {
        str(item.get("path") or "").replace("\\", "/")
        for item in assets.get("word_media", [])
        if isinstance(item, dict) and str(item.get("path") or "").strip()
    }
    actual_sources = set()
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            errors.append(f"Word asset manifest assets[{index}] must be an object")
            continue
        source_path = str(record.get("source_path") or "").replace("\\", "/")
        if source_path:
            actual_sources.add(source_path)
        output_name = safe_asset_filename(record.get("output"))
        if output_name is None:
            errors.append(f"Word asset manifest assets[{index}] must name one relative output file")
            continue
        output_path = package / "assets" / output_name
        if not output_path.is_file():
            errors.append(f"Word asset manifest assets[{index}] output is missing: assets/{output_name}")
            continue
        expected_bytes = record.get("bytes")
        if isinstance(expected_bytes, int) and expected_bytes >= 0 and output_path.stat().st_size != expected_bytes:
            errors.append(f"Word asset manifest assets[{index}] byte count does not match assets/{output_name}")
        latex_output = record.get("latex_output")
        if latex_output is not None:
            latex_name = safe_asset_filename(latex_output)
            if latex_name is None or not (package / "assets" / latex_name).is_file():
                errors.append(f"Word asset manifest assets[{index}] latex_output is missing under assets/")
    missing_sources = sorted(expected_sources - actual_sources)
    if missing_sources:
        errors.append("Word asset manifest is missing source media: " + ", ".join(missing_sources))
    if expected_sources and not records:
        errors.append("Word asset manifest is empty despite template_spec.json assets.word_media")


def source_metadata_kinds(spec: dict) -> list[str]:
    front_matter = spec.get("front_matter") if isinstance(spec.get("front_matter"), dict) else {}
    metadata_style = front_matter.get("metadata_style") if isinstance(front_matter.get("metadata_style"), dict) else {}
    kind_styles = metadata_style.get("kind_styles") if isinstance(metadata_style.get("kind_styles"), dict) else {}
    return sorted(
        str(kind)
        for kind, value in kind_styles.items()
        if isinstance(value, dict) and str(value.get("evidence_status") or "").lower() in {
            "source", "visible_role_exemplar", "direct_paragraph", "direct_run"
        }
    )


def validate_metadata_skeleton(package: Path, spec: dict, main_text: str, errors: list[str]) -> None:
    """Require typed, value-free metadata fields when Word exposes their kinds."""
    kinds = source_metadata_kinds(spec)
    if not kinds:
        return
    metadata_path = package / "metadata.tex"
    if not metadata_path.is_file():
        errors.append("Source-backed metadata kinds require metadata.tex")
        return
    try:
        metadata_text = metadata_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"metadata.tex could not be read as UTF-8: {exc}")
        return
    if not metadata_text.strip():
        errors.append("metadata.tex must not be empty when source-backed metadata kinds exist")
    missing_kinds = [kind for kind in kinds if kind not in metadata_text]
    if missing_kinds:
        errors.append("metadata.tex is missing typed source metadata fields: " + ", ".join(missing_kinds))
    if not re.search(r"(?m)^\s*%\s*\\input\{(?:\./)?metadata\.tex\}", main_text):
        errors.append("main.tex must retain a commented metadata.tex input skeleton for source-backed metadata")


def system_format_triage_required(ledger: dict | None) -> bool:
    """Return whether a readable Word ledger contains system-level review evidence."""
    objects = ledger.get("objects") if isinstance(ledger, dict) else None
    if not isinstance(objects, dict):
        return False
    checks = (
        ("text_grid_evidence", "present"),
        ("tab_stop_evidence", None),
        ("paragraph_break_policy_evidence", "observed"),
        ("character_effect_evidence", None),
        ("character_style_evidence", None),
        ("script_language_evidence", "observed"),
        ("theme_format_evidence", "present"),
        ("unmodeled_format_properties", "properties"),
    )
    for key, field in checks:
        value = objects.get(key)
        if field is None and isinstance(value, list) and value:
            return True
        if field is not None and isinstance(value, dict) and value.get(field):
            return True
    return False


def contains_cjk_fixture(text: str) -> bool:
    """Return whether a compiled fixture exercises common Han text ranges.

    An engine declaration alone does not prove that a Chinese or mixed-language
    package can typeset the source script. The ordinary package fixture must
    contain real CJK text in main.tex, where the declared document workflow
    compiles it rather than leaving it in an unused asset or comment.
    """
    return any("\u3400" <= char <= "\u4dbf" or "\u4e00" <= char <= "\u9fff" for char in text)


def strip_latex_comments(text: str) -> str:
    """Remove unescaped percent comments before checking exercised TeX paths."""
    cleaned: list[str] = []
    for line in text.splitlines():
        for index, char in enumerate(line):
            if char != "%":
                continue
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                line = line[:index]
                break
        cleaned.append(line)
    return "\n".join(cleaned)


def validate_legacy_conversion_contract(package: Path, ledger: dict | None, errors: list[str]) -> None:
    """Keep a legacy Word inspection conversion reproducible and auditable."""
    source_conversion = ledger.get("source_conversion") if isinstance(ledger, dict) else None
    if not isinstance(source_conversion, dict) or source_conversion.get("status") != "converted_for_inspection":
        return
    source_hash = str(source_conversion.get("source_sha256") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", source_hash):
        errors.append("Legacy Word source conversion must record the original source_sha256")
    derived = source_conversion.get("derived_docx") if isinstance(source_conversion.get("derived_docx"), dict) else {}
    relative = str(derived.get("package_relative_path") or "").strip().replace("\\", "/")
    expected_hash = str(derived.get("sha256") or "").lower()
    candidate = Path(relative)
    if (
        not derived.get("retained")
        or not relative
        or candidate.is_absolute()
        or ".." in candidate.parts
        or candidate.suffix.lower() != ".docx"
    ):
        errors.append("Legacy Word source inspection requires a retained derived DOCX inside the package")
        return
    derived_path = package / candidate
    if not derived_path.is_file():
        errors.append("Legacy Word source derived DOCX is missing from the recorded package path")
        return
    actual_hash = hashlib.sha256(derived_path.read_bytes()).hexdigest()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash) or actual_hash != expected_hash:
        errors.append("Legacy Word source derived DOCX hash does not match word_format_ledger.json")


def validate_word_atomic_contract(package: Path, coverage: dict | None, errors: list[str]) -> None:
    """Enforce the normal-delivery ledger gate for readable Word sources."""
    ledger_path = package / "word_format_ledger.json"
    triage_path = package / "system_format_triage.json"
    decisions_path = package / "atomic_mapping_decisions.json"
    audit_path = package / "atomic_mapping_audit.json"
    ledger: dict | None = None
    triage: dict | None = None
    audit: dict | None = None
    for path, label in ((ledger_path, "word_format_ledger.json"), (decisions_path, "atomic_mapping_decisions.json"), (audit_path, "atomic_mapping_audit.json")):
        if not path.is_file():
            errors.append(f"Word source evidence requires {label}")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{label} is not valid UTF-8 JSON: {exc}")
            continue
        if label == "word_format_ledger.json":
            ledger = data if isinstance(data, dict) else None
            if not isinstance(ledger, dict) or ledger.get("schema_version") != "temp2tex.word-format-ledger.v3":
                errors.append("word_format_ledger.json has an unsupported schema_version")
        elif label == "atomic_mapping_decisions.json":
            if not isinstance(data, dict) or data.get("schema_version") != "temp2tex.atomic-mapping-decisions.v1":
                errors.append("atomic_mapping_decisions.json has an unsupported schema_version")
        else:
            audit = data if isinstance(data, dict) else None
            if not isinstance(audit, dict) or audit.get("schema_version") != "temp2tex.atomic-mapping-audit.v1":
                errors.append("atomic_mapping_audit.json has an unsupported schema_version")

    if system_format_triage_required(ledger):
        if not triage_path.is_file():
            errors.append("Word system-format evidence requires system_format_triage.json before ordinary delivery")
        else:
            try:
                triage_data = json.loads(triage_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"system_format_triage.json is not valid UTF-8 JSON: {exc}")
            else:
                triage = triage_data if isinstance(triage_data, dict) else None
                if not isinstance(triage, dict) or triage.get("schema_version") != "temp2tex.system-format-triage.v2":
                    errors.append("system_format_triage.json has an unsupported schema_version")
                elif not isinstance(triage.get("records"), list) or not triage.get("records"):
                    errors.append("system_format_triage.json must contain one or more system-evidence records")
                elif triage.get("ledger_fingerprint") != ledger.get("evidence_fingerprint"):
                    errors.append("system_format_triage.json does not match word_format_ledger.json evidence fingerprint")

    ledger_coverage = ledger.get("coverage") if isinstance(ledger, dict) else None
    validate_legacy_conversion_contract(package, ledger, errors)
    if not isinstance(ledger_coverage, dict) or not ledger_coverage.get("all_visible_text_units_captured"):
        errors.append("word_format_ledger.json must record complete visible-text capture before ordinary delivery")
    if isinstance(ledger_coverage, dict) and ledger_coverage.get("capture_limitations"):
        errors.append("word_format_ledger.json has capture limitations; retain the affected items as delivery gaps")
    if not isinstance(ledger_coverage, dict) or ledger_coverage.get("all_observable_object_units_captured") is not True:
        errors.append("word_format_ledger.json must capture observable table structure and drawing placement before ordinary delivery")
    sequence_review = ledger.get("front_matter_sequence_review") if isinstance(ledger, dict) else None
    if not isinstance(sequence_review, dict):
        errors.append("word_format_ledger.json must contain front_matter_sequence_review before ordinary delivery")
    elif sequence_review.get("requires_semantic_confirmation"):
        confirmation_path = package / "front_matter_semantic_confirmation.json"
        confirmation: object = None
        if confirmation_path.is_file():
            try:
                confirmation = json.loads(confirmation_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"front_matter_semantic_confirmation.json is not valid UTF-8 JSON: {exc}")
        errors.extend(front_matter_confirmation_errors(ledger, confirmation))
    if not isinstance(audit, dict) or not audit.get("audit_complete"):
        errors.append("atomic_mapping_audit.json must be complete before ordinary delivery; pending decisions are regression diagnostics only")
    if not isinstance(audit, dict) or not audit.get("fidelity_complete"):
        errors.append("atomic_mapping_audit.json must resolve explicit Word-format gaps before claiming ordinary package fidelity")
    if isinstance(ledger, dict) and isinstance(audit, dict) and audit.get("ledger_fingerprint") != ledger.get("evidence_fingerprint"):
        errors.append("atomic_mapping_audit.json does not match word_format_ledger.json evidence fingerprint")
    if triage is not None and isinstance(audit, dict) and audit.get("system_triage_fingerprint") != system_triage_fingerprint(triage):
        errors.append("atomic_mapping_audit.json does not match the current system_format_triage.json child decisions; rerun strict atomic audit")
    summary = coverage.get("summary") if isinstance(coverage, dict) else None
    if not isinstance(summary, dict):
        errors.append("ledger-backed source_feature_coverage.json must contain a summary")
    else:
        if summary.get("ledger_source_capture_complete") is not True:
            errors.append("source_feature_coverage.json must confirm ledger source capture before ordinary delivery")
        if summary.get("atomic_mapping_audit_complete") is not True:
            errors.append("source_feature_coverage.json must confirm completed atomic mapping audit before ordinary delivery")
        if summary.get("atomic_mapping_audit_matches_ledger") is not True:
            errors.append("source_feature_coverage.json must confirm that the atomic audit matches the copied Word ledger")


def validate_spec_contract(spec: dict, errors: list[str], warnings: list[str]) -> None:
    """Check that an editable package retains the decisions an agent needs.

    This deliberately validates structure and provenance, rather than trying
    to decide whether a journal rule is visually correct.  A sparse Word
    template is still a valid input; missing official evidence belongs in the
    fallback/gap records, not in a silently incomplete specification.
    """
    for section in REQUIRED_SPEC_SECTIONS:
        if section not in spec:
            errors.append(f"template_spec.json is missing required section: {section}")

    journal = spec.get("journal")
    language = journal.get("language") if isinstance(journal, dict) else None
    if isinstance(journal, dict) and language not in {"en", "zh", "mixed"}:
        errors.append("template_spec.json journal.language must be en, zh, or mixed")

    document = spec.get("document")
    if isinstance(document, dict):
        if document.get("class_strategy") != "cls":
            warnings.append("document.class_strategy is not cls; confirm a legacy fallback is source-backed")
        engine = str(document.get("engine") or "").strip()
        if not engine:
            errors.append("template_spec.json document.engine is missing")
        elif language in {"zh", "mixed"} and engine.lower().replace(" ", "") != "xelatex":
            errors.append("template_spec.json document.engine must be xelatex for zh or mixed sources")

    page = spec.get("page")
    margins = page.get("margins_mm") if isinstance(page, dict) else None
    if not isinstance(margins, dict) or any(not isinstance(margins.get(side), (int, float)) for side in ("top", "right", "bottom", "left")):
        errors.append("template_spec.json page.margins_mm must contain numeric top/right/bottom/left values")
    float_evidence = page.get("float_spacing_evidence") if isinstance(page, dict) else None
    if not isinstance(float_evidence, dict):
        errors.append("template_spec.json page.float_spacing_evidence must be an evidence ledger")
    else:
        if float_evidence.get("status") not in {"source", "default"}:
            errors.append("page.float_spacing_evidence.status must be source or default")
        if float_evidence.get("mapping") != "candidate_only":
            errors.append("page.float_spacing_evidence.mapping must remain candidate_only")
        boundaries = float_evidence.get("boundaries")
        if not isinstance(boundaries, list):
            errors.append("page.float_spacing_evidence.boundaries must be a list")
            boundaries = []
        eligible_values = []
        for index, boundary in enumerate(boundaries, start=1):
            if not isinstance(boundary, dict) or boundary.get("kind") not in {"table", "figure"} or boundary.get("side") not in {"before", "after"}:
                errors.append(f"page.float_spacing_evidence.boundaries[{index}] must identify table/figure and before/after")
                continue
            side = boundary.get("side")
            role = boundary.get("preceding_role") if side == "before" else boundary.get("following_role")
            if not str(role or "").strip():
                errors.append(f"page.float_spacing_evidence.boundaries[{index}] must classify the outside paragraph role")
            if "emit once" not in str(boundary.get("rule") or ""):
                errors.append(f"page.float_spacing_evidence.boundaries[{index}] must document single emission")
            if role == "body_text_candidate" and boundary.get("status") == "source":
                raw_keys = (
                    ("preceding_space_after_twips", "block_space_before_twips")
                    if side == "before"
                    else ("block_space_after_twips", "following_space_before_twips")
                )
                if all(boundary.get(key) is None for key in raw_keys):
                    errors.append(f"page.float_spacing_evidence.boundaries[{index}] source boundary lacks raw Word sides")
                try:
                    eligible_values.append(float(boundary.get("resolved_pt")))
                except (TypeError, ValueError):
                    errors.append(f"page.float_spacing_evidence.boundaries[{index}] has invalid resolved_pt")
        eligible_count = float_evidence.get("eligible_boundary_count")
        if eligible_count != len(eligible_values):
            errors.append("page.float_spacing_evidence.eligible_boundary_count does not match eligible source boundaries")
        if float_evidence.get("status") == "source" and not eligible_values:
            errors.append("source float spacing evidence requires an eligible body-text boundary")
        if float_evidence.get("status") == "default" and eligible_values:
            errors.append("default float spacing evidence cannot contain eligible source boundaries")
        try:
            resolved_float = float(float_evidence.get("resolved_pt"))
            if resolved_float < 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.append("page.float_spacing_evidence.resolved_pt must be nonnegative")
            resolved_float = None
        if eligible_values and resolved_float is not None:
            ordered = sorted(eligible_values)
            middle = len(ordered) // 2
            expected = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2.0
            if abs(resolved_float - expected) > 0.01:
                errors.append("page.float_spacing_evidence.resolved_pt does not match the eligible-boundary median")
    float_calibration = page.get("float_spacing_calibration") if isinstance(page, dict) else None
    if float_calibration is not None:
        if not isinstance(float_calibration, dict):
            errors.append("page.float_spacing_calibration must be an evidence ledger")
        else:
            status = str(float_calibration.get("status") or "").lower()
            if status not in {"render_probe", "render_verified", "verified"}:
                errors.append("page.float_spacing_calibration.status is invalid")
            for field in ("textfloatsep_pt", "intextsep_pt", "dbltextfloatsep_pt"):
                try:
                    value = float(float_calibration.get(field))
                    if not 0 <= value <= 72:
                        raise ValueError
                except (TypeError, ValueError):
                    errors.append(f"page.float_spacing_calibration.{field} must be between 0pt and 72pt")
            if not str(float_calibration.get("source") or "").strip():
                errors.append("page.float_spacing_calibration must record its source")
            if status == "render_probe":
                warnings.append("float spacing remains a render_probe and is not active in ordinary output")
            if status in {"render_verified", "verified"} and not isinstance(float_calibration.get("acceptance"), dict):
                errors.append("render_verified float spacing requires an acceptance ledger")
    abstracts = spec.get("abstracts")
    if isinstance(abstracts, dict):
        if abstracts.get("label_mode") not in {"inline", "separate", "none", "default"}:
            errors.append("template_spec.json abstracts.label_mode must be inline, separate, none, or default")
        if not isinstance(abstracts.get("style"), dict):
            errors.append("template_spec.json abstracts.style must record the abstract content role")
        if abstracts.get("label_mode") in {"inline", "separate", "default"} and not isinstance(abstracts.get("label_style"), dict):
            errors.append("template_spec.json abstracts.label_style must record the visible or default label role")

    front_matter = spec.get("front_matter")
    boundaries = front_matter.get("spacing_boundaries") if isinstance(front_matter, dict) else None
    required_boundaries = {
        "title_to_author", "author_to_affiliation",
        "affiliation_to_abstract", "abstract_to_keywords",
    }
    if not isinstance(boundaries, dict):
        errors.append("template_spec.json front_matter.spacing_boundaries must be an evidence ledger")
    else:
        for name in sorted(required_boundaries):
            boundary = boundaries.get(name)
            if not isinstance(boundary, dict):
                errors.append(f"front_matter.spacing_boundaries.{name} is missing")
                continue
            if boundary.get("status") not in {"source", "default"}:
                errors.append(f"front_matter.spacing_boundaries.{name}.status must be source or default")
            try:
                resolved = float(boundary.get("resolved_pt"))
            except (TypeError, ValueError):
                resolved = -1
            if resolved < 0:
                errors.append(f"front_matter.spacing_boundaries.{name}.resolved_pt must be nonnegative")
            if "emit once" not in str(boundary.get("rule") or ""):
                errors.append(f"front_matter.spacing_boundaries.{name} must document the single-emission rule")

    for kind in ("tables", "figures"):
        area = spec.get(kind)
        layout = area.get("layout_evidence") if isinstance(area, dict) else None
        if isinstance(layout, dict):
            if "placement_mode" in layout or "placement_verified" in layout:
                errors.append(f"{kind}.layout_evidence uses legacy placement verification fields; use placement_calibration")
            calibration = layout.get("placement_calibration")
            if calibration is not None:
                if not isinstance(calibration, dict):
                    errors.append(f"{kind}.layout_evidence.placement_calibration must be an evidence ledger")
                else:
                    status = str(calibration.get("status") or "").lower()
                    if status not in {"render_probe", "render_verified", "verified"}:
                        errors.append(f"{kind}.layout_evidence.placement_calibration.status is invalid")
                    if str(calibration.get("mode") or "").lower() != "nonfloating":
                        errors.append(f"{kind}.layout_evidence.placement_calibration.mode must be nonfloating")
                    if not str(calibration.get("source") or "").strip():
                        errors.append(f"{kind}.layout_evidence.placement_calibration must record its source")
                    if status == "render_probe":
                        warnings.append(f"{kind} placement remains a render_probe and is not active in ordinary output")
                    if status in {"render_verified", "verified"} and not isinstance(calibration.get("acceptance"), dict):
                        errors.append(f"{kind} render_verified placement requires an acceptance ledger")
        spacing = area.get("caption_spacing_evidence") if isinstance(area, dict) else None
        if not isinstance(spacing, dict):
            errors.append(f"template_spec.json {kind}.caption_spacing_evidence must be an evidence ledger")
            continue
        if spacing.get("status") not in {"source", "default"}:
            errors.append(f"{kind}.caption_spacing_evidence.status must be source or default")
        if spacing.get("position") not in {"above", "below"}:
            errors.append(f"{kind}.caption_spacing_evidence.position must be above or below")
        try:
            resolved = float(spacing.get("resolved_pt"))
        except (TypeError, ValueError):
            resolved = -1
        if resolved < 0:
            errors.append(f"{kind}.caption_spacing_evidence.resolved_pt must be nonnegative")
        try:
            outer = float(spacing.get("outer_pt"))
        except (TypeError, ValueError):
            outer = -1
        if outer < 0:
            errors.append(f"{kind}.caption_spacing_evidence.outer_pt must be nonnegative")
        if spacing.get("outer_status") not in {"source", "default"}:
            errors.append(f"{kind}.caption_spacing_evidence.outer_status must be source or default")
        if spacing.get("caption_outer_side") not in {"space_before_twips", "space_after_twips"}:
            errors.append(f"{kind}.caption_spacing_evidence.caption_outer_side must name a Word paragraph side")
        if spacing.get("outer_status") == "source" and spacing.get("caption_outer_twips") is None:
            errors.append(f"{kind}.caption_spacing_evidence source outer status requires caption_outer_twips")
        if "facing-side" not in str(spacing.get("rule") or "") or "emit once" not in str(spacing.get("rule") or ""):
            errors.append(f"{kind}.caption_spacing_evidence must document facing-side selection and single emission")
        if spacing.get("status") == "source" and all(
            spacing.get(key) is None for key in ("caption_facing_twips", "object_facing_twips")
        ):
            errors.append(f"{kind}.caption_spacing_evidence source status requires a measured facing-side value")

    references = spec.get("references")
    evidence = references.get("style_evidence") if isinstance(references, dict) else None
    if not isinstance(evidence, dict) or not str(evidence.get("source") or "").strip():
        warnings.append("references.style_evidence is missing; record whether citation style is official, inferred, or default")

    fallbacks = spec.get("fallbacks")
    if not isinstance(fallbacks, list):
        errors.append("template_spec.json fallbacks must be a list")
    elif not fallbacks:
        warnings.append("template_spec.json has no fallback entries; confirm every missing official rule was considered")
    else:
        for index, fallback in enumerate(fallbacks, start=1):
            if not isinstance(fallback, dict) or not str(fallback.get("area") or "").strip():
                warnings.append(f"fallbacks[{index}] has no area identifier")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", help="Generated Temp2TeX package directory")
    parser.add_argument(
        "--output",
        help="Validation report path; defaults to package_validation.json inside the package directory",
    )
    args = parser.parse_args()
    package = Path(args.package).expanduser().resolve()
    output = Path(args.output).expanduser().resolve() if args.output else package / "package_validation.json"
    errors: list[str] = []
    warnings: list[str] = []
    for name in REQUIRED_FILES:
        if not (package / name).is_file():
            errors.append(f"Missing required file: {name}")
    for name in REQUIRED_DIRECTORIES:
        if not (package / name).is_dir():
            errors.append(f"Missing required directory: {name}/")
    validate_handoff_status(package, errors)

    inventory_path = package / "source_inventory.json"
    inventory: dict | None = None
    if inventory_path.is_file():
        try:
            loaded_inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory = loaded_inventory if isinstance(loaded_inventory, dict) else None
            if inventory is None:
                errors.append("source_inventory.json must contain a JSON object")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"source_inventory.json is not valid UTF-8 JSON: {exc}")
    coverage_path = package / "source_feature_coverage.json"
    coverage: dict | None = None
    structured_word_source = has_word_source(inventory or {})
    if inventory_path.is_file() and structured_word_source and not coverage_path.is_file():
        errors.append("source_inventory.json is present but source_feature_coverage.json is missing")
    if coverage_path.is_file():
        try:
            loaded_coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
            coverage = loaded_coverage if isinstance(loaded_coverage, dict) else None
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"source_feature_coverage.json is not valid UTF-8 JSON: {exc}")
        else:
            summary = coverage.get("summary") if isinstance(coverage, dict) else None
            features = coverage.get("features") if isinstance(coverage, dict) else None
            if coverage.get("schema_version") not in {1, 2, 3}:
                errors.append("source_feature_coverage.json schema_version must be 1, 2, or 3")
            if not isinstance(summary, dict) or not isinstance(features, list):
                errors.append("source_feature_coverage.json must contain summary and features")
            elif not any(item.get("feature") == "run_level_format_spans" for item in features if isinstance(item, dict)):
                errors.append("source_feature_coverage.json must audit run_level_format_spans")
            elif coverage.get("schema_version") == 3 and not any(item.get("feature") == "atomic_mapping_dispositions" for item in features if isinstance(item, dict)):
                errors.append("source_feature_coverage.json schema_version 3 must audit atomic_mapping_dispositions")
    if structured_word_source:
        validate_word_atomic_contract(package, coverage, errors)
    elif inventory_has_recorded_sources(inventory):
        validate_manual_evidence_contract(package, errors)

    spec: dict = {}
    spec_path = package / "template_spec.json"
    if spec_path.exists():
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"template_spec.json is not valid JSON: {exc}")
    if spec and not isinstance(spec.get("journal"), dict):
        errors.append("template_spec.json is missing journal metadata")
    elif spec:
        validate_spec_contract(spec, errors, warnings)
        validate_asset_contract(package, spec, errors, warnings)
    language = spec.get("journal", {}).get("language") if isinstance(spec.get("journal"), dict) else None

    for tex_name in ("main.tex", "journal-template.cls"):
        path = package / tex_name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"__[A-Z][A-Z0-9_]*__", text):
            errors.append(f"Unresolved generator placeholder in {tex_name}")
        if re.search(r"(?:^|[\s{\"'])(?:[A-Za-z]:\\|/Users/|/home/)", text, flags=re.MULTILINE):
            errors.append(f"Absolute local path found in {tex_name}")
        if tex_name == "main.tex":
            exercised_text = strip_latex_comments(text)
            if not DOCUMENT_CLASS_RE.search(exercised_text):
                errors.append("main.tex must load journal-template.cls with \\documentclass")
            if language in {"zh", "mixed"} and not contains_cjk_fixture(exercised_text):
                errors.append("main.tex must exercise visible CJK fixture text for zh or mixed sources")
            if not TITLE_DECLARATION_RE.search(exercised_text) or not TITLE_MAKING_RE.search(exercised_text):
                errors.append("main.tex must exercise editable title declaration and title-making interface")
            if not ABSTRACT_FIXTURE_RE.search(exercised_text):
                errors.append("main.tex must exercise an editable abstract fixture")
            if not HEADING_FIXTURE_RE.search(exercised_text):
                errors.append("main.tex must exercise an editable heading fixture")
            if not TABLE_FIXTURE_RE.search(exercised_text):
                errors.append("main.tex must exercise an editable table fixture")
            if not FIGURE_FIXTURE_RE.search(exercised_text):
                errors.append("main.tex must exercise an editable figure fixture")
            if not EQUATION_FIXTURE_RE.search(exercised_text):
                errors.append("main.tex must exercise an editable equation fixture")
            front_matter = spec.get("front_matter") if isinstance(spec.get("front_matter"), dict) else {}
            if front_matter.get("authors") is not False and not AUTHOR_FIXTURE_RE.search(exercised_text):
                errors.append("main.tex must exercise an editable author fixture")
            if front_matter.get("affiliations") is not False and not AFFILIATION_FIXTURE_RE.search(exercised_text):
                errors.append("main.tex must exercise an editable affiliation fixture")
            abstracts = spec.get("abstracts") if isinstance(spec.get("abstracts"), dict) else {}
            if abstracts.get("keywords") is not False and not KEYWORD_FIXTURE_RE.search(exercised_text):
                errors.append("main.tex must exercise an editable keyword fixture")
            footnotes = spec.get("footnotes") if isinstance(spec.get("footnotes"), dict) else {}
            if footnotes.get("enabled") is not False and not NOTE_FIXTURE_RE.search(exercised_text):
                errors.append("main.tex must exercise an editable footnote or author-note fixture")
            reference_index = exercised_text.find(r"\begin{thebibliography}")
            appendix_index = exercised_text.find(r"\journalappendix")
            has_inline_bibliography = reference_index >= 0 and r"\bibitem" in exercised_text
            has_external_bibliography = r"\bibliography{" in exercised_text or r"\printbibliography" in exercised_text
            if not has_inline_bibliography and not has_external_bibliography:
                errors.append("main.tex must exercise an editable bibliography fixture with an entry or backend")
            if not CITATION_COMMAND_RE.search(exercised_text):
                errors.append("main.tex must exercise an editable citation command")
            if appendix_index < 0:
                errors.append("main.tex must exercise the journalappendix interface")
            if reference_index >= 0 and appendix_index >= 0 and reference_index > appendix_index:
                errors.append("main.tex places the appendix before the reference list")
    main_path = package / "main.tex"
    if spec and main_path.is_file():
        validate_metadata_skeleton(package, spec, main_path.read_text(encoding="utf-8", errors="replace"), errors)
    references_bib = package / "references.bib"
    if references_bib.is_file():
        bib_text = references_bib.read_text(encoding="utf-8", errors="replace")
        if not BIB_ENTRY_RE.search(strip_latex_comments(bib_text)):
            errors.append("references.bib must contain at least one editable BibTeX entry")
    readme = package / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8", errors="replace")
        readme_lower = text.lower()
        if "xelatex" not in readme_lower and "latexmk" not in readme_lower:
            warnings.append("README.md does not state a LaTeX compile command")
        if language in {"zh", "mixed"} and "xelatex" not in readme_lower:
            errors.append("README.md must state an xelatex compile command for zh or mixed sources")
    gaps = package / "format_gap_log.md"
    if gaps.exists() and not gaps.read_text(encoding="utf-8", errors="replace").strip():
        warnings.append("format_gap_log.md is empty; confirm no inferred/default rules were omitted")

    report = {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "package": str(package),
        "package_contract_fingerprint": package_contract_fingerprint(package),
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "required_files": list(REQUIRED_FILES),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
