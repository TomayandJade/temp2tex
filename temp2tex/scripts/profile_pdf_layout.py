#!/usr/bin/env python3
"""Profile two PDFs by text geometry so visual failures have a cause."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


ANCHOR_PROFILE_VERSION = "stress-body-unique-v10"

ANCHORS = {
    "title": ["Temp2TeX Regression Benchmark", "Template Fidelity Across Journal Formats"],
    "abstract": ["This benchmark manuscript is intentionally"],
    "keywords": ["template conversion"],
    "introduction": ["Introduction"],
    "methods": ["Methods"],
    "table": ["Regression table with a note and a merged cell"],
    "figure": ["Single-panel"],
    "acknowledgements": ["The authors thank the template maintainers"],
    "data_availability": ["All data in this manuscript are placeholders"],
    "references": ["Template regression testing"],
    "appendix": ["Appendix Regression Checks"],
}


def load_anchor_map(path: Path) -> tuple[dict[str, list[str]], str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise ValueError("anchor map must be a non-empty JSON object")
    anchors: dict[str, list[str]] = {}
    for name, value in raw.items():
        needles = [value] if isinstance(value, str) else value
        if not isinstance(name, str) or not name.strip() or not isinstance(needles, list):
            raise ValueError("each anchor must map a non-empty name to a string or string list")
        cleaned = [item.strip() for item in needles if isinstance(item, str) and item.strip()]
        if not cleaned:
            raise ValueError(f"anchor {name!r} has no usable phrases")
        anchors[name.strip()] = cleaned
    digest = hashlib.sha256(json.dumps(anchors, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
    return anchors, f"custom-{digest}"


def normalized_match_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    for codepoint in (0x00AD, 0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015, 0x2212):
        text = text.replace(chr(codepoint), "-")
    return " ".join(text.split())


def horizontal_gap(first: list[float], second: list[float]) -> float:
    if first[2] < second[0]:
        return float(second[0] - first[2])
    if second[2] < first[0]:
        return float(first[0] - second[2])
    return 0.0


def semantic_anchor_hits(lines: list[dict], needles: list[str], max_parts: int = 12, max_scan: int = 48) -> list[dict]:
    """Find unique phrases across wrapped lines while skipping another column."""
    normalized_needles = [normalized_match_text(needle) for needle in needles]
    hits = []
    for start, first in enumerate(lines):
        window = [first]
        lane_box = list(first["bbox"])
        last_top = float(first["bbox"][1])
        combined = normalized_match_text(first["text"])
        for end in range(start, min(len(lines), start + max_scan)):
            if any(needle in combined for needle in normalized_needles):
                hits.append({
                    "text": " ".join(item["text"] for item in window)[:160],
                    "bbox": bbox_union([item["bbox"] for item in window]),
                    "line_count": len(window),
                })
                break
            if end == start or len(window) >= max_parts:
                continue
            current = lines[end]
            top_step = float(current["bbox"][1]) - last_top
            if top_step > 48:
                break
            if top_step < -2:
                continue
            lane_center = (float(lane_box[0]) + float(lane_box[2])) / 2
            current_center = (float(current["bbox"][0]) + float(current["bbox"][2])) / 2
            center_distance = abs(current_center - lane_center)
            same_baseline_fragment = abs(top_step) <= 2 and horizontal_gap(lane_box, current["bbox"]) <= 50
            wrapped_line = 2 < top_step <= 48 and (
                horizontal_overlap_ratio(lane_box, current["bbox"]) >= 0.15 or center_distance <= 120
            )
            if not (same_baseline_fragment or wrapped_line):
                continue
            window.append(current)
            lane_box = bbox_union([lane_box, current["bbox"]]) or lane_box
            last_top = float(current["bbox"][1])
            combined = normalized_match_text(" ".join(item["text"] for item in window))
            if any(needle in combined for needle in normalized_needles):
                hits.append({
                    "text": " ".join(item["text"] for item in window)[:160],
                    "bbox": bbox_union([item["bbox"] for item in window]),
                    "line_count": len(window),
                })
                break
    return hits


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def bbox_union(boxes: list[list[float]]) -> list[float] | None:
    if not boxes:
        return None
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]


def bbox_delta(a: list[float] | None, b: list[float] | None) -> dict:
    if not a or not b:
        return {"available": False}
    labels = ["left", "top", "right", "bottom"]
    deltas = {label: float(b[idx] - a[idx]) for idx, label in enumerate(labels)}
    deltas["max_abs_pt"] = max(abs(value) for value in deltas.values())
    deltas["available"] = True
    return deltas


def text_words(text: str) -> int:
    return len([item for item in text.replace("\n", " ").split(" ") if item.strip()])


def horizontal_overlap_ratio(first: list[float], second: list[float]) -> float:
    overlap = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    narrower = min(max(first[2] - first[0], 0.0), max(second[2] - second[0], 0.0))
    return overlap / narrower if narrower > 0 else 0.0


def baseline_steps(lines: list[dict]) -> list[float]:
    """Estimate top-to-top body-line steps without crossing column lanes."""
    steps = []
    for index, first in enumerate(lines):
        first_box = first["bbox"]
        candidates = []
        for second in lines[index + 1:]:
            second_box = second["bbox"]
            step = float(second_box[1]) - float(first_box[1])
            if step > 36:
                break
            if step < 5 or horizontal_overlap_ratio(first_box, second_box) < 0.55:
                continue
            candidates.append(step)
        if candidates:
            steps.append(min(candidates))
    return steps


def line_from_spans(spans: list[dict], bbox: list[float]) -> dict:
    text = "".join(str(span.get("text", "")) for span in spans).strip()
    sizes = [float(span.get("size") or 0) for span in spans if span.get("size")]
    fonts = [str(span.get("font", "")) for span in spans if span.get("font")]
    return {
        "text": text,
        "bbox": [float(value) for value in bbox],
        "font_size": median(sizes),
        "font": fonts[0] if fonts else None,
        "word_count": text_words(text),
    }


def extract_profile(pdf: Path, max_pages: int) -> dict:
    try:
        import fitz  # type: ignore
    except Exception as exc:
        return {"available": False, "error": f"PyMuPDF is unavailable: {exc}", "pages": []}

    pages = []
    total_page_count = 0
    with fitz.open(str(pdf)) as doc:
        total_page_count = len(doc)
        for page_index, page in enumerate(doc[:max_pages], 1):
            width = float(page.rect.width)
            height = float(page.rect.height)
            lines = []
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                for raw_line in block.get("lines", []):
                    line = line_from_spans(raw_line.get("spans", []), raw_line.get("bbox", [0, 0, 0, 0]))
                    if line["text"]:
                        lines.append(line)
            lines.sort(key=lambda item: (item["bbox"][1], item["bbox"][0]))
            text_bbox = bbox_union([line["bbox"] for line in lines])
            body_lines = [
                line for line in lines
                if line["bbox"][1] >= height * 0.12 and line["bbox"][3] <= height * 0.88
            ]
            gaps = []
            for first, second in zip(body_lines, body_lines[1:]):
                gap = float(second["bbox"][1]) - float(first["bbox"][3])
                if -2 <= gap <= 60:
                    gaps.append(gap)
            sizes = [float(line["font_size"]) for line in body_lines if line.get("font_size")]
            body_baseline_steps = baseline_steps(body_lines)
            text = "\n".join(line["text"] for line in lines)
            top_band = [line for line in lines if line["bbox"][1] <= height * 0.12]
            bottom_band = [line for line in lines if line["bbox"][3] >= height * 0.88]
            anchors = {}
            for name, needles in ANCHORS.items():
                hits = semantic_anchor_hits(lines, needles)
                anchors[name] = {
                    "present": bool(hits),
                    "first_bbox": hits[0]["bbox"] if hits else None,
                    "hit_count": len(hits),
                    "sample_text": hits[0]["text"] if hits else None,
                    "matched_line_count": hits[0]["line_count"] if hits else None,
                }
            pages.append({
                "index": page_index,
                "width_pt": width,
                "height_pt": height,
                "text_bbox": text_bbox,
                "body_text_bbox": bbox_union([line["bbox"] for line in body_lines]),
                "top_margin_pt": text_bbox[1] if text_bbox else None,
                "bottom_margin_pt": height - text_bbox[3] if text_bbox else None,
                "left_margin_pt": text_bbox[0] if text_bbox else None,
                "right_margin_pt": width - text_bbox[2] if text_bbox else None,
                "line_count": len(lines),
                "word_count": text_words(text),
                "body_line_count": len(body_lines),
                "body_word_count": sum(line["word_count"] for line in body_lines),
                "median_line_gap_pt": median(gaps),
                "median_baseline_step_pt": median(body_baseline_steps),
                "baseline_step_sample_count": len(body_baseline_steps),
                "median_font_size_pt": median(sizes),
                "header_line_count": len(top_band),
                "footer_line_count": len(bottom_band),
                "image_count": len(page.get_images(full=True)),
                "anchors": anchors,
            })
    return {
        "available": True,
        "anchor_profile_version": ANCHOR_PROFILE_VERSION,
        "pdf": str(pdf),
        "total_page_count": total_page_count,
        "profiled_page_count": len(pages),
        "pages": pages,
    }


def compare_page(ref: dict, gen: dict) -> dict:
    line_gap_delta = None
    if ref.get("median_line_gap_pt") is not None and gen.get("median_line_gap_pt") is not None:
        line_gap_delta = float(gen["median_line_gap_pt"] - ref["median_line_gap_pt"])
    font_delta = None
    if ref.get("median_font_size_pt") is not None and gen.get("median_font_size_pt") is not None:
        font_delta = float(gen["median_font_size_pt"] - ref["median_font_size_pt"])
    baseline_delta = None
    if ref.get("median_baseline_step_pt") is not None and gen.get("median_baseline_step_pt") is not None:
        baseline_delta = float(gen["median_baseline_step_pt"] - ref["median_baseline_step_pt"])
    word_ratio = None
    if ref.get("body_word_count"):
        word_ratio = float(gen.get("body_word_count", 0)) / float(ref["body_word_count"])
    anchor_deltas = {}
    for name in ANCHORS:
        ref_anchor = (ref.get("anchors") or {}).get(name, {})
        gen_anchor = (gen.get("anchors") or {}).get(name, {})
        delta = bbox_delta(ref_anchor.get("first_bbox"), gen_anchor.get("first_bbox"))
        anchor_deltas[name] = {
            "reference_present": bool(ref_anchor.get("present")),
            "generated_present": bool(gen_anchor.get("present")),
            "bbox_delta": delta,
        }
    return {
        "page": ref.get("index"),
        "text_bbox_delta": bbox_delta(ref.get("body_text_bbox") or ref.get("text_bbox"), gen.get("body_text_bbox") or gen.get("text_bbox")),
        "line_count_delta": int(gen.get("body_line_count", gen.get("line_count", 0)) - ref.get("body_line_count", ref.get("line_count", 0))),
        "word_count_ratio": word_ratio,
        "median_line_gap_delta_pt": line_gap_delta,
        "median_baseline_step_delta_pt": baseline_delta,
        "reference_baseline_step_sample_count": int(ref.get("baseline_step_sample_count", 0)),
        "generated_baseline_step_sample_count": int(gen.get("baseline_step_sample_count", 0)),
        "median_font_size_delta_pt": font_delta,
        "header_line_count_delta": int(gen.get("header_line_count", 0) - ref.get("header_line_count", 0)),
        "footer_line_count_delta": int(gen.get("footer_line_count", 0) - ref.get("footer_line_count", 0)),
        "image_count_delta": int(gen.get("image_count", 0) - ref.get("image_count", 0)),
        "anchor_deltas": anchor_deltas,
    }


def document_anchors(profile: dict) -> dict:
    found = {}
    for page in profile.get("pages", []):
        for name, anchor in (page.get("anchors") or {}).items():
            if name not in found and anchor.get("present"):
                found[name] = {
                    "page": page.get("index"),
                    "bbox": anchor.get("first_bbox"),
                    "sample_text": anchor.get("sample_text"),
                }
    return found


def compare_document_anchors(ref_profile: dict, gen_profile: dict) -> dict:
    ref_anchors = document_anchors(ref_profile)
    gen_anchors = document_anchors(gen_profile)
    result = {}
    for name in ANCHORS:
        ref = ref_anchors.get(name)
        gen = gen_anchors.get(name)
        page_delta = None
        if ref and gen and ref.get("page") is not None and gen.get("page") is not None:
            page_delta = int(gen["page"] - ref["page"])
        result[name] = {
            "reference_present": bool(ref),
            "generated_present": bool(gen),
            "reference_page": ref.get("page") if ref else None,
            "generated_page": gen.get("page") if gen else None,
            "page_delta": page_delta,
            "bbox_delta": bbox_delta(ref.get("bbox") if ref else None, gen.get("bbox") if gen else None),
        }
    return result


def finite_abs(value: object) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except Exception:
        return 0.0
    return abs(number) if math.isfinite(number) else 0.0


def summarize(comparisons: list[dict], document_anchor_deltas: dict | None = None) -> dict:
    anchor_max: dict[str, float] = {}
    missing_anchors: list[str] = []
    anchor_page_shifts: dict[str, int] = {}
    for name, info in (document_anchor_deltas or {}).items():
        delta = info.get("bbox_delta", {})
        if delta.get("available"):
            anchor_max[name] = max(anchor_max.get(name, 0.0), finite_abs(delta.get("top")))
            if info.get("page_delta"):
                anchor_page_shifts[name] = abs(int(info["page_delta"]))
        elif info.get("reference_present") != info.get("generated_present"):
            missing_anchors.append(name)
    bbox_max = max((finite_abs((item.get("text_bbox_delta") or {}).get("max_abs_pt")) for item in comparisons), default=0.0)
    line_gap_max = max((finite_abs(item.get("median_line_gap_delta_pt")) for item in comparisons), default=0.0)
    baseline_step_max = max((finite_abs(item.get("median_baseline_step_delta_pt")) for item in comparisons), default=0.0)
    font_max = max((finite_abs(item.get("median_font_size_delta_pt")) for item in comparisons), default=0.0)
    header_footer_max = max(
        (
            max(finite_abs(item.get("header_line_count_delta")), finite_abs(item.get("footer_line_count_delta")))
            for item in comparisons
        ),
        default=0.0,
    )
    body_box_deltas = [
        item.get("text_bbox_delta") or {} for item in comparisons
        if (item.get("text_bbox_delta") or {}).get("available")
    ]
    left_delta = median([float(item.get("left", 0)) for item in body_box_deltas])
    right_delta = median([float(item.get("right", 0)) for item in body_box_deltas])
    width_delta = median([
        float(item.get("right", 0)) - float(item.get("left", 0))
        for item in body_box_deltas
    ])

    # A large vertical displacement on a late anchor is usually a pagination,
    # column-flow, or float issue. It must not be misreported as a page-frame
    # error merely because a later page has a different text-box bottom.
    front_anchor_max = max((anchor_max.get(name, 0.0) for name in ("title", "abstract", "keywords")), default=0.0)
    late_anchor_max = max((anchor_max.get(name, 0.0) for name in ("introduction", "methods", "table", "figure", "references", "appendix")), default=0.0)
    page_shift_max = max(anchor_page_shifts.values(), default=0)
    pagination_or_flow = max(
        page_shift_max * 0.75,
        late_anchor_max / 120.0 if late_anchor_max > 72 and front_anchor_max < 48 else 0.0,
    )
    horizontal_body_box = max(
        abs(width_delta or 0.0) / 120.0 if abs(width_delta or 0.0) > 12 else 0.0,
        max(abs(left_delta or 0.0), abs(right_delta or 0.0)) / 180.0 if max(abs(left_delta or 0.0), abs(right_delta or 0.0)) > 18 else 0.0,
    )
    cause_scores = {
        "front_matter_spacing": max(anchor_max.get("title", 0.0), anchor_max.get("abstract", 0.0), anchor_max.get("keywords", 0.0)) / 120.0,
        "page_frame_or_body_box": horizontal_body_box,
        "pagination_or_structural_flow": pagination_or_flow,
        "body_density": max(
            baseline_step_max / 6.0 if baseline_step_max > 1 else 0.0,
            line_gap_max / 8.0 if line_gap_max > 3 else 0.0,
            font_max / 4.0 if font_max > 0.5 else 0.0,
        ),
        "table_figure_caption_or_float": max(anchor_max.get("table", 0.0), anchor_max.get("figure", 0.0)) / 120.0,
        "header_footer": header_footer_max * 0.25 if header_footer_max >= 2 else 0.0,
        "anchor_presence": len(missing_anchors) * 0.25,
    }
    top_causes = [
        name for name, score in sorted(cause_scores.items(), key=lambda item: item[1], reverse=True)
        if score >= 0.10
    ][:3]
    penalty = (
        bbox_max / 120.0
        + line_gap_max / 8.0
        + font_max / 4.0
        + max(anchor_max.values(), default=0.0) / 120.0
        + len(missing_anchors) * 0.25
    )
    line_delta = median([
        float(item["median_line_gap_delta_pt"])
        for item in comparisons if item.get("median_line_gap_delta_pt") is not None
    ])
    font_delta = median([
        float(item["median_font_size_delta_pt"])
        for item in comparisons if item.get("median_font_size_delta_pt") is not None
    ])
    baseline_delta = median([
        float(item["median_baseline_step_delta_pt"])
        for item in comparisons if item.get("median_baseline_step_delta_pt") is not None
    ])
    calibration_hints = []
    if pagination_or_flow >= 0.75:
        calibration_hints.append(
            "Later anchors drift across pages; repair front-matter flow, column transition, or float placement before proposing page-margin calibration."
        )
    elif width_delta is not None and abs(width_delta) > 12:
        direction = "narrower" if width_delta < 0 else "wider"
        calibration_hints.append(
            f"Generated body text box is about {abs(width_delta):.1f}pt {direction}; inspect page margins and role-specific left/right indents before tuning local spacing."
        )
    if font_delta is not None and abs(font_delta) > 0.5:
        direction = "larger" if font_delta > 0 else "smaller"
        calibration_hints.append(
            f"Generated median body font is about {abs(font_delta):.1f}pt {direction}; verify font family metrics and source body size together."
        )
    if line_delta is not None and abs(line_delta) > 1.0:
        direction = "looser" if line_delta > 0 else "tighter"
        calibration_hints.append(
            f"Generated median body line gap is about {abs(line_delta):.1f}pt {direction}; calibrate line spacing only after the body box is correct."
        )
    if baseline_delta is not None and abs(baseline_delta) > 0.75:
        direction = "larger" if baseline_delta > 0 else "smaller"
        calibration_hints.append(
            f"Generated median same-lane baseline step is about {abs(baseline_delta):.1f}pt {direction}; consider a bounded body-density render probe only when page count, body width, and anchor pages are stable."
        )
    return {
        "layout_penalty": round(penalty, 6),
        "max_text_bbox_delta_pt": round(bbox_max, 3),
        "max_line_gap_delta_pt": round(line_gap_max, 3),
        "max_baseline_step_delta_pt": round(baseline_step_max, 3),
        "median_baseline_step_delta_pt": round(baseline_delta, 3) if baseline_delta is not None else None,
        "max_font_size_delta_pt": round(font_max, 3),
        "median_body_box_delta_pt": {
            "left": round(left_delta or 0.0, 3),
            "right": round(right_delta or 0.0, 3),
            "width": round(width_delta or 0.0, 3),
        },
        "max_anchor_top_delta_pt": {key: round(value, 3) for key, value in sorted(anchor_max.items())},
        "anchor_page_shifts": anchor_page_shifts,
        "missing_or_asymmetric_anchors": missing_anchors,
        "cause_scores": {key: round(value, 6) for key, value in sorted(cause_scores.items())},
        "top_causes": top_causes or ["minor_visual_difference"],
        "calibration_hints": calibration_hints,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_pdf")
    parser.add_argument("generated_pdf")
    parser.add_argument("--outdir", default="layout-profile")
    parser.add_argument("--max-pages", type=int, default=8)
    parser.add_argument("--anchors-json", help="Optional JSON map of semantic zone names to unique same-content phrases")
    args = parser.parse_args()

    global ANCHOR_PROFILE_VERSION
    if args.anchors_json:
        custom_anchors, ANCHOR_PROFILE_VERSION = load_anchor_map(Path(args.anchors_json).expanduser().resolve())
        ANCHORS.clear()
        ANCHORS.update(custom_anchors)

    ref_pdf = Path(args.reference_pdf).expanduser().resolve()
    gen_pdf = Path(args.generated_pdf).expanduser().resolve()
    outdir = Path(args.outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    if not ref_pdf.exists() or not gen_pdf.exists():
        print("both PDF paths must exist", file=sys.stderr)
        return 2

    ref_profile = extract_profile(ref_pdf, args.max_pages)
    gen_profile = extract_profile(gen_pdf, args.max_pages)
    comparisons = []
    if ref_profile.get("available") and gen_profile.get("available"):
        for ref_page, gen_page in zip(ref_profile.get("pages", []), gen_profile.get("pages", [])):
            comparisons.append(compare_page(ref_page, gen_page))
    document_anchor_deltas = compare_document_anchors(ref_profile, gen_profile) if comparisons else {}
    report = {
        "anchor_profile_version": ANCHOR_PROFILE_VERSION,
        "anchor_map": ANCHORS,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reference_pdf": str(ref_pdf),
        "generated_pdf": str(gen_pdf),
        "reference_profile": str(outdir / "layout_profile_reference.json"),
        "generated_profile": str(outdir / "layout_profile_generated.json"),
        "reference_page_count": ref_profile.get("total_page_count", len(ref_profile.get("pages", []))),
        "generated_page_count": gen_profile.get("total_page_count", len(gen_profile.get("pages", []))),
        "available": bool(ref_profile.get("available") and gen_profile.get("available")),
        "comparisons": comparisons,
        "document_anchor_deltas": document_anchor_deltas,
        "summary": summarize(comparisons, document_anchor_deltas) if comparisons else {
            "layout_penalty": None,
            "top_causes": ["layout_profile_unavailable"],
        },
        "errors": [item.get("error") for item in [ref_profile, gen_profile] if item.get("error")],
    }
    (outdir / "layout_profile_reference.json").write_text(json.dumps(ref_profile, indent=2, ensure_ascii=False), encoding="utf-8")
    (outdir / "layout_profile_generated.json").write_text(json.dumps(gen_profile, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path = outdir / "layout_diagnostics.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
