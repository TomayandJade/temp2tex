#!/usr/bin/env python3
"""Preflight Temp2TeX regression manifests before expensive PDF regression.

The preflight gate verifies that each case has traceable official source metadata,
downloads a real Word/DOCX artifact, rejects HTML/challenge payloads, records a
hash, and renders the selected Word source to PDF when a renderer is available.
Official LaTeX declarations are inventoried, but LaTeX downloads are deferred to
the full regression and are not required for admission.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import run_regression as rr


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def preflight_case(case: dict, case_root: Path, skip_network: bool, skip_render: bool) -> dict:
    source_pages = case_root / "source_pages"
    downloads = case_root / "downloads"
    inputs = case_root / "inputs"
    official_latex = case_root / "official_latex_source"
    for path in (source_pages, downloads, inputs, official_latex):
        path.mkdir(parents=True, exist_ok=True)

    direct_word_configured = bool(case.get("doc_template_url") or case.get("local_word_paths"))
    if direct_word_configured:
        page_reports, discovered = [], []
    else:
        page_reports, discovered = rr.capture_source_pages(case, source_pages, skip_network)
    links = rr.add_explicit_links(case, discovered)
    word_links = [link for link in links if link.get("classification") == "word"]
    download_reports = rr.download_artifacts(
        word_links,
        downloads,
        skip_network,
        max_valid_per_kind=1,
        fetch_timeout=20,
    )
    local_word_reports = rr.copy_local_word_inputs(case, inputs)
    downloaded_word_reports = rr.collect_downloaded_word_sources(downloads, inputs)
    extraction_reports, official_main_tex = rr.prepare_official_latex_sources(
        downloads,
        official_latex,
        preferred_patterns=case.get("preferred_latex_main_patterns"),
    )
    word_source = rr.choose_word_source(inputs, preferred_patterns=case.get("preferred_word_patterns"))

    render_report = {"success": False, "skipped": skip_render}
    if word_source and not skip_render:
        render_report = rr.render_word_reference(word_source, case_root / "word_reference_render")

    source_metadata_present = bool(case.get("source_page_urls"))
    official_latex_declared = bool(case.get("latex_template_url"))
    word_ready = bool(word_source)
    render_ready = bool(word_source and (skip_render or render_report.get("success")))
    admitted = source_metadata_present and word_ready and render_ready
    issues: list[str] = []
    if not source_metadata_present:
        issues.append("missing official source page URL")
    if not word_ready:
        issues.append("no valid official Word/DOCX/DOT/RTF artifact obtained")
    elif not render_ready:
        issues.append("official Word source did not render to PDF")

    result = {
        "case_id": case["case_id"],
        "publisher": case.get("publisher"),
        "journal_or_template_system": case.get("journal_or_template_system"),
        "status": "admitted" if admitted else "rejected",
        "source_metadata_present": source_metadata_present,
        "source_page_usable": any(report.get("ok") for report in page_reports),
        "source_page_fetch_skipped": direct_word_configured,
        "word_source": str(word_source) if word_source else None,
        "word_sha256": rr.sha256_file(word_source) if word_source else None,
        "word_render_success": bool(render_report.get("success")) if not skip_render else None,
        "word_reference_pdf": render_report.get("pdf"),
        "official_latex_declared": official_latex_declared,
        "official_main_tex": str(official_main_tex) if official_main_tex else None,
        "official_latex_available": bool(official_main_tex),
        "word_render_fallback_ready": render_ready,
        "comparison_mode": "official_latex" if official_main_tex else ("word_render_fallback" if word_source else "missing_reference_source"),
        "issues": issues,
        "source_page_reports": page_reports,
        "discovered_links": links,
        "download_reports": download_reports,
        "local_word_reports": local_word_reports,
        "downloaded_word_reports": downloaded_word_reports,
        "latex_extraction_reports": extraction_reports,
        "word_render": render_report,
    }
    write_json(case_root / "preflight_report.json", result)
    return result


def markdown_summary(summary: dict) -> str:
    lines = [
        "# Temp2TeX Corpus Preflight",
        "",
        f"- Total: {summary['total']}",
        f"- Admitted: {summary['admitted']}",
        f"- Rejected: {summary['rejected']}",
        f"- Official LaTeX declared: {summary['official_latex_declared']}",
        f"- Official LaTeX downloaded locally: {summary['official_latex_available']}",
        f"- Word-render fallback ready: {summary['word_render_fallback_ready']}",
        "",
        "| Case | Status | Mode | Word render | LaTeX local | Issues |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in summary["cases"]:
        issues = "; ".join(case.get("issues") or [])
        render = "yes" if case.get("word_render_success") else ("skipped" if case.get("word_render_success") is None else "no")
        latex = "yes" if case.get("official_latex_available") else "no"
        lines.append(
            f"| {case['case_id']} | {case['status']} | {case['comparison_mode']} | {render} | {latex} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", action="append", required=True, help="Manifest path; repeat for multiple batches.")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--cases", nargs="*")
    parser.add_argument("--skip-network", action="store_true")
    parser.add_argument("--skip-render", action="store_true")
    args = parser.parse_args()

    selected = set(args.cases or [])
    cases: list[dict] = []
    seen: set[str] = set()
    manifests: list[str] = []
    for manifest_path in args.manifest:
        path = Path(manifest_path)
        manifest = rr.read_json(path)
        manifests.append(str(path))
        for case in manifest.get("cases", []):
            case_id = case["case_id"]
            if selected and case_id not in selected:
                continue
            if case_id in seen:
                raise ValueError(f"duplicate case_id across manifests: {case_id}")
            seen.add(case_id)
            cases.append(case)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    results = [
        preflight_case(case, outdir / case["case_id"], args.skip_network, args.skip_render)
        for case in cases
    ]
    summary = {
        "generated_at": rr.utc_now(),
        "manifests": manifests,
        "total": len(results),
        "admitted": sum(case["status"] == "admitted" for case in results),
        "rejected": sum(case["status"] == "rejected" for case in results),
        "official_latex_declared": sum(case["official_latex_declared"] for case in results),
        "official_latex_available": sum(case["official_latex_available"] for case in results),
        "word_render_fallback_ready": sum(case["word_render_fallback_ready"] for case in results),
        "word_render_fallback": sum(case["comparison_mode"] == "word_render_fallback" for case in results),
        "cases": results,
    }
    write_json(outdir / "preflight_summary.json", summary)
    (outdir / "preflight_summary.md").write_text(markdown_summary(summary), encoding="utf-8")
    print(outdir / "preflight_summary.json")
    return 0 if summary["rejected"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
