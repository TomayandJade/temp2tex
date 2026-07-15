# Render Comparison

Use this reference when render tooling is available or when the user explicitly asks for visual comparison. For ordinary conversion tasks, missing render tooling should be recorded as a verification gap, not treated as task failure.

The visual check is a PDF-to-PDF comparison between the rendered original template and the generated LaTeX PDF.

When an official LaTeX template exists, run that check as the primary regression gate: compile the official LaTeX template and the Temp2TeX-generated template with the same fixed regression body, then compare those two PDFs. Keep the Word-rendered PDF comparison as supporting evidence for source extraction fidelity.

Confirm the official golden actually contains the complete fixed body after
normalization. Custom metadata macros can compile successfully while retaining
the publisher's example title or dropping the abstract. In that situation the
PDF is not a same-content golden: fall back to a complete normalized Word
render. A failed TeX command may emit a partial PDF; never compare it.
Also require the complete official LaTeX and Word renders to use compatible
page dimensions and the same fixture page count. A mismatch means they are
different layout families, so the Word render is primary for Word reconstruction
and the official LaTeX PDF is only auxiliary evidence.

When an official LaTeX template does not exist but an official Word/DOCX template exists, render the Word template to PDF and compare that PDF against the compiled Temp2TeX-generated package. Record the comparison as `word_render_fallback`, not as an official-LaTeX strict pass.

## Comparison Order

1. Compile status: LaTeX must produce a PDF without fatal errors.
2. Page count: detect extra or missing pages.
3. Page geometry: compare width and height.
4. Structural presence: check title, abstract, keywords, headings, tables, figures, references, appendices.
5. Page images: render both PDFs at the same DPI and generate diff images.
6. Layout profile: extract text boxes, anchor positions, line gaps, same-column baseline steps, font sizes, header/footer occupancy, and image counts.

## Graphics-Insensitive Metrics

Do not use manuscript-specific image pixels as a template-fidelity gate. When
the PDFs contain embedded raster artwork, the format comparison masks only
the interior of each image rectangle and retains a small perimeter. Evaluate
the resulting `format_*` metrics for the pass/fail visual gate. The ordinary
pixel metrics remain diagnostic evidence only.

The mask does **not** excuse a figure mismatch. Confirm image position, outer
width and height, border/frame, wrapping or float behavior, caption order,
caption typography, and the downstream page flow. Tables are never image
content for this purpose: compare their column widths, rules, merged cells,
cell alignment, notes, and captions directly.

Anchor every applicable semantic zone with a phrase unique to the shared test
manuscript. Treat the resulting JSON map as a same-content contract, not a
small collection of convenient search terms. Include separate anchors for
front matter, body/heading hierarchy, table/caption/note, figure/caption,
notes, references, and appendix whenever those zones exist.
Avoid generic labels such as `Table`, `Figure`, or `References`, which can also
occur in the abstract, running text, or bibliography. The built-in anchor map
is valid only for the bundled regression fixture. For any other manuscript,
pass a task-specific JSON map through `--anchors-json` and retain
`anchor_profile_version` in every report. Do not compare layout scores produced
by different anchor versions.
Every declared anchor must occur in both PDFs. If
`layout_diagnostics.summary.semantic_comparable` is `false`, if
`same_content_contract_status` is not `passed`, or if
`shared_anchor_count` differs from `required_anchor_count`, mark the layout
comparison `not_comparable`.
`text_contract_status: passed` proves only that the fixture content is shared.
It does not replace `geometry_contract_status: passed`: every role anchor must
also have a positioned match before a layout measurement can calibrate the
class. This distinction is essential when pdfplumber is the geometry fallback.

Use role names, not page numbers, as JSON keys. A minimal bilingual Chinese
fixture contract can look like this; omit only zones that are genuinely absent:

```json
{
  "front_matter.abstract": "摘要：",
  "front_matter.english_abstract": "Abstract:",
  "body.heading_1": "1 研究背景",
  "table.caption": "表 1: 样例数据",
  "figure.caption": "图 1: 样例流程",
  "notes.body_footnote": "基金项目：",
  "references.entry": "[1] Wang",
  "appendix.heading": "A 附录"
}
```

Choose a phrase that is unique within the fixed manuscript and survives PDF
text extraction. Do not use only a label such as `摘要` or `表`; bind the label
to its role-specific content or numbering.
Do not use text-box, baseline, line-gap, margin, float, or calibration hints
from that pair to change the class. Supply a shared fixture-specific anchor map
first. `profile_pdf_layout.py` prefers PyMuPDF and falls back to pdfplumber
when needed; preserve the reported extractor because fallback word grouping is
diagnostic geometry, not a substitute for a rendered visual review.
Allow a unique phrase to span a bounded vertical window of wrapped lines or
same-baseline PDF fragments. Track a horizontal lane, skip interleaved lines
from another column, and join only overlapping/center-near wrapped lines or
side-by-side fragments with a small gap. Retain the union bounding box and
matched line count. Do not flatten an entire page into one string: that can
join unrelated columns or zones and fabricate an anchor.

When page-frame deltas are small and consistent, `suggest_page_calibration.py`
may produce a pending `page.render_calibration` proposal. Review and rerender
it as a candidate; enable it only after the comparison improves. If the tool
reports a large-adjustment warning, do not use its margins: resolve front
matter, float, or page-flow differences first.

When page count, body-box width, and anchor pages are stable but body density
still differs consistently across at least two pages, `suggest_body_calibration.py`
may produce a bounded pending font/baseline proposal. Materialize it into a
separate candidate and generate only with `--apply-render-probe`. Compare the
candidate against the same reference and the ordinary package. Promote it only
when all structural gates remain satisfied and visual metrics improve; reject
an equal or worse candidate. A proposal with `candidate_available: false` is a
useful diagnosis and must not be forced into the class.

If generated output is longer, `suggest_body_calibration.py
--allow-page-count-repair` may emit one narrower candidate only when two or
more pages compare, every anchor shifts later, body width is within 30pt, and
the generated font is stably at least 1pt larger. Reject all other pagination
signatures before materialization. Promotion must repair page count and every
shift, improve body-density and aggregate layout scores, preserve zones and
page size, keep pixel changes bounded, and not worsen the existing width delta.

Use `promote_render_probe.py` for the final acceptance decision, including a
source-derived non-floating figure or table candidate. Do not change a
candidate's `render_probe` status by hand. The promotion gate rejects candidates
that change unrelated spec fields, use a different reference PDF, fail to
compile, introduce anchor failures, or worsen the applicable strict metrics. A
placement probe must be the only active candidate path and must not worsen the
table/figure/caption/float diagnostic score. The gate uses
`stable_visual_calibration` when the ordinary package already matches the
reference page count: preserve page geometry and require meaningful visual
improvement. It uses `page_count_repair` only when the ordinary output has the
wrong page count and the isolated candidate matches the complete reference.
That repair candidate must also match page size, eliminate anchor page shifts,
improve layout and placement diagnostics, and keep pixel-score deterioration
inside bounded tolerances. On acceptance it creates a new portable
`render_verified` spec and a separate detailed `promotion_report.json`; on
rejection it creates only the report.

An appendix-boundary repair is a narrower exception to the general layout-
penalty improvement rule. It is eligible only when appendix is the ordinary
output's sole shifted anchor. The candidate must remove every shift, improve
the `pagination_or_structural_flow` score and mean pixel difference, and may
worsen aggregate layout penalty by no more than 0.1 because the corrected extra
page changes that aggregate. Do not apply this exception to body, float,
reference, or page-frame calibrations.

A backmatter-boundary repair places one candidate boundary before the first
acknowledgement/declaration, not before references or appendix individually.
It is eligible only when generated output is shorter and shifted anchors are a
subset of acknowledgements, data availability, references, and appendix, with
references and appendix both present and every shift identical. Require the
candidate to match page count/size, clear all shifts, preserve zones, improve
structural flow, mean visual difference, and total layout, and keep pixel
deterioration bounded. Ordinary `\journalbackmatter` remains continuous.

A source float-spacing probe follows the same gate. It may change only
`page.float_spacing_calibration`, must come from source-backed body-text outer
boundaries, and tests the shared `textfloatsep`/`intextsep`/`dbltextfloatsep`
mapping. Reject it if another calibration path is active or if the
table/figure/caption/float diagnostic score worsens, even when mean pixel diff
improves.

Interpret the diagnostics in this order: a persistent horizontal body-box
width/edge difference supports a page-frame investigation. A large vertical
shift on later anchors (methods, table, figure, references, appendix), while
the title/abstract stay near their expected positions, is a pagination or
structural-flow problem instead. Repair the front-matter column transition,
float policy, caption flow, or forced break before proposing a margin change.
7. First-page layout: title block, author block, abstract, keywords, header/footer.
8. Body page: heading levels, paragraph spacing, line width, indentation.
9. Table page: caption location, rules, cell spacing, notes.
10. Figure page: caption style, width, placement, subfigures.
11. Reference and appendix pages.

For official-LaTeX regression, add these hard gates before visual interpretation:

1. The official DOC/DOCX source and official LaTeX source are both recorded from official pages.
2. Both normalized LaTeX projects compile locally.
3. Page count matches exactly.
4. Page size matches within 1 pt.
5. Required text zones are extractable from both PDFs.
6. Diff previews are produced for every compared page.

For Word-render fallback, replace the official-LaTeX source and compile gates with:

1. The official DOC/DOCX source is recorded from official pages or configured local official files.
2. The Word/DOCX source renders to a reference PDF with Word or LibreOffice.
3. The Temp2TeX-generated package compiles to PDF.
4. Page count, page size, required zones, and diff previews are evaluated against the Word-rendered PDF.

## Interpreting Diff Images

Large visual differences are expected while placeholder content differs. Focus on:

- page frame and margins
- position of major zones
- relative spacing before and after headings
- caption placement
- table and figure alignment
- header/footer/page number behavior

Do not chase pixel-perfect text differences before structural zones are correct.

For regression, record `pixel_exact`, average normalized diff, maximum page diff,
and the per-page ink-weighted difference plus ink-mask IoU. Whole-page averages
are dominated by white paper, so they must never be the sole visual gate. The
comparison tool flags a page when either normalized difference or ink-weighted
difference exceeds `0.20`; inspect its diff preview and structure before any
promotion. Calibrate stricter corpus thresholds only from comparable
same-content cases.

## Report Expectations

When comparison runs, `render_compare_report.json` should include:

- input PDF paths
- renderer and tool availability
- page count comparison
- page size comparison
- whole-page and ink-weighted image diff scores plus ink-mask IoU per compared page
- generated diff image paths
- layout diagnostics with `layout_penalty`, likely visual causes, anchor page shifts, and horizontal text-box deltas
- prioritized issues

If comparison cannot run, do not fabricate a report. Instead, write the missing tool and rerun command in `README.md` and list visual verification as pending in `format_gap_log.md`. Create `render_compare_report.json` only if the project convention requires a machine-readable pending status.
