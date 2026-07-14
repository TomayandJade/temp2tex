#!/usr/bin/env python3
"""Aggregate Temp2TeX regression runs into a training-signal report."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_rows(label: str, run_dir: Path) -> list[dict]:
    bench = read_json(run_dir / "benchmark.json")
    rows = []
    for run in bench.get("runs", []):
        case_id = run.get("eval_name")
        case_dir = run_dir / case_id
        evaluation = read_json(case_dir / "evaluation.json") if (case_dir / "evaluation.json").exists() else {}
        report = read_json(case_dir / "case_report.json") if (case_dir / "case_report.json").exists() else {}
        comparison_mode = report.get("comparison_mode") or evaluation.get("comparison_mode") or "official_latex"
        word_reference_success = bool(report.get("word_reference_render", {}).get("success"))
        reference_compile = word_reference_success if comparison_mode == "word_render_fallback" else report.get("official_compile", {}).get("success")
        rows.append({
            "batch": label,
            "case": case_id,
            "comparison_mode": comparison_mode,
            "status": evaluation.get("status"),
            "pass_rate": run.get("result", {}).get("pass_rate"),
            "word_source": bool(report.get("word_source")),
            "official_latex_source": bool(report.get("official_main_tex")),
            "word_reference_render": word_reference_success,
            "reference_compile": reference_compile,
            "official_compile": report.get("official_compile", {}).get("success"),
            "temp2tex_compile": report.get("temp_compile", {}).get("success"),
            "same_page_count": evaluation.get("same_page_count"),
            "same_page_size": evaluation.get("same_page_size"),
            "missing_official_zones": evaluation.get("missing_text_zones_official") or [],
            "missing_temp2tex_zones": evaluation.get("missing_text_zones_temp2tex") or [],
            "average_normalized_diff": evaluation.get("average_normalized_diff"),
            "max_normalized_diff": evaluation.get("max_normalized_diff"),
            "layout_penalty": evaluation.get("layout_penalty"),
            "layout_visual_causes": evaluation.get("layout_visual_causes") or [],
            "compare_issues": evaluation.get("compare_issues") or [],
            "hard_gate_passed": evaluation.get("hard_gate_passed"),
            "visual_passed": evaluation.get("visual_passed"),
        })
    return rows


def summarize(rows: list[dict]) -> dict:
    return {
        "total": len(rows),
        "passed": sum(1 for row in rows if row["status"] == "passed"),
        "failed": sum(1 for row in rows if row["status"] == "failed"),
        "not_comparable": sum(1 for row in rows if row["status"] == "not_comparable"),
        "official_latex_mode": sum(1 for row in rows if row["comparison_mode"] == "official_latex"),
        "word_render_fallback_mode": sum(1 for row in rows if row["comparison_mode"] == "word_render_fallback"),
        "word_render_success": sum(1 for row in rows if row["word_reference_render"]),
        "both_compile": sum(1 for row in rows if row["reference_compile"] and row["temp2tex_compile"]),
        "missing_word_source": sum(1 for row in rows if not row["word_source"]),
        "missing_official_latex_source": sum(1 for row in rows if not row["official_latex_source"]),
        "official_compile_fail": sum(1 for row in rows if row["official_latex_source"] and not row["official_compile"]),
        "reference_compile_fail": sum(1 for row in rows if row["word_source"] and not row["reference_compile"]),
        "temp2tex_compile_fail": sum(1 for row in rows if row["word_source"] and not row["temp2tex_compile"]),
        "page_count_fail": sum(1 for row in rows if row["same_page_count"] is False),
        "page_size_fail": sum(1 for row in rows if row["same_page_size"] is False),
        "missing_official_zones": sum(1 for row in rows if row["missing_official_zones"]),
        "missing_temp2tex_zones": sum(1 for row in rows if row["missing_temp2tex_zones"]),
        "visual_fail_after_hard_gate": sum(1 for row in rows if row["hard_gate_passed"] and not row["visual_passed"]),
        "layout_diagnostics_available": sum(1 for row in rows if row["layout_penalty"] is not None),
    }


def comparison_mode_switches(rows: list[dict]) -> list[dict]:
    """Report cases whose reference source changed across compared runs.

    Visual metrics from official-LaTeX and Word-render fallback comparisons are
    not directly comparable. Keeping the switch explicit prevents a download
    or compiler recovery from being misread as a Temp2TeX regression.
    """
    by_case: dict[str, list[dict]] = {}
    for row in rows:
        by_case.setdefault(str(row.get("case")), []).append(row)
    switches = []
    for case, entries in sorted(by_case.items()):
        modes = {str(entry.get("comparison_mode")) for entry in entries}
        if len(modes) > 1:
            switches.append({
                "case": case,
                "modes": sorted(modes),
                "batches": [{"batch": entry.get("batch"), "comparison_mode": entry.get("comparison_mode")} for entry in entries],
                "note": "Do not compare visual/layout metrics across these rows until the reference mode is stable.",
            })
    return switches


def fmt_bool(value) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return ""


def fmt_float(value) -> str:
    return "" if value is None else f"{float(value):.5f}"


def markdown_report(data: dict) -> str:
    lines = [
        "# Temp2TeX Regression Training Signal",
        "",
        f"Generated: {data['generated_at']}",
        "",
        "## Summary",
        "",
    ]
    for key, value in data["summary"].items():
        lines.append(f"- {key}: {value}")
    if data.get("comparison_mode_switches"):
        lines.extend(["", "## Reference Mode Switches", ""])
        for switch in data["comparison_mode_switches"]:
            details = ", ".join(f"{item['batch']}={item['comparison_mode']}" for item in switch["batches"])
            lines.append(f"- `{switch['case']}`: {details}. {switch['note']}")
    lines.extend([
        "",
        "## Case Table",
        "",
        "| Batch | Case | Mode | Status | Both compile | Same pages | Same size | Avg diff | Max diff | Layout penalty | Layout causes | Main blocker |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |",
    ])
    for row in data["rows"]:
        blockers = []
        if not row["word_source"]:
            blockers.append("missing Word source")
        if not row["official_latex_source"] and row["comparison_mode"] != "word_render_fallback":
            blockers.append("missing official LaTeX")
        if row["comparison_mode"] == "word_render_fallback":
            blockers.append("using Word-render fallback")
        if row["comparison_mode"] == "word_render_fallback" and not row["word_reference_render"]:
            blockers.append("Word render failed")
        if row["official_latex_source"] and not row["official_compile"]:
            blockers.append("official compile failed")
        if row["word_source"] and not row["temp2tex_compile"]:
            blockers.append("temp2tex compile failed")
        if row["same_page_count"] is False:
            blockers.append("page count")
        if row["same_page_size"] is False:
            blockers.append("page size")
        if row["missing_official_zones"]:
            blockers.append("official zones: " + ", ".join(row["missing_official_zones"]))
        if row["missing_temp2tex_zones"]:
            blockers.append("temp2tex zones: " + ", ".join(row["missing_temp2tex_zones"]))
        if row["hard_gate_passed"] and not row["visual_passed"]:
            blockers.append("visual diff")
        lines.append(
            "| {batch} | {case} | {mode} | {status} | {compile} | {pages} | {size} | {avg} | {max} | {layout} | {causes} | {blocker} |".format(
                batch=row["batch"],
                case=row["case"],
                mode=row["comparison_mode"],
                status=row["status"],
                compile=fmt_bool(row["reference_compile"] and row["temp2tex_compile"]),
                pages=fmt_bool(row["same_page_count"]),
                size=fmt_bool(row["same_page_size"]),
                avg=fmt_float(row["average_normalized_diff"]),
                max=fmt_float(row["max_normalized_diff"]),
                layout=fmt_float(row["layout_penalty"]),
                causes=", ".join(row["layout_visual_causes"]),
                blocker="; ".join(blockers) or "strict visual/layout gate",
            )
        )
    lines.extend([
        "",
        "## Training Priorities",
        "",
        "1. Restore comparability first: missing sources and official compile failures block useful visual learning.",
        "2. For comparable cases, fix page count and page size before chasing pixel-level differences.",
        "3. When page count and size already match, use layout causes to choose between page frame/body box, front-matter spacing, body density, table/figure float placement, and header/footer fixes.",
        "4. Treat missing text zones as extraction or normalization defects unless the PDF preview proves the zone is genuinely absent.",
    ])
    return "\n".join(lines) + "\n"


def parse_run(value: str) -> tuple[str, Path]:
    if "=" in value:
        label, path = value.split("=", 1)
    else:
        path = value
        label = Path(value).name
    return label, Path(path).expanduser().resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True, help="Regression run as label=path")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    rows = []
    run_entries = []
    for item in args.run:
        label, path = parse_run(item)
        run_entries.append({"label": label, "path": str(path)})
        rows.extend(load_rows(label, path))

    mode_switches = comparison_mode_switches(rows)
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs": run_entries,
        "summary": {**summarize(rows), "comparison_mode_switch_cases": len(mode_switches)},
        "comparison_mode_switches": mode_switches,
        "rows": rows,
    }
    output_json = Path(args.output_json).expanduser().resolve()
    output_md = Path(args.output_md).expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(markdown_report(data), encoding="utf-8")
    print(output_json)
    print(output_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
