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


def image_diff(ref: Path, gen: Path, diff: Path) -> dict:
    try:
        from PIL import Image, ImageChops, ImageStat  # type: ignore
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
        delta.save(diff)
    return {"available": True, "mean_abs_diff": mean, "normalized_diff": score, "diff_image": str(diff)}


def layout_diagnostics(reference_pdf: Path, generated_pdf: Path, outdir: Path, max_pages: int) -> dict:
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

    comparisons = []
    for idx, (ref_img, gen_img) in enumerate(zip(rendered_ref, rendered_gen), 1):
        diff_dir.mkdir(parents=True, exist_ok=True)
        comparisons.append({
            "page": idx,
            "reference_image": str(ref_img),
            "generated_image": str(gen_img),
            "diff": image_diff(ref_img, gen_img, diff_dir / f"page-{idx:03d}-diff.png"),
        })

    issues = []
    if ref_pages and gen_pages and len(ref_pages) != len(gen_pages):
        issues.append(f"Page count differs: reference={len(ref_pages)}, generated={len(gen_pages)}")
    if not rendered_ref or not rendered_gen:
        issues.append("PDF image rendering did not run; ensure pdftoppm is available.")
    if comparisons:
        high = [c for c in comparisons if c["diff"].get("normalized_diff", 0) > 0.20]
        if high:
            issues.append(f"{len(high)} compared page(s) have high visual difference; inspect diff_previews.")
    layout_report = layout_diagnostics(ref_pdf, gen_pdf, outdir, args.max_pages)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reference_pdf": str(ref_pdf),
        "generated_pdf": str(gen_pdf),
        "reference_pages": ref_pages,
        "generated_pages": gen_pages,
        "rendering": {"reference": ref_render_report, "generated": gen_render_report},
        "comparisons": comparisons,
        "layout_diagnostics": layout_report,
        "issues": issues,
    }
    outdir.mkdir(parents=True, exist_ok=True)
    report_path = outdir / "render_compare_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(report_path)
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
