#!/usr/bin/env python3
"""Profile two PDFs by text geometry so visual failures have a cause."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


ANCHOR_PROFILE_VERSION = "stress-body-unique-v13"
CONTRACT_SCOPE = "full_document"
ANCHOR_ZONE_SPECS: dict[str, dict] = {}
ANCHOR_ZONE_NAMES: dict[str, str] = {}
ANCHOR_MAX_BBOX_DELTAS: dict[str, float] = {}
ANCHOR_PLACEMENT_MODELS: dict[str, str] = {}
ANCHOR_CONTEXTS: dict[str, str] = {}
ANCHOR_SOURCE_EVIDENCE_IDS: dict[str, list[str]] = {}

ANCHORS = {
    # Prefer a unique phrase that fits on one rendered line. Long anchors can
    # be split by a narrow Word column, making a valid same-manuscript pair
    # look incomparable solely because the geometry extractor cannot join
    # text from separated lanes. Alternatives retain semantic specificity.
    "title": ["Temp2TeX Regression", "Template Fidelity"],
    "abstract": ["This benchmark", "template behavior"],
    "keywords": ["template conversion", "regression testing"],
    "introduction": ["The regression body verifies", "converted template preserves"],
    "methods": ["The method section includes", "Equation (1) should"],
    "table": ["Expected stress", "merged-cell behavior"],
    "figure": ["Single-panel figure", "subfigure regression"],
    "acknowledgements": ["The authors thank the template maintainers"],
    "data_availability": ["All data in this manuscript are placeholders"],
    "references": ["Template regression testing", "Journal Formatting Methods"],
    "appendix": ["Appendix Regression Checks", "appendix verifies"],
}

# A central page band includes front matter, tables, figures, and occasionally
# page furniture. It is useful for a coarse visual signal, but it is not
# evidence that a Word section frame or global margin is wrong. Only repeated
# manuscript-body anchors can support that diagnosis.
BODY_FRAME_ANCHORS = (
    "introduction",
    "methods",
    "acknowledgements",
    "data_availability",
)


def normalized_zone_spec(name: str, value: object) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"zone {name!r} must be an object")
    placement_model = str(value.get("placement_model") or "page_fixed").strip().lower()
    if placement_model not in {"page_fixed", "flow_relative"}:
        raise ValueError(f"zone {name!r} placement_model must be page_fixed or flow_relative")
    if placement_model == "flow_relative":
        context_anchor = value.get("context_anchor")
        if not isinstance(context_anchor, str) or not context_anchor.strip():
            raise ValueError(f"flow_relative zone {name!r} must name a context_anchor")
        if value.get("required_image_count", 0) or value.get("max_image_box_delta_pt") is not None:
            raise ValueError(
                f"flow_relative zone {name!r} cannot use image-box checks; use a page_fixed zone for page-relative artwork"
            )
        return {
            "placement_model": placement_model,
            "context_anchor": context_anchor.strip(),
            "pages": [],
            "rect_ratio": None,
            "required_image_count": 0,
            "max_image_box_delta_pt": None,
        }
    pages_raw = value.get("pages", value.get("page"))
    if isinstance(pages_raw, int):
        pages = [pages_raw]
    elif isinstance(pages_raw, list) and all(isinstance(item, int) for item in pages_raw):
        pages = pages_raw
    else:
        raise ValueError(f"zone {name!r} must declare page or pages as positive integers")
    if not pages or any(item < 1 for item in pages):
        raise ValueError(f"zone {name!r} must declare at least one positive page number")
    rect = value.get("rect_ratio", value.get("bbox_ratio"))
    if not (isinstance(rect, list) and len(rect) == 4 and all(isinstance(item, (int, float)) for item in rect)):
        raise ValueError(f"zone {name!r} must declare rect_ratio as [left, top, right, bottom]")
    left, top, right, bottom = [float(item) for item in rect]
    if not (0.0 <= left < right <= 1.0 and 0.0 <= top < bottom <= 1.0):
        raise ValueError(f"zone {name!r} rect_ratio must be inside the page and have positive area")
    required_image_count = value.get("required_image_count", 0)
    if not isinstance(required_image_count, int) or required_image_count < 0:
        raise ValueError(f"zone {name!r} required_image_count must be a non-negative integer")
    max_image_box_delta = value.get("max_image_box_delta_pt")
    if max_image_box_delta is not None and (not isinstance(max_image_box_delta, (int, float)) or max_image_box_delta < 0):
        raise ValueError(f"zone {name!r} max_image_box_delta_pt must be a non-negative number")
    return {
        "placement_model": placement_model,
        "context_anchor": None,
        "pages": sorted(set(pages)),
        "rect_ratio": [left, top, right, bottom],
        "required_image_count": required_image_count,
        "max_image_box_delta_pt": float(max_image_box_delta) if max_image_box_delta is not None else None,
    }


def load_anchor_map(path: Path) -> tuple[
    dict[str, list[str]], str, str, dict[str, dict], dict[str, str], dict[str, float], dict[str, str], dict[str, str], dict[str, list[str]]
]:
    # Windows editors commonly emit UTF-8 with BOM. Anchor maps are user
    # supplied verification contracts, so accept both UTF-8 variants instead
    # of failing before any layout evidence is inspected.
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict) or not raw:
        raise ValueError("anchor map must be a non-empty JSON object")
    contract_scope = "full_document"
    zones: dict[str, dict] = {}
    anchor_zones: dict[str, str] = {}
    anchor_max_deltas: dict[str, float] = {}
    anchor_source_evidence_ids: dict[str, list[str]] = {}
    if "anchors" in raw:
        contract_scope = str(raw.get("scope") or raw.get("contract_scope") or "full_document").strip().lower()
        raw_zones = raw.get("zones", {})
        if not isinstance(raw_zones, dict):
            raise ValueError("zones must be an object")
        zones = {str(name): normalized_zone_spec(str(name), value) for name, value in raw_zones.items()}
        raw = raw.get("anchors")
    if contract_scope not in {"full_document", "partial_zone"}:
        raise ValueError("anchor-map scope must be full_document or partial_zone")
    if not isinstance(raw, dict) or not raw:
        raise ValueError("anchor map must contain a non-empty anchors object")
    anchors: dict[str, list[str]] = {}
    for name, value in raw.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("each anchor must map a non-empty name to a string or string list")
        normalized_name = name.strip()
        if isinstance(value, dict):
            needles = value.get("phrases", value.get("phrase"))
            zone_name = value.get("zone")
            if zone_name is not None:
                if not isinstance(zone_name, str) or zone_name not in zones:
                    raise ValueError(f"anchor {name!r} names an unknown zone")
                anchor_zones[normalized_name] = zone_name
            max_bbox_delta = value.get("max_bbox_delta_pt")
            if max_bbox_delta is not None:
                if not isinstance(max_bbox_delta, (int, float)) or max_bbox_delta < 0:
                    raise ValueError(f"anchor {name!r} max_bbox_delta_pt must be a non-negative number")
                anchor_max_deltas[normalized_name] = float(max_bbox_delta)
            raw_evidence_ids = value.get("source_evidence_ids")
            if raw_evidence_ids is not None:
                evidence_ids = [raw_evidence_ids] if isinstance(raw_evidence_ids, str) else raw_evidence_ids
                if not isinstance(evidence_ids, list):
                    raise ValueError(f"anchor {name!r} source_evidence_ids must be a string or non-empty string list")
                cleaned_evidence_ids = sorted({
                    evidence_id.strip()
                    for evidence_id in evidence_ids
                    if isinstance(evidence_id, str) and evidence_id.strip()
                })
                if not cleaned_evidence_ids or len(cleaned_evidence_ids) != len(evidence_ids):
                    raise ValueError(f"anchor {name!r} source_evidence_ids must contain only non-empty strings")
                anchor_source_evidence_ids[normalized_name] = cleaned_evidence_ids
        else:
            needles = [value] if isinstance(value, str) else value
        if not isinstance(needles, list):
            raise ValueError("each anchor must map a non-empty name to a string or string list")
        cleaned = [item.strip() for item in needles if isinstance(item, str) and item.strip()]
        if not cleaned:
            raise ValueError(f"anchor {name!r} has no usable phrases")
        anchors[normalized_name] = cleaned
    anchor_placement_models: dict[str, str] = {}
    anchor_contexts: dict[str, str] = {}
    for zone_name, zone in zones.items():
        placement_model = zone["placement_model"]
        zoned_anchors = [name for name, bound_zone in anchor_zones.items() if bound_zone == zone_name]
        if placement_model == "flow_relative":
            context_anchor = zone["context_anchor"]
            if context_anchor not in anchors:
                raise ValueError(f"flow_relative zone {zone_name!r} names unknown context_anchor {context_anchor!r}")
            target_anchors = [name for name in zoned_anchors if name != context_anchor]
            if not target_anchors:
                raise ValueError(f"flow_relative zone {zone_name!r} must bind at least one non-context anchor")
            for name in target_anchors:
                if name not in anchor_max_deltas:
                    raise ValueError(
                        f"flow_relative anchor {name!r} must declare max_bbox_delta_pt for its context-relative placement"
                    )
                anchor_placement_models[name] = placement_model
                anchor_contexts[name] = context_anchor
        else:
            for name in zoned_anchors:
                anchor_placement_models[name] = placement_model
    digest_payload = {
        "scope": contract_scope,
        "anchors": anchors,
        "zones": zones,
        "anchor_zones": anchor_zones,
        "anchor_max_deltas": anchor_max_deltas,
        "anchor_placement_models": anchor_placement_models,
        "anchor_contexts": anchor_contexts,
        "anchor_source_evidence_ids": anchor_source_evidence_ids,
    }
    digest = hashlib.sha256(json.dumps(digest_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
    return anchors, f"custom-{digest}", contract_scope, zones, anchor_zones, anchor_max_deltas, anchor_placement_models, anchor_contexts, anchor_source_evidence_ids


def normalized_match_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    for codepoint in (0x00AD, 0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015, 0x2212):
        text = text.replace(chr(codepoint), "-")
    text = " ".join(text.split())
    # pdfplumber can expose CJK glyphs as individually spaced words and can
    # insert spaces around punctuation. Remove only those extraction artefacts;
    # preserve ordinary Latin word boundaries for anchor uniqueness.
    text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
    text = re.sub(r"(?<=[\u3400-\u9fff0-9])\s+(?=[:;,，。；、])", "", text)
    text = re.sub(r"(?<=[:;,，。；、])\s+(?=[\u3400-\u9fff])", "", text)
    return text


def document_text_contract(pdf: Path, anchors: dict[str, list[str]]) -> dict:
    """Check fixture content independently of positioned-line extraction.

    pdfplumber's fallback geometry can split labels and numbers into separate
    word lanes. Keep that limitation visible: a plain-text pass establishes
    structural content only; it never substitutes for the positioned anchor
    contract used by layout calibration.
    """
    extractor = "pypdf"
    try:
        from pypdf import PdfReader  # type: ignore
        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf)).pages)
    except Exception as pypdf_error:
        extractor = "pdfplumber_fallback"
        try:
            import pdfplumber  # type: ignore
            with pdfplumber.open(str(pdf)) as document:
                text = "\n".join(page.extract_text() or "" for page in document.pages)
        except Exception as exc:
            return {"available": False, "extractor": extractor, "error": f"pypdf={pypdf_error}; fallback={exc}", "anchors": {}}
    normalized = normalized_match_text(text)
    found = {}
    for name, needles in anchors.items():
        matched = next((needle for needle in needles if normalized_match_text(needle) in normalized), None)
        found[name] = {"present": matched is not None, "matched_phrase": matched}
    return {"available": True, "extractor": extractor, "anchors": found}


def horizontal_gap(first: list[float], second: list[float]) -> float:
    if first[2] < second[0]:
        return float(second[0] - first[2])
    if second[2] < first[0]:
        return float(first[0] - second[2])
    return 0.0


def semantic_anchor_hits(lines: list[dict], needles: list[str], max_parts: int = 12, max_scan: int = 48) -> list[dict]:
    """Find unique phrases across wrapped lines while skipping another column."""
    # The strict document-level text contract retains ordinary word spacing.
    # This positioned pass also supports pdfplumber's fallback extractor,
    # which can concatenate adjacent Latin glyph runs in some XeLaTeX PDFs.
    # It is safe to compact whitespace here because geometry is considered
    # only after the independent text contract has already passed.
    compact = lambda value: re.sub(r"\s+", "", normalized_match_text(value))
    normalized_needles = [compact(needle) for needle in needles]
    hits = []
    for start, first in enumerate(lines):
        window = [first]
        lane_box = list(first["bbox"])
        last_top = float(first["bbox"][1])
        combined = compact(first["text"])
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
            combined = compact(" ".join(item["text"] for item in window))
            if any(needle in combined for needle in normalized_needles):
                hits.append({
                    "text": " ".join(item["text"] for item in window)[:160],
                    "bbox": bbox_union([item["bbox"] for item in window]),
                    "line_count": len(window),
                })
                break
    # A phrase near the end of a long same-column paragraph can be reachable
    # from several earlier lines. Prefer the smallest local match; otherwise a
    # footer anchor may incorrectly absorb body text and become unusable for
    # source-relative placement checks.
    def hit_key(hit: dict) -> tuple[float, float, float, float]:
        box = hit.get("bbox") or [0.0, 0.0, 0.0, 0.0]
        width = max(float(box[2]) - float(box[0]), 0.0)
        height = max(float(box[3]) - float(box[1]), 0.0)
        return (float(hit.get("line_count") or 0), width * height, float(box[1]), float(box[0]))

    return sorted(hits, key=hit_key)


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


def bbox_offset(box: list[float] | None, origin: list[float] | None) -> list[float] | None:
    """Return a box in the coordinate system of a same-page context box."""
    if not box or not origin:
        return None
    return [float(box[index] - origin[index]) for index in range(4)]


def bbox_center(box: list[float]) -> tuple[float, float]:
    return ((float(box[0]) + float(box[2])) / 2.0, (float(box[1]) + float(box[3])) / 2.0)


def zone_rect_pt(zone: dict, width: float, height: float) -> list[float]:
    left, top, right, bottom = zone["rect_ratio"]
    return [left * width, top * height, right * width, bottom * height]


def bbox_in_zone(box: list[float] | None, zone: dict, page_index: int, width: float, height: float) -> bool:
    if not box or page_index not in zone["pages"]:
        return False
    left, top, right, bottom = zone_rect_pt(zone, width, height)
    x, y = bbox_center(box)
    return left <= x <= right and top <= y <= bottom


def zone_metrics(zone: dict, page_index: int, width: float, height: float, lines: list[dict], image_boxes: list[list[float]]) -> dict | None:
    if page_index not in zone["pages"]:
        return None
    rect = zone_rect_pt(zone, width, height)
    contained_lines = [line for line in lines if bbox_in_zone(line.get("bbox"), zone, page_index, width, height)]
    contained_images = [box for box in image_boxes if bbox_in_zone(box, zone, page_index, width, height)]
    return {
        "rect_pt": rect,
        "text_line_count": len(contained_lines),
        "text_bbox": bbox_union([line["bbox"] for line in contained_lines]),
        "image_count": len(contained_images),
        "image_boxes": contained_images,
        "required_image_count": zone["required_image_count"],
        "image_requirement_passed": len(contained_images) >= zone["required_image_count"],
    }


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


def profile_page(index: int, width: float, height: float, lines: list[dict], image_boxes: list[list[float]]) -> dict:
    """Produce backend-neutral page metrics from positioned text lines."""
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
        zone_name = ANCHOR_ZONE_NAMES.get(name)
        zone = ANCHOR_ZONE_SPECS.get(zone_name) if zone_name else None
        # A flow-relative zone follows its local text context. Restricting it
        # to one absolute page rectangle would turn a body-flow shift into a
        # false missing-anchor failure.
        page_fixed_zone = zone if zone and zone.get("placement_model") == "page_fixed" else None
        in_zone_hits = [hit for hit in hits if not page_fixed_zone or bbox_in_zone(hit.get("bbox"), page_fixed_zone, index, width, height)]
        selected_hits = in_zone_hits if page_fixed_zone else hits
        anchors[name] = {
            "present": bool(selected_hits),
            "first_bbox": selected_hits[0]["bbox"] if selected_hits else None,
            "hit_count": len(selected_hits),
            "out_of_zone_hit_count": len(hits) - len(in_zone_hits) if zone else 0,
            "zone": zone_name,
            "sample_text": selected_hits[0]["text"] if selected_hits else None,
            "matched_line_count": selected_hits[0]["line_count"] if selected_hits else None,
        }
    zones = {
        name: metrics
        for name, zone in ANCHOR_ZONE_SPECS.items()
        if zone.get("placement_model") == "page_fixed"
        and (metrics := zone_metrics(zone, index, width, height, lines, image_boxes)) is not None
    }
    return {
        "index": index,
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
        "image_count": len(image_boxes),
        "image_boxes": image_boxes,
        "zones": zones,
        "anchors": anchors,
    }


def extract_profile_pdfplumber(pdf: Path, max_pages: int, pymupdf_error: str) -> dict:
    """Fallback profiler for environments without PyMuPDF.

    pdfplumber exposes positioned words rather than native text spans, so font
    names and line grouping are less exact. It still provides the geometry
    needed to diagnose page-frame, body-density, anchor, and image-box issues.
    """
    try:
        import pdfplumber  # type: ignore
    except Exception as exc:
        return {
            "available": False,
            "error": f"PyMuPDF is unavailable: {pymupdf_error}; pdfplumber is unavailable: {exc}",
            "pages": [],
        }
    pages = []
    try:
        with pdfplumber.open(str(pdf)) as doc:
            for page_index, page in enumerate(doc.pages[:max_pages], 1):
                raw_words = page.extract_words(
                    use_text_flow=True,
                    keep_blank_chars=False,
                    extra_attrs=["fontname", "size"],
                ) or []
                # Font-size changes (heading numbers, CJK glyphs, superscripts,
                # caption labels) often give one visual line slightly different
                # `top` values. Cluster by vertical midpoint/overlap first, then
                # order the full visual line left-to-right.
                rows: list[list[dict]] = []
                for word in sorted(raw_words, key=lambda item: float(item.get("top") or 0.0)):
                    text = str(word.get("text") or "").strip()
                    if not text:
                        continue
                    top = float(word.get("top") or 0.0)
                    bottom = float(word.get("bottom") or top)
                    midpoint = (top + bottom) / 2
                    placed = False
                    for row in reversed(rows):
                        row_tops = [float(item.get("top") or 0.0) for item in row]
                        row_bottoms = [float(item.get("bottom") or 0.0) for item in row]
                        row_midpoint = (statistics.median(row_tops) + statistics.median(row_bottoms)) / 2
                        row_height = max(statistics.median(row_bottoms) - statistics.median(row_tops), 1.0)
                        word_height = max(bottom - top, 1.0)
                        overlap = max(0.0, min(bottom, max(row_bottoms)) - max(top, min(row_tops)))
                        if abs(midpoint - row_midpoint) <= max(2.0, min(row_height, word_height) * 0.55) or overlap >= min(row_height, word_height) * 0.55:
                            row.append(word)
                            placed = True
                            break
                    if not placed:
                        rows.append([word])
                lines = []
                for words in rows:
                    words.sort(key=lambda item: float(item.get("x0") or 0.0))
                    bbox = [
                        min(float(item.get("x0") or 0.0) for item in words),
                        min(float(item.get("top") or 0.0) for item in words),
                        max(float(item.get("x1") or 0.0) for item in words),
                        max(float(item.get("bottom") or 0.0) for item in words),
                    ]
                    sizes = [float(item.get("size")) for item in words if item.get("size")]
                    lines.append({
                        "text": " ".join(str(item.get("text") or "") for item in words).strip(),
                        "bbox": bbox,
                        "font_size": median(sizes),
                        "font": str(words[0].get("fontname") or "") or None,
                        "word_count": text_words(" ".join(str(item.get("text") or "") for item in words)),
                    })
                image_boxes = []
                for image in page.images or []:
                    try:
                        image_boxes.append([
                            float(image["x0"]),
                            float(image["top"]),
                            float(image["x1"]),
                            float(image["bottom"]),
                        ])
                    except (KeyError, TypeError, ValueError):
                        continue
                pages.append(profile_page(page_index, float(page.width), float(page.height), lines, image_boxes))
            total_page_count = len(doc.pages)
    except Exception as exc:
        return {
            "available": False,
            "error": f"PyMuPDF is unavailable: {pymupdf_error}; pdfplumber extraction failed: {exc}",
            "pages": [],
        }
    return {
        "available": True,
        "anchor_profile_version": ANCHOR_PROFILE_VERSION,
        "pdf": str(pdf),
        "extractor": "pdfplumber_fallback",
        "pymupdf_error": pymupdf_error,
        "total_page_count": total_page_count,
        "profiled_page_count": len(pages),
        "pages": pages,
    }


def extract_profile(pdf: Path, max_pages: int) -> dict:
    try:
        import fitz  # type: ignore
    except Exception as exc:
        return extract_profile_pdfplumber(pdf, max_pages, str(exc))

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
            image_boxes = []
            seen_image_boxes: set[tuple[float, float, float, float]] = set()
            for image in page.get_images(full=True):
                for rect in page.get_image_rects(image[0]):
                    box = (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
                    if box not in seen_image_boxes:
                        seen_image_boxes.add(box)
                        image_boxes.append(list(box))
            pages.append(profile_page(page_index, width, height, lines, image_boxes))
    return {
        "available": True,
        "anchor_profile_version": ANCHOR_PROFILE_VERSION,
        "pdf": str(pdf),
        "extractor": "pymupdf",
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
        placement_model = ANCHOR_PLACEMENT_MODELS.get(name, "page_fixed")
        context_name = ANCHOR_CONTEXTS.get(name)
        delta = bbox_delta(ref.get("bbox") if ref else None, gen.get("bbox") if gen else None)
        max_bbox_delta = ANCHOR_MAX_BBOX_DELTAS.get(name)
        item = {
            "reference_present": bool(ref),
            "generated_present": bool(gen),
            "reference_page": ref.get("page") if ref else None,
            "generated_page": gen.get("page") if gen else None,
            "page_delta": page_delta,
            "bbox_delta": delta,
            "max_bbox_delta_pt": max_bbox_delta,
            "placement_model": placement_model,
            "context_anchor": context_name,
        }
        if placement_model == "flow_relative":
            ref_context = ref_anchors.get(context_name) if context_name else None
            gen_context = gen_anchors.get(context_name) if context_name else None
            reference_same_page = bool(
                ref and ref_context and ref.get("page") is not None and ref.get("page") == ref_context.get("page")
            )
            generated_same_page = bool(
                gen and gen_context and gen.get("page") is not None and gen.get("page") == gen_context.get("page")
            )
            relative_delta = bbox_delta(
                bbox_offset(ref.get("bbox") if ref else None, ref_context.get("bbox") if ref_context else None),
                bbox_offset(gen.get("bbox") if gen else None, gen_context.get("bbox") if gen_context else None),
            )
            item.update({
                "context_reference_present": bool(ref_context),
                "context_generated_present": bool(gen_context),
                "reference_same_page_as_context": reference_same_page,
                "generated_same_page_as_context": generated_same_page,
                "relative_bbox_delta": relative_delta,
                "geometry_basis": "context_relative_bbox",
                "geometry_within_tolerance": (
                    relative_delta.get("available")
                    and reference_same_page
                    and generated_same_page
                    and float(relative_delta["max_abs_pt"]) <= max_bbox_delta
                    if max_bbox_delta is not None else None
                ),
            })
        else:
            item.update({
                "geometry_basis": "page_absolute_bbox",
                "geometry_within_tolerance": (
                    delta.get("available") and float(delta["max_abs_pt"]) <= max_bbox_delta
                    if max_bbox_delta is not None else None
                ),
            })
        result[name] = item
    return result


def body_anchor_horizontal_evidence(document_anchor_deltas: dict | None) -> dict:
    """Return a conservative page-frame signal from repeated body anchors.

    The profiler's central-band text box is deliberately broad. A consistent
    left-edge shift across at least two body anchors is stronger evidence than
    that broad box, but still identifies a page-or-local-indent investigation,
    not an automatic margin edit.
    """
    candidates = []
    for name in BODY_FRAME_ANCHORS:
        item = (document_anchor_deltas or {}).get(name)
        if not isinstance(item, dict) or item.get("page_delta") not in {None, 0}:
            continue
        delta = item.get("bbox_delta")
        if not isinstance(delta, dict) or not delta.get("available"):
            continue
        try:
            left = float(delta.get("left"))
        except (TypeError, ValueError):
            continue
        candidates.append({"anchor": name, "left_delta_pt": round(left, 3)})
    values = [item["left_delta_pt"] for item in candidates]
    median_left = median(values)
    spread = (max(values) - min(values)) if values else None
    minimum_signal = 12.0
    maximum_spread = 8.0
    confirmed = (
        len(values) >= 2
        and median_left is not None
        and abs(float(median_left)) >= minimum_signal
        and spread is not None
        and spread <= maximum_spread
    )
    if confirmed:
        reason = "At least two same-page manuscript-body anchors have a stable horizontal shift."
    elif len(values) < 2:
        reason = "Fewer than two same-page manuscript-body anchors have usable horizontal geometry."
    elif spread is not None and spread > maximum_spread:
        reason = "Body-anchor horizontal shifts vary by more than 8pt, so local role layout may dominate."
    else:
        reason = "Body-anchor horizontal shift is below the 12pt investigation threshold."
    return {
        "status": "confirmed" if confirmed else "not_confirmed",
        "anchors": candidates,
        "usable_anchor_count": len(candidates),
        "median_left_delta_pt": round(float(median_left), 3) if median_left is not None else None,
        "left_delta_spread_pt": round(float(spread), 3) if spread is not None else None,
        "minimum_signal_pt": minimum_signal,
        "maximum_spread_pt": maximum_spread,
        "reason": reason,
    }


def ordered_box_deltas(reference_boxes: list[list[float]], generated_boxes: list[list[float]]) -> list[dict]:
    reference_sorted = sorted(reference_boxes, key=lambda box: (box[1], box[0], box[3], box[2]))
    generated_sorted = sorted(generated_boxes, key=lambda box: (box[1], box[0], box[3], box[2]))
    return [bbox_delta(reference, generated) for reference, generated in zip(reference_sorted, generated_sorted)]


def compare_document_zones(ref_profile: dict, gen_profile: dict) -> dict:
    """Compare declared visual zones without treating image pixels as template evidence."""
    result = {}
    for name, zone in ANCHOR_ZONE_SPECS.items():
        if zone.get("placement_model") != "page_fixed":
            result[name] = {
                "placement_model": "flow_relative",
                "context_anchor": zone.get("context_anchor"),
                "status": "anchor_relative_only",
                "rule": "Flow-relative zones are checked through their bound text anchors, not through absolute page rectangles or image boxes.",
            }
            continue
        ref_entries = [page.get("zones", {}).get(name) for page in ref_profile.get("pages", []) if page.get("zones", {}).get(name)]
        gen_entries = [page.get("zones", {}).get(name) for page in gen_profile.get("pages", []) if page.get("zones", {}).get(name)]
        ref_images = [box for entry in ref_entries for box in entry.get("image_boxes", [])]
        gen_images = [box for entry in gen_entries for box in entry.get("image_boxes", [])]
        ref_text = bbox_union([entry["text_bbox"] for entry in ref_entries if entry.get("text_bbox")])
        gen_text = bbox_union([entry["text_bbox"] for entry in gen_entries if entry.get("text_bbox")])
        image_box_deltas = ordered_box_deltas(ref_images, gen_images)
        max_image_box_delta = zone["max_image_box_delta_pt"]
        image_geometry_within_tolerance = None
        if max_image_box_delta is not None:
            image_geometry_within_tolerance = (
                len(ref_images) == len(gen_images)
                and all(delta.get("available") and float(delta["max_abs_pt"]) <= max_image_box_delta for delta in image_box_deltas)
            )
        result[name] = {
            "placement_model": "page_fixed",
            "pages": zone["pages"],
            "rect_ratio": zone["rect_ratio"],
            "reference_text_bbox": ref_text,
            "generated_text_bbox": gen_text,
            "text_bbox_delta": bbox_delta(ref_text, gen_text),
            "reference_image_count": len(ref_images),
            "generated_image_count": len(gen_images),
            "image_count_delta": len(gen_images) - len(ref_images),
            "image_box_deltas": image_box_deltas,
            "required_image_count": zone["required_image_count"],
            "max_image_box_delta_pt": max_image_box_delta,
            "image_geometry_within_tolerance": image_geometry_within_tolerance,
            "reference_image_requirement_passed": bool(ref_entries) and all(entry.get("image_requirement_passed") for entry in ref_entries),
            "generated_image_requirement_passed": bool(gen_entries) and all(entry.get("image_requirement_passed") for entry in gen_entries),
        }
    return result


def finite_abs(value: object) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except Exception:
        return 0.0
    return abs(number) if math.isfinite(number) else 0.0


def summarize(
    comparisons: list[dict],
    document_anchor_deltas: dict | None = None,
    document_zone_deltas: dict | None = None,
    reference_text_contract: dict | None = None,
    generated_text_contract: dict | None = None,
    contract_scope: str = "full_document",
    reference_page_count: int | None = None,
    generated_page_count: int | None = None,
) -> dict:
    anchor_max: dict[str, float] = {}
    missing_anchors: list[str] = []
    anchor_page_shifts: dict[str, int] = {}
    for name, info in (document_anchor_deltas or {}).items():
        delta = info.get("bbox_delta", {})
        if delta.get("available"):
            anchor_max[name] = max(anchor_max.get(name, 0.0), finite_abs(delta.get("top")))
            if info.get("page_delta"):
                anchor_page_shifts[name] = abs(int(info["page_delta"]))
        # A same-content contract is not satisfied when either side lacks a
        # required phrase. Treat a phrase missing from both PDFs as an invalid
        # contract entry too, rather than silently ignoring it.
        elif not (info.get("reference_present") and info.get("generated_present")):
            missing_anchors.append(name)
    shared_anchor_count = len(anchor_max)
    required_anchor_count = len(document_anchor_deltas or {})
    text_contract = {}
    for name in (document_anchor_deltas or {}):
        ref = (reference_text_contract or {}).get("anchors", {}).get(name, {})
        gen = (generated_text_contract or {}).get("anchors", {}).get(name, {})
        text_contract[name] = {
            "reference_present": bool(ref.get("present")),
            "generated_present": bool(gen.get("present")),
        }
    missing_text_contract_anchors = [
        name for name, item in text_contract.items()
        if not (item["reference_present"] and item["generated_present"])
    ]
    text_contract_passed = bool(text_contract) and not missing_text_contract_anchors
    out_of_tolerance_anchors = [
        name for name, item in (document_anchor_deltas or {}).items()
        if item.get("geometry_within_tolerance") is False
    ]
    failed_flow_context_anchors = [
        name for name, item in (document_anchor_deltas or {}).items()
        if item.get("placement_model") == "flow_relative"
        and not (
            item.get("context_reference_present")
            and item.get("context_generated_present")
            and item.get("reference_same_page_as_context")
            and item.get("generated_same_page_as_context")
        )
    ]
    missing_zone_anchors = [
        name for name, item in (document_anchor_deltas or {}).items()
        if not (item.get("reference_present") and item.get("generated_present"))
    ]
    failed_image_zones = [
        name for name, item in (document_zone_deltas or {}).items()
        if item.get("placement_model") == "page_fixed"
        and (
            not item.get("reference_image_requirement_passed")
        or not item.get("generated_image_requirement_passed")
        or item.get("image_geometry_within_tolerance") is False
        )
    ]
    has_local_tolerance = any(
        item.get("max_bbox_delta_pt") is not None for item in (document_anchor_deltas or {}).values()
    ) or any(
        item.get("max_image_box_delta_pt") is not None or item.get("required_image_count", 0) > 0
        for item in (document_zone_deltas or {}).values()
    )
    local_zone_gate_status = (
        "failed" if missing_zone_anchors or out_of_tolerance_anchors or failed_flow_context_anchors or failed_image_zones
        else "passed" if has_local_tolerance
        else "not_configured"
    )
    # Geometry from unrelated or partly divergent fixtures is not a calibration
    # signal. An anchor map is a same-content contract: every declared phrase
    # must occur in both PDFs before interpreting text extents, density, or
    # float flow. A partial hit is diagnostic evidence, never a tuning gate.
    geometry_contract_passed = required_anchor_count > 0 and shared_anchor_count == required_anchor_count
    anchor_contract_passed = text_contract_passed and geometry_contract_passed
    semantic_comparable = anchor_contract_passed and contract_scope == "full_document"
    zone_comparable = anchor_contract_passed and contract_scope == "partial_zone"
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
    central_text_box_deltas = [
        item.get("text_bbox_delta") or {} for item in comparisons
        if (item.get("text_bbox_delta") or {}).get("available")
    ]
    left_delta = median([float(item.get("left", 0)) for item in central_text_box_deltas])
    right_delta = median([float(item.get("right", 0)) for item in central_text_box_deltas])
    width_delta = median([
        float(item.get("right", 0)) - float(item.get("left", 0))
        for item in central_text_box_deltas
    ])

    # A large vertical displacement on a late anchor is usually a pagination,
    # column-flow, or float issue. It must not be misreported as a page-frame
    # error merely because a later page has a different text-box bottom.
    front_anchor_max = max((anchor_max.get(name, 0.0) for name in ("title", "abstract", "keywords")), default=0.0)
    late_anchor_max = max((anchor_max.get(name, 0.0) for name in ("introduction", "methods", "table", "figure", "references", "appendix")), default=0.0)
    page_shift_max = max(anchor_page_shifts.values(), default=0)
    page_count_matches = (
        isinstance(reference_page_count, int)
        and isinstance(generated_page_count, int)
        and reference_page_count == generated_page_count
    )
    pagination_or_flow = max(
        0.75 if not page_count_matches else 0.0,
        page_shift_max * 0.75,
        late_anchor_max / 120.0 if late_anchor_max > 72 and front_anchor_max < 48 else 0.0,
    )
    central_content_extent = max(
        abs(width_delta or 0.0) / 120.0 if abs(width_delta or 0.0) > 12 else 0.0,
        max(abs(left_delta or 0.0), abs(right_delta or 0.0)) / 180.0 if max(abs(left_delta or 0.0), abs(right_delta or 0.0)) > 18 else 0.0,
    )
    body_anchor_evidence = body_anchor_horizontal_evidence(document_anchor_deltas)
    page_frame_score = 0.0
    if body_anchor_evidence.get("status") == "confirmed":
        page_frame_score = abs(float(body_anchor_evidence["median_left_delta_pt"])) / 60.0
    cause_scores = {
        "front_matter_spacing": max(anchor_max.get("title", 0.0), anchor_max.get("abstract", 0.0), anchor_max.get("keywords", 0.0)) / 120.0,
        "page_frame_or_body_box": page_frame_score,
        "central_content_extent_unattributed": central_content_extent if not page_frame_score else 0.0,
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
    global_calibration_eligible = (
        semantic_comparable
        and page_count_matches
        and not anchor_page_shifts
        and pagination_or_flow < 0.75
    )
    if zone_comparable:
        calibration_hints.append(
            "This is a partial-zone contract. Use its positioned anchors only for the declared header/footer or other local zone; do not calibrate page margins, body density, captions, floats, or full-document fidelity from this pair."
        )
        if local_zone_gate_status == "failed":
            calibration_hints.append(
                "The declared local-zone tolerance gate failed. Repair the named page-furniture element before promoting this candidate into the active class."
            )
    elif not semantic_comparable:
        calibration_hints.append(
            "The same-content anchor contract is incomplete. Do not calibrate margins, body density, captions, or float placement; repair the fixture or its role-level anchor map first."
        )
    elif pagination_or_flow >= 0.75:
        calibration_hints.append(
            "Later anchors drift across pages; repair front-matter flow, column transition, or float placement before proposing page-margin calibration."
        )
    elif body_anchor_evidence.get("status") == "confirmed":
        direction = "right" if float(body_anchor_evidence["median_left_delta_pt"]) > 0 else "left"
        calibration_hints.append(
            f"Same-page manuscript-body anchors consistently begin about {abs(float(body_anchor_evidence['median_left_delta_pt'])):.1f}pt to the {direction}; inspect Word section margins and role-specific left/right indents before any bounded page-frame probe."
        )
    elif width_delta is not None and abs(width_delta) > 12:
        direction = "narrower" if width_delta < 0 else "wider"
        calibration_hints.append(
            f"Central-band text extent is about {abs(width_delta):.1f}pt {direction}, but body-anchor geometry does not confirm a shared page frame; inspect the role-local extremes before inferring a margin change."
        )
    if global_calibration_eligible and font_delta is not None and abs(font_delta) > 0.5:
        direction = "larger" if font_delta > 0 else "smaller"
        calibration_hints.append(
            f"Generated median body font is about {abs(font_delta):.1f}pt {direction}; verify font family metrics and source body size together."
        )
    if global_calibration_eligible and line_delta is not None and abs(line_delta) > 1.0:
        direction = "looser" if line_delta > 0 else "tighter"
        calibration_hints.append(
            f"Generated median body line gap is about {abs(line_delta):.1f}pt {direction}; calibrate line spacing only after the body box is correct."
        )
    if global_calibration_eligible and baseline_delta is not None and abs(baseline_delta) > 0.75:
        direction = "larger" if baseline_delta > 0 else "smaller"
        calibration_hints.append(
            f"Generated median same-lane baseline step is about {abs(baseline_delta):.1f}pt {direction}; consider a bounded body-density render probe only when page count, body width, and anchor pages are stable."
        )
    return {
        "layout_penalty": round(penalty, 6) if semantic_comparable else None,
        "contract_scope": contract_scope,
        "semantic_comparable": semantic_comparable,
        "zone_comparable": zone_comparable,
        "shared_anchor_count": shared_anchor_count,
        "required_anchor_count": required_anchor_count,
        "same_content_contract_status": "passed" if semantic_comparable else "partial_zone_only" if zone_comparable else "failed",
        "page_count_matches": page_count_matches,
        "global_calibration_eligible": global_calibration_eligible,
        "text_contract_status": "passed" if text_contract_passed else "failed",
        "geometry_contract_status": "passed" if geometry_contract_passed else "failed",
        "missing_text_contract_anchors": missing_text_contract_anchors,
        "local_zone_gate_status": local_zone_gate_status,
        "missing_zone_anchors": missing_zone_anchors,
        "out_of_tolerance_anchors": out_of_tolerance_anchors,
        "failed_flow_context_anchors": failed_flow_context_anchors,
        "failed_image_zones": failed_image_zones,
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
        "central_text_box_delta_pt": {
            "left": round(left_delta or 0.0, 3),
            "right": round(right_delta or 0.0, 3),
            "width": round(width_delta or 0.0, 3),
            "rule": "Central-band text extent is diagnostic only; it does not prove page geometry without body-anchor corroboration.",
        },
        "body_anchor_horizontal_evidence": body_anchor_evidence,
        "max_anchor_top_delta_pt": {key: round(value, 3) for key, value in sorted(anchor_max.items())},
        "anchor_page_shifts": anchor_page_shifts,
        "missing_or_asymmetric_anchors": missing_anchors,
        "cause_scores": {key: round(value, 6) for key, value in sorted(cause_scores.items())},
        "top_causes": (top_causes or ["minor_visual_difference"]) if (semantic_comparable or zone_comparable) else ["same_content_anchor_evidence_missing"],
        "calibration_hints": calibration_hints,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_pdf")
    parser.add_argument("generated_pdf")
    parser.add_argument("--outdir", default="layout-profile")
    parser.add_argument("--max-pages", type=int, default=8)
    parser.add_argument("--anchors-json", help="Optional anchor map. A partial_zone map may declare page_fixed zones with page rectangles or flow_relative zones tied to a same-page context anchor.")
    args = parser.parse_args()

    global ANCHOR_PROFILE_VERSION, CONTRACT_SCOPE, ANCHOR_ZONE_SPECS, ANCHOR_ZONE_NAMES, ANCHOR_MAX_BBOX_DELTAS, ANCHOR_PLACEMENT_MODELS, ANCHOR_CONTEXTS, ANCHOR_SOURCE_EVIDENCE_IDS
    if args.anchors_json:
        (
            custom_anchors,
            ANCHOR_PROFILE_VERSION,
            CONTRACT_SCOPE,
            ANCHOR_ZONE_SPECS,
            ANCHOR_ZONE_NAMES,
            ANCHOR_MAX_BBOX_DELTAS,
            ANCHOR_PLACEMENT_MODELS,
            ANCHOR_CONTEXTS,
            ANCHOR_SOURCE_EVIDENCE_IDS,
        ) = load_anchor_map(Path(args.anchors_json).expanduser().resolve())
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
    reference_text_contract = document_text_contract(ref_pdf, ANCHORS)
    generated_text_contract = document_text_contract(gen_pdf, ANCHORS)
    comparisons = []
    if ref_profile.get("available") and gen_profile.get("available"):
        for ref_page, gen_page in zip(ref_profile.get("pages", []), gen_profile.get("pages", [])):
            comparisons.append(compare_page(ref_page, gen_page))
    document_anchor_deltas = compare_document_anchors(ref_profile, gen_profile) if comparisons else {}
    document_zone_deltas = compare_document_zones(ref_profile, gen_profile) if comparisons else {}
    report = {
        "anchor_profile_version": ANCHOR_PROFILE_VERSION,
        "anchor_map": ANCHORS,
        "anchor_zones": ANCHOR_ZONE_NAMES,
        "anchor_max_bbox_deltas": ANCHOR_MAX_BBOX_DELTAS,
        "anchor_placement_models": ANCHOR_PLACEMENT_MODELS,
        "anchor_contexts": ANCHOR_CONTEXTS,
        "anchor_source_evidence_ids": ANCHOR_SOURCE_EVIDENCE_IDS,
        "zones": ANCHOR_ZONE_SPECS,
        "contract_scope": CONTRACT_SCOPE,
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
        "document_zone_deltas": document_zone_deltas,
        "same_content_text_contract": {
            "reference": reference_text_contract,
            "generated": generated_text_contract,
            "rule": "Text-contract presence is structural evidence only; every anchor also needs a positioned match before layout calibration.",
        },
        "summary": summarize(
            comparisons,
            document_anchor_deltas,
            document_zone_deltas,
            reference_text_contract,
            generated_text_contract,
            CONTRACT_SCOPE,
            ref_profile.get("total_page_count", len(ref_profile.get("pages", []))),
            gen_profile.get("total_page_count", len(gen_profile.get("pages", []))),
        ) if comparisons else {
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
