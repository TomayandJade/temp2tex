#!/usr/bin/env python3
"""Validate the ordinary Temp2TeX package contract without requiring PDF tools."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_FILES = (
    "main.tex",
    "journal-template.cls",
    "references.bib",
    "template_spec.json",
    "format_gap_log.md",
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
    if isinstance(journal, dict) and journal.get("language") not in {"en", "zh", "mixed"}:
        errors.append("template_spec.json journal.language must be en, zh, or mixed")

    document = spec.get("document")
    if isinstance(document, dict):
        if document.get("class_strategy") != "cls":
            warnings.append("document.class_strategy is not cls; confirm a legacy fallback is source-backed")
        if not str(document.get("engine") or "").strip():
            errors.append("template_spec.json document.engine is missing")

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
    parser.add_argument("--output", default="package_validation.json")
    args = parser.parse_args()
    package = Path(args.package).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    for name in REQUIRED_FILES:
        if not (package / name).is_file():
            errors.append(f"Missing required file: {name}")
    for name in REQUIRED_DIRECTORIES:
        if not (package / name).is_dir():
            errors.append(f"Missing required directory: {name}/")

    inventory_path = package / "source_inventory.json"
    coverage_path = package / "source_feature_coverage.json"
    if inventory_path.is_file() and not coverage_path.is_file():
        errors.append("source_inventory.json is present but source_feature_coverage.json is missing")
    if coverage_path.is_file():
        try:
            coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"source_feature_coverage.json is not valid UTF-8 JSON: {exc}")
        else:
            summary = coverage.get("summary") if isinstance(coverage, dict) else None
            features = coverage.get("features") if isinstance(coverage, dict) else None
            if coverage.get("schema_version") not in {1, 2}:
                errors.append("source_feature_coverage.json schema_version must be 1 or 2")
            if not isinstance(summary, dict) or not isinstance(features, list):
                errors.append("source_feature_coverage.json must contain summary and features")
            elif not any(item.get("feature") == "run_level_format_spans" for item in features if isinstance(item, dict)):
                errors.append("source_feature_coverage.json must audit run_level_format_spans")

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
            reference_index = text.find(r"\begin{thebibliography}")
            appendix_index = text.find(r"\journalappendix")
            if reference_index < 0:
                errors.append("main.tex must exercise an editable bibliography fixture")
            if appendix_index < 0:
                errors.append("main.tex must exercise the journalappendix interface")
            if reference_index >= 0 and appendix_index >= 0 and reference_index > appendix_index:
                errors.append("main.tex places the appendix before the reference list")
    readme = package / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8", errors="replace")
        if "xelatex" not in text.lower() and "latexmk" not in text.lower():
            warnings.append("README.md does not state a LaTeX compile command")
    gaps = package / "format_gap_log.md"
    if gaps.exists() and not gaps.read_text(encoding="utf-8", errors="replace").strip():
        warnings.append("format_gap_log.md is empty; confirm no inferred/default rules were omitted")

    report = {
        "package": str(package),
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
