#!/usr/bin/env python3
"""Compare two PDFs by page metadata and rendered page images."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def pdf_pages(path: Path) -> list[dict]:
    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(str(path))
        pages = []
        for idx, page in enumerate(reader.pages, 1):
            box = page.mediabox
            pages.append({"index": idx, "width_pt": float(box.width), "height_pt": float(box.height)})
        return pages
    except Exception:
        pass
    candidates = tool_candidates("pdfinfo")
    if not candidates:
        return []
    try:
        proc = subprocess.run([candidates[0], str(path)], text=True, capture_output=True, timeout=20)
        page_count = None
        width = None
        height = None
        for line in proc.stdout.splitlines():
            lower = line.lower()
            if lower.startswith("pages:"):
                page_count = int(line.split(":", 1)[1].strip())
            elif lower.startswith("page size:"):
                parts = line.split(":", 1)[1].strip().split()
                if len(parts) >= 3:
                    width = float(parts[0])
                    height = float(parts[2])
        if page_count:
            return [{"index": idx, "width_pt": width, "height_pt": height} for idx in range(1, page_count + 1)]
    except Exception:
        return []
    return []


def tool_candidates(name: str) -> list[str]:
    candidates = []
    preferred = [
        Path(r"D:\texlive\2025\bin\windows") / f"{name}.exe",
        Path(r"C:\Program Files\MiKTeX\miktex\bin\x64") / f"{name}.exe",
    ]
    candidates.extend(str(p) for p in preferred if p.exists())
    try:
        proc = subprocess.run(["where.exe", name], text=True, capture_output=True)
        if proc.returncode == 0:
            candidates.extend(line.strip() for line in proc.stdout.splitlines() if line.strip())
    except Exception:
        pass
    unique = []
    for item in candidates:
        if item not in unique:
            unique.append(item)
    unique.sort(key=lambda p: (0 if p.lower().endswith(".exe") else 1, 0 if "texlive" in p.lower() else 1, p.lower()))
    return unique


def render_pdf(pdf: Path, outdir: Path, prefix: str, dpi: int, max_pages: int) -> tuple[list[Path], dict]:
    pdftoppm_candidates = tool_candidates("pdftoppm")
    pdftoppm = pdftoppm_candidates[0] if pdftoppm_candidates else None
    if not pdftoppm:
        return [], {"success": False, "error": "pdftoppm not found", "candidates": []}
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [pdftoppm, "-png", "-r", str(dpi), "-f", "1", "-l", str(max_pages), str(pdf), str(outdir / prefix)]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    pages = sorted(outdir.glob(f"{prefix}-*.png"))
    return pages, {
        "success": proc.returncode == 0 and bool(pages),
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
        "candidates": pdftoppm_candidates,
    }


def pdf_graphic_regions(path: Path, dpi: int, max_pages: int) -> dict:
    """Find embedded raster artwork rectangles for content-insensitive comparison.

    The rectangles are evidence for image geometry. Their interiors are masked
    only in the format metric: figure borders, caption placement, page flow,
    and every non-image region remain comparable.
    """
    try:
        import pdfplumber  # type: ignore
    except Exception as exc:
        return {"available": False, "error": f"pdfplumber unavailable: {exc}", "pages": []}
    pages = []
    try:
        with pdfplumber.open(str(path)) as pdf:
            for page_index, page in enumerate(pdf.pages[:max_pages], 1):
                scale = dpi / 72.0
                rectangles = []
                for image in page.images:
                    try:
                        x0 = max(0.0, float(image["x0"]) * scale)
                        x1 = min(float(page.width) * scale, float(image["x1"]) * scale)
                        y0 = max(0.0, float(image["top"]) * scale)
                        y1 = min(float(page.height) * scale, float(image["bottom"]) * scale)
                    except (KeyError, TypeError, ValueError):
                        continue
                    if x1 - x0 >= 12 and y1 - y0 >= 12:
                        rectangles.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1})
                pages.append({"page": page_index, "regions": rectangles})
    except Exception as exc:
        return {"available": False, "error": str(exc), "pages": []}
    return {"available": True, "pages": pages}


def page_graphic_regions(report: dict, page: int) -> list[dict]:
    for record in report.get("pages", []):
        if record.get("page") == page:
            return record.get("regions", [])
    return []


def graphic_geometry_diff(reference: list[dict], generated: list[dict], width: int, height: int) -> dict:
    """Compare embedded-image boxes without looking at their raster content."""
    if not reference and not generated:
        return {
            "status": "not_applicable",
            "reference_region_count": 0,
            "generated_region_count": 0,
            "matched_region_count": 0,
            "unmatched_reference_count": 0,
            "unmatched_generated_count": 0,
            "mean_normalized_box_error": 0.0,
            "max_normalized_box_error": 0.0,
        }

    def metric(left: dict, right: dict) -> float:
        try:
            lx0, ly0, lx1, ly1 = (float(left[key]) for key in ("x0", "y0", "x1", "y1"))
            rx0, ry0, rx1, ry1 = (float(right[key]) for key in ("x0", "y0", "x1", "y1"))
        except (KeyError, TypeError, ValueError):
            return float("inf")
        lw, lh = max(1.0, lx1 - lx0), max(1.0, ly1 - ly0)
        rw, rh = max(1.0, rx1 - rx0), max(1.0, ry1 - ry0)
        return (
            abs(((lx0 + lx1) - (rx0 + rx1)) / 2.0) / max(1.0, float(width))
            + abs(((ly0 + ly1) - (ry0 + ry1)) / 2.0) / max(1.0, float(height))
            + 0.5 * abs(lw - rw) / max(1.0, float(width))
            + 0.5 * abs(lh - rh) / max(1.0, float(height))
        )

    pending = list(generated)
    errors: list[float] = []
    for ref in reference:
        if not pending:
            break
        best_index, best_error = min(
            enumerate(metric(ref, candidate) for candidate in pending),
            key=lambda item: item[1],
        )
        if best_error == float("inf"):
            continue
        pending.pop(best_index)
        errors.append(best_error)
    return {
        "status": "compared",
        "reference_region_count": len(reference),
        "generated_region_count": len(generated),
        "matched_region_count": len(errors),
        "unmatched_reference_count": max(0, len(reference) - len(errors)),
        "unmatched_generated_count": len(pending),
        "mean_normalized_box_error": sum(errors) / len(errors) if errors else None,
        "max_normalized_box_error": max(errors) if errors else None,
    }


def image_diff(
    ref: Path,
    gen: Path,
    diff: Path,
    ignored_graphics: list[dict] | None = None,
    graphic_frame_band_px: int = 3,
) -> dict:
    try:
        from PIL import Image, ImageChops, ImageDraw, ImageOps, ImageStat  # type: ignore
    except Exception as exc:
        return {"available": False, "error": f"Install Pillow for pixel diff: {exc}"}

    with Image.open(ref).convert("RGB") as a, Image.open(gen).convert("RGB") as b:
        width = max(a.width, b.width)
        height = max(a.height, b.height)
        canvas_a = Image.new("RGB", (width, height), "white")
        canvas_b = Image.new("RGB", (width, height), "white")
        canvas_a.paste(a, (0, 0))
        canvas_b.paste(b, (0, 0))
        delta = ImageChops.difference(canvas_a, canvas_b)
        stat = ImageStat.Stat(delta)
        mean = sum(stat.mean) / len(stat.mean)
        score = mean / 255.0
        # Whole-page averages are dominated by white paper. Measure the delta
        # again only where either PDF renders visible ink so sparse layouts do
        # not receive an artificially small difference score.
        threshold = 245
        ref_ink = ImageOps.grayscale(canvas_a).point(lambda value: 255 if value < threshold else 0)
        gen_ink = ImageOps.grayscale(canvas_b).point(lambda value: 255 if value < threshold else 0)
        ink_union = ImageChops.lighter(ref_ink, gen_ink)
        ink_intersection = ImageChops.darker(ref_ink, gen_ink)
        union_pixels = ink_union.histogram()[255]
        intersection_pixels = ink_intersection.histogram()[255]
        reference_pixels = ref_ink.histogram()[255]
        generated_pixels = gen_ink.histogram()[255]
        grayscale_delta = ImageOps.grayscale(delta)
        masked_delta = ImageChops.multiply(grayscale_delta, ink_union)
        masked_sum = ImageStat.Stat(masked_delta).sum[0]
        ink_weighted_diff = masked_sum / (union_pixels * 255.0) if union_pixels else 0.0
        delta.save(diff)
        comparison_mask = Image.new("L", (width, height), "white")
        mask_draw = ImageDraw.Draw(comparison_mask)
        # Image placement is checked separately from these rectangles. Mask
        # only raster interiors: preserve a narrow perimeter so a visible frame
        # or rule remains part of the format metric, while differing artwork
        # pixels cannot dominate it.
        border_px = max(0, int(graphic_frame_band_px))
        masked_regions = 0
        for region in ignored_graphics or []:
            try:
                x0 = max(0, min(width, round(float(region["x0"]) + border_px)))
                y0 = max(0, min(height, round(float(region["y0"]) + border_px)))
                x1 = max(0, min(width, round(float(region["x1"]) - border_px)))
                y1 = max(0, min(height, round(float(region["y1"]) - border_px)))
            except (KeyError, TypeError, ValueError):
                continue
            if x1 > x0 and y1 > y0:
                mask_draw.rectangle((x0, y0, x1, y1), fill=0)
                masked_regions += 1
        mask_histogram = comparison_mask.histogram()
        compared_pixels = mask_histogram[255]
        format_delta = ImageChops.multiply(grayscale_delta, comparison_mask)
        format_delta.save(diff.with_name(diff.stem + "-format" + diff.suffix))
        format_ref_ink = ImageChops.multiply(ref_ink, comparison_mask)
        format_gen_ink = ImageChops.multiply(gen_ink, comparison_mask)
        format_union = ImageChops.lighter(format_ref_ink, format_gen_ink)
        format_intersection = ImageChops.darker(format_ref_ink, format_gen_ink)
        format_union_pixels = format_union.histogram()[255]
        format_intersection_pixels = format_intersection.histogram()[255]
        format_delta_sum = ImageStat.Stat(format_delta).sum[0]
        format_ink_delta = ImageChops.multiply(format_delta, format_union)
        format_ink_sum = ImageStat.Stat(format_ink_delta).sum[0]
        format_ink_weighted_diff = format_ink_sum / (format_union_pixels * 255.0) if format_union_pixels else 0.0
        format_normalized_diff = format_delta_sum / (compared_pixels * 255.0) if compared_pixels else 0.0
    total_pixels = width * height
    return {
        "available": True,
        "mean_abs_diff": mean,
        "normalized_diff": score,
        "ink_weighted_diff": ink_weighted_diff,
        "reference_ink_ratio": reference_pixels / total_pixels,
        "generated_ink_ratio": generated_pixels / total_pixels,
        "ink_union_ratio": union_pixels / total_pixels,
        "ink_iou": intersection_pixels / union_pixels if union_pixels else 1.0,
        "diff_image": str(diff),
        "format_normalized_diff": format_normalized_diff,
        "format_ink_weighted_diff": format_ink_weighted_diff,
        "format_ink_iou": format_intersection_pixels / format_union_pixels if format_union_pixels else 1.0,
        "format_diff_image": str(diff.with_name(diff.stem + "-format" + diff.suffix)),
        "canvas_width_px": width,
        "canvas_height_px": height,
        "ignored_graphic_interior_regions": masked_regions,
        "ignored_graphic_interior_pixels": total_pixels - compared_pixels,
        "preserved_graphic_frame_band_px": border_px,
    }


def layout_diagnostics(
    reference_pdf: Path,
    generated_pdf: Path,
    outdir: Path,
    max_pages: int,
    anchors_json: Path | None = None,
) -> dict:
    layout_dir = outdir / "layout_profile"
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "profile_pdf_layout.py"),
        str(reference_pdf),
        str(generated_pdf),
        "--outdir",
        str(layout_dir),
        "--max-pages",
        str(max_pages),
    ]
    if anchors_json:
        cmd.extend(["--anchors-json", str(anchors_json)])
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=90)
    except Exception as exc:
        return {"available": False, "error": str(exc), "cmd": cmd}
    report_path = layout_dir / "layout_diagnostics.json"
    report = {
        "available": False,
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
        "report": str(report_path),
    }
    if report_path.exists():
        try:
            report.update(json.loads(report_path.read_text(encoding="utf-8")))
        except Exception as exc:
            report["read_error"] = str(exc)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_pdf")
    parser.add_argument("generated_pdf")
    parser.add_argument("--outdir", default="render-compare")
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--max-pages", type=int, default=8)
    parser.add_argument("--anchors-json", help="Optional unique same-content anchor map forwarded to profile_pdf_layout.py")
    args = parser.parse_args()

    ref_pdf = Path(args.reference_pdf).expanduser().resolve()
    gen_pdf = Path(args.generated_pdf).expanduser().resolve()
    if not ref_pdf.exists() or not gen_pdf.exists():
        print("both PDF paths must exist", file=sys.stderr)
        return 2

    outdir = Path(args.outdir).expanduser().resolve()
    pages_dir = outdir / "pages"
    diff_dir = outdir / "diff_previews"
    ref_pages = pdf_pages(ref_pdf)
    gen_pages = pdf_pages(gen_pdf)
    rendered_ref, ref_render_report = render_pdf(ref_pdf, pages_dir, "reference", args.dpi, args.max_pages)
    rendered_gen, gen_render_report = render_pdf(gen_pdf, pages_dir, "generated", args.dpi, args.max_pages)
    reference_graphics = pdf_graphic_regions(ref_pdf, args.dpi, args.max_pages)
    generated_graphics = pdf_graphic_regions(gen_pdf, args.dpi, args.max_pages)
    graphic_frame_band_px = max(2, round(args.dpi / 72.0 * 1.25))

    comparisons = []
    for idx, (ref_img, gen_img) in enumerate(zip(rendered_ref, rendered_gen), 1):
        diff_dir.mkdir(parents=True, exist_ok=True)
        reference_regions = page_graphic_regions(reference_graphics, idx)
        generated_regions = page_graphic_regions(generated_graphics, idx)
        ignored_graphics = reference_regions + generated_regions
        diff = image_diff(
            ref_img,
            gen_img,
            diff_dir / f"page-{idx:03d}-diff.png",
            ignored_graphics,
            graphic_frame_band_px,
        )
        geometry = graphic_geometry_diff(
            reference_regions,
            generated_regions,
            int(diff.get("canvas_width_px") or 1),
            int(diff.get("canvas_height_px") or 1),
        )
        comparisons.append({
            "page": idx,
            "reference_image": str(ref_img),
            "generated_image": str(gen_img),
            "reference_graphic_regions": reference_regions,
            "generated_graphic_regions": generated_regions,
            "graphic_geometry": geometry,
            "diff": diff,
        })

    issues = []
    if ref_pages and gen_pages and len(ref_pages) != len(gen_pages):
        issues.append(f"Page count differs: reference={len(ref_pages)}, generated={len(gen_pages)}")
    if not rendered_ref or not rendered_gen:
        issues.append("PDF image rendering did not run; ensure pdftoppm is available.")
    if comparisons:
        high = [
            c for c in comparisons
            if c["diff"].get("format_normalized_diff", c["diff"].get("normalized_diff", 0)) > 0.20
            or (
                not c["reference_graphic_regions"] and not c["generated_graphic_regions"]
                and c["diff"].get("format_ink_weighted_diff", c["diff"].get("ink_weighted_diff", 0)) > 0.20
            )
            or c["graphic_geometry"].get("unmatched_reference_count", 0) > 0
            or c["graphic_geometry"].get("unmatched_generated_count", 0) > 0
            or (c["graphic_geometry"].get("max_normalized_box_error") or 0.0) > 0.02
        ]
        if high:
            issues.append(f"{len(high)} compared page(s) have high visual difference; inspect diff_previews.")
    anchors_json = Path(args.anchors_json).expanduser().resolve() if args.anchors_json else None
    if anchors_json and not anchors_json.is_file():
        print(f"--anchors-json does not exist: {anchors_json}", file=sys.stderr)
        return 2
    layout_report = layout_diagnostics(ref_pdf, gen_pdf, outdir, args.max_pages, anchors_json)
    layout_summary = layout_report.get("summary") if isinstance(layout_report, dict) else None
    semantic_comparable = layout_summary.get("semantic_comparable") if isinstance(layout_summary, dict) else None
    zone_comparable = layout_summary.get("zone_comparable") if isinstance(layout_summary, dict) else None
    contract_scope = layout_summary.get("contract_scope") if isinstance(layout_summary, dict) else None
    if semantic_comparable is True:
        comparability_status = "comparable"
    elif zone_comparable is True:
        comparability_status = "partial_zone_only"
    elif semantic_comparable is False:
        comparability_status = "not_comparable"
    else:
        comparability_status = "unavailable"
    layout_comparability = {
        "status": comparability_status,
        "contract_scope": contract_scope,
        "semantic_comparable": semantic_comparable,
        "zone_comparable": zone_comparable,
        "shared_anchor_count": layout_summary.get("shared_anchor_count") if isinstance(layout_summary, dict) else None,
        "required_anchor_count": layout_summary.get("required_anchor_count") if isinstance(layout_summary, dict) else None,
        "same_content_contract_status": layout_summary.get("same_content_contract_status") if isinstance(layout_summary, dict) else None,
        "text_contract_status": layout_summary.get("text_contract_status") if isinstance(layout_summary, dict) else None,
        "geometry_contract_status": layout_summary.get("geometry_contract_status") if isinstance(layout_summary, dict) else None,
        "local_zone_gate_status": layout_summary.get("local_zone_gate_status") if isinstance(layout_summary, dict) else None,
        "out_of_tolerance_anchors": layout_summary.get("out_of_tolerance_anchors") if isinstance(layout_summary, dict) else [],
        "failed_flow_context_anchors": layout_summary.get("failed_flow_context_anchors") if isinstance(layout_summary, dict) else [],
        "failed_image_zones": layout_summary.get("failed_image_zones") if isinstance(layout_summary, dict) else [],
        "rule": "Full class calibration requires a full_document contract. A partial_zone contract may calibrate only its declared local zone; flow-relative anchors require their declared same-page context.",
    }
    if layout_comparability["status"] == "not_comparable":
        issues.append("The same-content anchor contract is incomplete; do not use this PDF pair for class calibration.")
    elif layout_comparability["status"] == "partial_zone_only":
        issues.append("This PDF pair is comparable only for its declared local zone; do not use it for whole-class calibration.")
    if layout_comparability["local_zone_gate_status"] == "failed":
        issues.append("The declared local-zone gate failed; do not promote the affected page-furniture candidate.")
    if layout_comparability["failed_flow_context_anchors"]:
        issues.append("A flow-relative zone lost its required same-page context; do not use it for placement calibration.")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reference_pdf": str(ref_pdf),
        "generated_pdf": str(gen_pdf),
        "reference_pages": ref_pages,
        "generated_pages": gen_pages,
        "rendering": {"reference": ref_render_report, "generated": gen_render_report},
        "graphic_content_policy": {
            "mode": "mask_embedded_graphic_interiors_for_format_metric",
            "rule": "Ignore raster image interiors only; retain a perimeter band for image borders/frames plus geometry, captions, page flow, tables, and text in the format comparison.",
            "preserved_graphic_frame_band_px": graphic_frame_band_px,
            "reference": reference_graphics,
            "generated": generated_graphics,
        },
        "comparisons": comparisons,
        "layout_diagnostics": layout_report,
        "layout_comparability": layout_comparability,
        "issues": issues,
    }
    outdir.mkdir(parents=True, exist_ok=True)
    report_path = outdir / "render_compare_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(report_path)
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
