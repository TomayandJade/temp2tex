#!/usr/bin/env python3
"""Promote a bounded render probe only after strict same-target comparison."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path


ALLOWED_CALIBRATION_PATHS = (
    ("document", "render_calibration"),
    ("page", "render_calibration"),
    ("page", "float_spacing_calibration"),
    ("figures", "layout_evidence", "placement_calibration"),
    ("tables", "layout_evidence", "placement_calibration"),
    ("statements", "layout_evidence", "boundary_calibration"),
    ("appendices", "layout_evidence", "boundary_calibration"),
)

PLACEMENT_CALIBRATION_PATHS = {
    ("figures", "layout_evidence", "placement_calibration"),
    ("tables", "layout_evidence", "placement_calibration"),
}

FLOAT_SPACING_CALIBRATION_PATH = ("page", "float_spacing_calibration")
APPENDIX_BOUNDARY_CALIBRATION_PATH = ("appendices", "layout_evidence", "boundary_calibration")
BACKMATTER_BOUNDARY_CALIBRATION_PATH = ("statements", "layout_evidence", "boundary_calibration")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def nested(data: dict, path: tuple[str, ...], default=None):
    current = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def remove_path(data: dict, path: tuple[str, ...]) -> None:
    current = data
    parents: list[tuple[dict, str]] = []
    for key in path[:-1]:
        parents.append((current, key))
        current = current.get(key)
        if not isinstance(current, dict):
            return
    current.pop(path[-1], None)
    for parent, key in reversed(parents):
        child = parent.get(key)
        if isinstance(child, dict) and not child:
            parent.pop(key, None)
        else:
            break


def comparison_metrics(report: dict) -> dict:
    values = [
        float(item["diff"]["normalized_diff"])
        for item in report.get("comparisons", [])
        if isinstance(item, dict)
        and isinstance(item.get("diff"), dict)
        and isinstance(item["diff"].get("normalized_diff"), (int, float))
    ]
    return {
        "page_count": len(report.get("generated_pages", [])),
        "reference_page_count": len(report.get("reference_pages", [])),
        "average_normalized_diff": sum(values) / len(values) if values else None,
        "max_normalized_diff": max(values) if values else None,
        "comparison_page_count": len(values),
    }


def page_sizes_match(report: dict, tolerance_pt: float = 0.5) -> bool:
    reference = report.get("reference_pages", [])
    generated = report.get("generated_pages", [])
    if len(reference) != len(generated) or not reference:
        return False
    for ref, gen in zip(reference, generated):
        try:
            if abs(float(ref["width_pt"]) - float(gen["width_pt"])) > tolerance_pt:
                return False
            if abs(float(ref["height_pt"]) - float(gen["height_pt"])) > tolerance_pt:
                return False
        except (KeyError, TypeError, ValueError):
            return False
    return True


def normalized_path(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    try:
        return str(Path(value).expanduser().resolve()).lower()
    except OSError:
        return value.strip().lower()


def summary_metrics(diagnostics: dict) -> dict:
    summary = diagnostics.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    width = summary.get("median_body_box_delta_pt", {})
    cause_scores = summary.get("cause_scores", {})
    return {
        "layout_penalty": summary.get("layout_penalty"),
        "anchor_page_shifts": summary.get("anchor_page_shifts", {}),
        "missing_or_asymmetric_anchors": summary.get("missing_or_asymmetric_anchors", []),
        "median_body_box_width_delta_pt": width.get("width") if isinstance(width, dict) else None,
        "float_layout_score": cause_scores.get("table_figure_caption_or_float") if isinstance(cause_scores, dict) else None,
        "structural_flow_score": cause_scores.get("pagination_or_structural_flow") if isinstance(cause_scores, dict) else None,
        "body_density_score": cause_scores.get("body_density") if isinstance(cause_scores, dict) else None,
    }


def finite_number(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None


def evidence_record(path: Path) -> dict:
    return {
        "file": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def evaluate(
    original_spec: dict,
    candidate_spec: dict,
    ordinary_compare: dict,
    candidate_compare: dict,
    ordinary_layout: dict,
    candidate_layout: dict,
    candidate_compile: dict,
    minimum_improvement: float,
) -> dict:
    reasons: list[str] = []
    original_without = copy.deepcopy(original_spec)
    candidate_without = copy.deepcopy(candidate_spec)
    active_paths = []
    for path in ALLOWED_CALIBRATION_PATHS:
        calibration = nested(candidate_spec, path)
        if isinstance(calibration, dict) and str(calibration.get("status", "")).lower() == "render_probe":
            active_paths.append(path)
        remove_path(original_without, path)
        remove_path(candidate_without, path)
    if not active_paths:
        reasons.append("Candidate contains no allowed calibration with status render_probe.")
    active_placement_paths = [path for path in active_paths if path in PLACEMENT_CALIBRATION_PATHS]
    active_float_spacing_paths = [path for path in active_paths if path == FLOAT_SPACING_CALIBRATION_PATH]
    active_appendix_boundary_paths = [path for path in active_paths if path == APPENDIX_BOUNDARY_CALIBRATION_PATH]
    active_backmatter_boundary_paths = [path for path in active_paths if path == BACKMATTER_BOUNDARY_CALIBRATION_PATH]
    if (active_placement_paths or active_float_spacing_paths) and len(active_paths) != 1:
        reasons.append("A float placement/spacing probe must change exactly one calibration path.")
    if active_appendix_boundary_paths and len(active_paths) != 1:
        reasons.append("An appendix boundary probe must change exactly one calibration path.")
    if active_backmatter_boundary_paths and len(active_paths) != 1:
        reasons.append("A backmatter boundary probe must change exactly one calibration path.")
    for path in active_placement_paths:
        calibration = nested(candidate_spec, path, {})
        if str(calibration.get("mode", "")).lower() != "nonfloating":
            reasons.append(f"{'.'.join(path)}.mode must be nonfloating.")
        if not str(calibration.get("source", "")).strip():
            reasons.append(f"{'.'.join(path)} must record its source rationale.")
        if path[0] == "figures":
            drawing_type = nested(original_spec, ("figures", "layout_evidence", "drawing_type"), "")
            if str(drawing_type).lower() != "inline":
                reasons.append("A nonfloating figure probe requires an inline Word drawing candidate.")
        elif not isinstance(nested(original_spec, ("tables", "layout_evidence")), dict):
            reasons.append("A nonfloating table probe requires Word table layout evidence.")
    for path in active_float_spacing_paths:
        calibration = nested(candidate_spec, path, {})
        if not str(calibration.get("source", "")).strip():
            reasons.append("Float spacing calibration must record its source rationale.")
        evidence = nested(original_spec, ("page", "float_spacing_evidence"), {})
        if not isinstance(evidence, dict) or evidence.get("status") != "source":
            reasons.append("Float spacing promotion requires source-backed Word object/text boundaries.")
        for field in ("textfloatsep_pt", "intextsep_pt", "dbltextfloatsep_pt"):
            value = finite_number(calibration.get(field))
            if value is None or not 0 <= value <= 72:
                reasons.append(f"page.float_spacing_calibration.{field} must be between 0pt and 72pt.")
    for path in active_appendix_boundary_paths:
        calibration = nested(candidate_spec, path, {})
        if str(calibration.get("mode", "")).lower() != "new_page":
            reasons.append("Appendix boundary calibration mode must be new_page.")
        if not str(calibration.get("source", "")).strip():
            reasons.append("Appendix boundary calibration must record its rendered diagnostic rationale.")
    for path in active_backmatter_boundary_paths:
        calibration = nested(candidate_spec, path, {})
        if str(calibration.get("mode", "")).lower() != "new_page":
            reasons.append("Backmatter boundary calibration mode must be new_page.")
        if not str(calibration.get("source", "")).strip():
            reasons.append("Backmatter boundary calibration must record its rendered diagnostic rationale.")
    page_calibration = nested(candidate_spec, ("page", "render_calibration"), {})
    body_parskip_active = (
        isinstance(page_calibration, dict)
        and str(page_calibration.get("status", "")).lower() == "render_probe"
        and "body_parskip_pt" in page_calibration
    )
    if body_parskip_active:
        body_parskip = finite_number(page_calibration.get("body_parskip_pt"))
        if body_parskip is None or not 0 <= body_parskip <= 72:
            reasons.append("page.render_calibration.body_parskip_pt must be between 0pt and 72pt.")
        if not str(page_calibration.get("source", "")).strip():
            reasons.append("Body paragraph-spacing calibration must record its Word source rationale.")
    if original_without != candidate_without:
        reasons.append("Candidate changes fields outside the allowed render_calibration paths.")
    if candidate_compile.get("success") is not True:
        reasons.append("Candidate compile report is not successful.")

    ordinary_reference = normalized_path(ordinary_compare.get("reference_pdf"))
    candidate_reference = normalized_path(candidate_compare.get("reference_pdf"))
    if not ordinary_reference or ordinary_reference != candidate_reference:
        reasons.append("Ordinary and candidate comparisons do not use the same reference PDF.")
    ordinary = comparison_metrics(ordinary_compare)
    candidate = comparison_metrics(candidate_compare)
    page_count_repair = (
        ordinary["page_count"] != ordinary["reference_page_count"]
        and candidate["page_count"] == candidate["reference_page_count"]
    )
    document_calibration = nested(candidate_spec, ("document", "render_calibration"), {})
    body_density_page_repair = (
        isinstance(document_calibration, dict)
        and str(document_calibration.get("status", "")).lower() == "render_probe"
        and str(document_calibration.get("proposal_mode", "")).lower() == "body_density_page_count_repair"
    )
    if body_density_page_repair and not page_count_repair:
        reasons.append("A body-density page-count repair candidate must actually repair the reference page count.")
    ordinary_issues = ordinary_compare.get("issues") or []
    ordinary_page_count_issues_only = bool(ordinary_issues) and all(
        str(issue).startswith("Page count differs:") for issue in ordinary_issues
    )
    if ordinary_issues and not (page_count_repair and ordinary_page_count_issues_only):
        reasons.append("Ordinary comparison reports unresolved non-pagination issues.")
    if candidate_compare.get("issues"):
        reasons.append("Candidate comparison reports unresolved rendering issues.")
    if candidate["page_count"] != candidate["reference_page_count"]:
        reasons.append("Candidate page count differs from the reference.")
    if not page_count_repair and candidate["page_count"] != ordinary["page_count"]:
        reasons.append("Candidate changes the ordinary package page count.")
    if not page_count_repair and not page_sizes_match(ordinary_compare):
        reasons.append("Ordinary package page size differs from the reference.")
    if not page_sizes_match(candidate_compare):
        reasons.append("Candidate page size differs from the reference.")
    ordinary_mean = finite_number(ordinary["average_normalized_diff"])
    candidate_mean = finite_number(candidate["average_normalized_diff"])
    ordinary_max = finite_number(ordinary["max_normalized_diff"])
    candidate_max = finite_number(candidate["max_normalized_diff"])
    if ordinary_mean is None or candidate_mean is None:
        reasons.append("Comparable normalized visual differences are unavailable.")
    elif page_count_repair and candidate_mean > ordinary_mean + 0.02:
        reasons.append("Page-count repair worsens mean visual difference by more than 0.02.")
    elif not page_count_repair and ordinary_mean - candidate_mean < minimum_improvement:
        reasons.append(
            f"Mean visual improvement {ordinary_mean - candidate_mean:.6f} is below the required {minimum_improvement:.6f}."
        )
    if ordinary_max is None or candidate_max is None:
        reasons.append("Maximum normalized visual differences are unavailable.")
    elif page_count_repair and candidate_max > ordinary_max + 0.01:
        reasons.append("Page-count repair worsens maximum page difference by more than 0.01.")
    elif not page_count_repair and candidate_max > ordinary_max + 0.001:
        reasons.append("Candidate maximum page difference is materially worse.")

    ordinary_summary = summary_metrics(ordinary_layout)
    candidate_summary = summary_metrics(candidate_layout)
    appendix_boundary_active = bool(active_appendix_boundary_paths)
    backmatter_boundary_active = bool(active_backmatter_boundary_paths)
    if appendix_boundary_active:
        ordinary_shifts = ordinary_summary["anchor_page_shifts"] or {}
        if set(ordinary_shifts) != {"appendix"} or not ordinary_shifts.get("appendix"):
            reasons.append("Appendix boundary promotion requires appendix to be the ordinary output's only shifted anchor page.")
    if backmatter_boundary_active:
        ordinary_shifts = ordinary_summary["anchor_page_shifts"] or {}
        allowed = {"acknowledgements", "data_availability", "references", "appendix"}
        if not {"references", "appendix"}.issubset(ordinary_shifts) or not set(ordinary_shifts).issubset(allowed):
            reasons.append("Backmatter boundary promotion requires only backmatter anchors to shift, including references and appendix.")
        shift_values = {finite_number(value) for value in ordinary_shifts.values()}
        if None in shift_values or len(shift_values) != 1:
            reasons.append("Backmatter anchors must share one page-shift direction and magnitude.")
        if ordinary["page_count"] >= ordinary["reference_page_count"]:
            reasons.append("Backmatter new-page repair requires generated output to be shorter than the reference.")
    ordinary_penalty = finite_number(ordinary_summary["layout_penalty"])
    candidate_penalty = finite_number(candidate_summary["layout_penalty"])
    if ordinary_penalty is None or candidate_penalty is None:
        reasons.append("Layout penalty is unavailable for ordinary or candidate output.")
    elif page_count_repair and appendix_boundary_active and candidate_penalty > ordinary_penalty + 0.1:
        reasons.append("Appendix page-count repair worsens layout penalty by more than 0.1.")
    elif page_count_repair and not appendix_boundary_active and candidate_penalty >= ordinary_penalty - 0.001:
        reasons.append("Page-count repair does not improve layout penalty.")
    elif not page_count_repair and candidate_penalty > ordinary_penalty + 0.001:
        reasons.append("Candidate layout penalty is worse than the ordinary package.")
    if candidate_summary["anchor_page_shifts"]:
        reasons.append("Candidate introduces or retains document anchor page shifts.")
    ordinary_missing = set(ordinary_summary["missing_or_asymmetric_anchors"] or [])
    candidate_missing = set(candidate_summary["missing_or_asymmetric_anchors"] or [])
    if not candidate_missing.issubset(ordinary_missing):
        reasons.append("Candidate introduces missing or asymmetric document anchors.")
    ordinary_width = finite_number(ordinary_summary["median_body_box_width_delta_pt"])
    candidate_width = finite_number(candidate_summary["median_body_box_width_delta_pt"])
    body_box_calibration_active = any(path == ("document", "render_calibration") for path in active_paths) or (
        ("page", "render_calibration") in active_paths and not body_parskip_active
    )
    if body_box_calibration_active and body_density_page_repair:
        if ordinary_width is not None and candidate_width is not None and abs(candidate_width) > abs(ordinary_width) + 0.5:
            reasons.append("Body-density page repair worsens the pre-existing body-box width mismatch.")
    elif body_box_calibration_active and candidate_width is not None and abs(candidate_width) > 12.0:
        reasons.append("Candidate body-box width differs from the reference by more than 12pt.")
    elif ordinary_width is not None and candidate_width is not None and abs(candidate_width) > abs(ordinary_width) + 4.0:
        reasons.append("Candidate materially worsens body-box width alignment.")
    ordinary_float = finite_number(ordinary_summary["float_layout_score"])
    candidate_float = finite_number(candidate_summary["float_layout_score"])
    if active_placement_paths or active_float_spacing_paths:
        if ordinary_float is None or candidate_float is None:
            reasons.append("Placement promotion requires the table/figure/caption/float diagnostic score.")
        elif candidate_float > ordinary_float + 0.001:
            reasons.append("Placement candidate worsens the table/figure/caption/float diagnostic score.")
    if appendix_boundary_active:
        ordinary_structural = finite_number(ordinary_summary["structural_flow_score"])
        candidate_structural = finite_number(candidate_summary["structural_flow_score"])
        if ordinary_structural is None or candidate_structural is None:
            reasons.append("Appendix boundary promotion requires the structural-flow diagnostic score.")
        elif candidate_structural >= ordinary_structural - 0.001:
            reasons.append("Appendix boundary candidate does not improve the structural-flow diagnostic score.")
    if backmatter_boundary_active:
        ordinary_structural = finite_number(ordinary_summary["structural_flow_score"])
        candidate_structural = finite_number(candidate_summary["structural_flow_score"])
        if ordinary_structural is None or candidate_structural is None:
            reasons.append("Backmatter boundary promotion requires the structural-flow diagnostic score.")
        elif candidate_structural >= ordinary_structural - 0.001:
            reasons.append("Backmatter boundary candidate does not improve the structural-flow diagnostic score.")
        if ordinary_mean is None or candidate_mean is None or candidate_mean >= ordinary_mean - 0.0001:
            reasons.append("Backmatter boundary candidate does not improve mean visual difference.")
    if body_density_page_repair:
        ordinary_density = finite_number(ordinary_summary["body_density_score"])
        candidate_density = finite_number(candidate_summary["body_density_score"])
        if ordinary_density is None or candidate_density is None:
            reasons.append("Body-density page repair requires the body-density diagnostic score.")
        elif candidate_density >= ordinary_density - 0.001:
            reasons.append("Body-density page repair does not improve the body-density diagnostic score.")

    return {
        "accepted": not reasons,
        "status": "accepted" if not reasons else "rejected",
        "promotion_mode": "page_count_repair" if page_count_repair else "stable_visual_calibration",
        "reasons": reasons,
        "active_calibration_paths": [".".join(path) for path in active_paths],
        "ordinary_metrics": {**ordinary, **ordinary_summary},
        "candidate_metrics": {**candidate, **candidate_summary},
        "minimum_mean_improvement": minimum_improvement,
        "reference_pdf": candidate_compare.get("reference_pdf"),
        "generated_pdf": candidate_compare.get("generated_pdf"),
    }


def promoted_spec(original: dict, candidate: dict, report: dict, evidence_records: dict) -> dict:
    result = copy.deepcopy(original)
    for path in ALLOWED_CALIBRATION_PATHS:
        calibration = nested(candidate, path)
        if not isinstance(calibration, dict) or str(calibration.get("status", "")).lower() != "render_probe":
            continue
        verified = copy.deepcopy(calibration)
        verified["status"] = "render_verified"
        proposal_path = verified.pop("proposal_path", None)
        if isinstance(proposal_path, str) and proposal_path:
            verified["proposal_file"] = Path(proposal_path).name
        verified["acceptance"] = {
            "source": "strict same-target render-probe promotion gate",
            "ordinary_metrics": report["ordinary_metrics"],
            "candidate_metrics": report["candidate_metrics"],
            "reference_pdf": Path(str(report["reference_pdf"])).name,
            "generated_pdf": Path(str(report["generated_pdf"])).name,
            "evidence": evidence_records,
        }
        owner = result
        for key in path[:-1]:
            owner = owner.setdefault(key, {})
        owner[path[-1]] = verified
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_spec")
    parser.add_argument("candidate_spec")
    parser.add_argument("--ordinary-compare", required=True)
    parser.add_argument("--candidate-compare", required=True)
    parser.add_argument("--ordinary-layout", required=True)
    parser.add_argument("--candidate-layout", required=True)
    parser.add_argument("--candidate-compile", required=True)
    parser.add_argument("--output", required=True, help="Verified spec; written only when accepted")
    parser.add_argument("--report", required=True)
    parser.add_argument("--minimum-improvement", type=float, default=0.0001)
    args = parser.parse_args()
    paths = {name: Path(value).expanduser().resolve() for name, value in {
        "original_spec": args.original_spec,
        "candidate_spec": args.candidate_spec,
        "ordinary_compare": args.ordinary_compare,
        "candidate_compare": args.candidate_compare,
        "ordinary_layout": args.ordinary_layout,
        "candidate_layout": args.candidate_layout,
        "candidate_compile": args.candidate_compile,
        "output": args.output,
        "report": args.report,
    }.items()}
    original = read_json(paths["original_spec"])
    candidate = read_json(paths["candidate_spec"])
    report = evaluate(
        original,
        candidate,
        read_json(paths["ordinary_compare"]),
        read_json(paths["candidate_compare"]),
        read_json(paths["ordinary_layout"]),
        read_json(paths["candidate_layout"]),
        read_json(paths["candidate_compile"]),
        max(0.0, args.minimum_improvement),
    )
    report["evidence_paths"] = {key: str(value) for key, value in paths.items() if key not in {"output", "report"}}
    paths["report"].parent.mkdir(parents=True, exist_ok=True)
    paths["report"].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["accepted"]:
        portable_records = {
            key: evidence_record(value)
            for key, value in paths.items()
            if key in {
                "original_spec", "candidate_spec", "ordinary_compare",
                "candidate_compare", "ordinary_layout", "candidate_layout",
                "candidate_compile",
            }
        }
        verified = promoted_spec(original, candidate, report, portable_records)
        paths["output"].parent.mkdir(parents=True, exist_ok=True)
        paths["output"].write_text(json.dumps(verified, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(paths["output"])
        return 0
    if paths["output"].exists():
        paths["output"].unlink()
    print(paths["report"])
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
