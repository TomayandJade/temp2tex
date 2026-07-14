# Official LaTeX Regression Testing

## Contents

- [Goal](#goal)
- [Corpus Rules](#corpus-rules)
- [Admission Preflight](#admission-preflight)
- [Acceptance Order](#acceptance-order)
- [Standard Command](#standard-command)
- [Variant Search](#variant-search)
- [Thirty-Case Training Loop](#thirty-case-training-loop)

Use this reference when a task asks whether Temp2TeX matches official journal template evidence, or when the user is improving the skill from the fixed corpus. This is not the ordinary single-journal conversion workflow.

Do not run the 30-case regression suite for a normal user request that only asks for a LaTeX package from a Word/PDF/web template. In that case, deliver the package and optional verification artifacts described in `SKILL.md`.

## Goal

When official LaTeX exists, compare two PDFs built from the same regression manuscript:

1. The official LaTeX template, with its original class/style/preamble retained.
2. The Temp2TeX-generated LaTeX template, generated from the official Word/DOCX template.

Replace the body of both LaTeX projects with `assets/regression/stress_body.tex` and inject `assets/regression/stress_preamble.tex` before `\begin{document}`. This makes the comparison about template behavior instead of differences between official sample documents. Preserve any source-backed structural wrapper around the injected body: for example, when a Temp2TeX package uses `\twocolumn[...]` for single-column front matter followed by a two-column body, inject the stress title/author/abstract/keyword prefix inside that bracket and the stress body after it. Do not flatten the normalized project to one column, because that invalidates the layout comparison.

Before injection, remove source example metadata commands that start a
preamble line (`title`, `author`, `affiliation`, `date`, `maketitle`, and
equivalent running-title/author commands). Keep class and package definitions
intact. The normalization report must record the stripped command names;
otherwise an original placeholder affiliation or author note can remain beside
the stress manuscript and make the PDF comparison unfair.

Likewise, use a generated package's source-backed class interface when the
fixed stress body exercises that module. For example, when the package defines
`journalfigure`, normalize its figure fixtures through that environment so the
comparison tests the Word-derived inline-versus-floating policy. When the
package defines `journaltable`, adapt the stress tables in the same way so
source-backed table width, border, and placement helpers are exercised. Record
each adapter in normalization output; do not apply it to unrelated official
templates that do not expose the interface.

Some official classes need a specialized stress body to accept the same manuscript. The runner auto-selects `stress_body_elsarticle.tex`, `stress_body_icck.tex`, or `stress_body_imsart.tex` when the official source reveals those class/front-matter patterns. Treat these as compile adapters, not easier acceptance standards.

When official LaTeX does not exist, cannot be obtained, or cannot produce a local
reference PDF, but official Word/DOCX exists, use a fallback gate:

1. Create a working copy with `scripts/normalize_word_stress.py`, using the same
   fixture as the LaTeX test and preserving the Word template's selected role
   styles. The original download is evidence and must remain unchanged.
2. Render that normalized Word copy to PDF with the best available renderer.
3. Compile the Temp2TeX-generated LaTeX package to PDF.
4. Compare the Word-rendered PDF against the generated PDF.
5. Record the mode as `word_render_fallback` so it is not confused with an official-LaTeX strict pass.

A blank template PDF versus a populated LaTeX test is `not_comparable`.

The normalized Word reference must preserve the selected role's own style. A
direct paragraph/run format may be copied only when its source paragraph has
the same Word style ID as the target role; otherwise record the mismatch and
retain the target style. This prevents a long abstract, instruction, or
reference paragraph from contaminating the canonical body manuscript.

It must also preserve the source section semantics that affect layout. Keep an
explicit continuous one-column front-matter section followed by a two-column
body section, and place the normalized boundary at the corresponding role
transition. In Word, a section with no `headerReference` or `footerReference`
inherits the latest reference of that variant from the preceding section;
materialize those effective references before removing intermediate section
breaks. After normalization, inspect the working copy and render it with two
engines when available. Do not train a placement, density, or page-count rule
against a reference whose section count, column transition, or active running
furniture was accidentally discarded.

When generation with `--word-source` records
`assets.extracted_manifest` in each package-local spec, pass the ordinary
package's spec and the candidate package's spec to `promote_render_probe.py`.
Using the pre-extraction source spec for only one side creates an unrelated
provenance diff and must be rejected rather than whitelisted as calibration.

## Corpus Rules

- Count unique template systems, not journals that share the same publisher package.
- Prefer official publisher or journal pages that expose both Word/DOCX and LaTeX sources.
- Record the official page URL, discovered template URLs, local file paths, download timestamp, SHA-256 hashes, and compile engine.
- Mark a case `not_comparable` when no official Word source can be obtained, when neither an official-LaTeX PDF nor a Word-render fallback can produce a reference PDF, or when the generated LaTeX package cannot produce a PDF.
- Missing, inaccessible, or locally uncompilable official LaTeX alone is not enough to mark the case `not_comparable` if an official Word source exists and can be rendered.
- Replace `not_comparable` cases from the backup pool instead of relaxing acceptance.

## Admission Preflight

Set these locations once for the current machine:

```powershell
$skillRoot = "<path-to-temp2tex-skill>"
$corpusRoot = "<path-to-temp2tex-regression-corpus>"
```

Run admission preflight before adding a candidate to the active corpus:

```powershell
python "$skillRoot\scripts\preflight_corpus.py" `
  --manifest "$corpusRoot\manifest_30.json" `
  --outdir "$corpusRoot\preflight-30case"
```

A candidate is admitted only when its official source metadata exists, the downloaded Word artifact has a valid DOC/DOCX/DOT/DOTX/RTF payload, a SHA-256 hash is recorded, and the Word source renders to PDF. Missing official LaTeX selects `word_render_fallback`; it does not reject the case. Challenge pages, HTML saved as a document, inaccessible redirects, and non-renderable Word files remain outside the active corpus until fixed or replaced.

## Acceptance Order

1. Official source page is captured.
2. Official DOC/DOCX source is present.
3. If official LaTeX is declared, obtain and normalize it; otherwise render the official Word source as the reference PDF.
4. The selected official LaTeX or Word-render reference PDF is produced.
5. Temp2TeX-generated normalized PDF compiles.
6. Page count matches exactly.
7. Page size matches within 1 pt.
8. Required text zones are extractable from both PDFs: title, abstract, keywords, Introduction, Methods, Results, Discussion, References, Appendix.
9. PDF image comparison produces diff previews.
10. Average normalized visual diff is at or below 0.03 and max page diff is at or below 0.08 by default.

Record `pixel_exact`, `layout_penalty`, and likely layout causes separately. Pixel exactness is a stronger signal than the default gate, and layout diagnostics explain visual failures, but the default gate remains the strict layered acceptance standard.

## Standard Command

```powershell
python "$skillRoot\scripts\run_regression.py" `
  --manifest "$corpusRoot\manifest.json" `
  --outdir "$corpusRoot\iteration-1" `
  --variant-search `
  --review
```

Run failing cases again with `--cases <case_id>` after improving the skill, then run the representative set and the configured 30-case manifest before declaring the 30-case regression clean.

If a full run is split because of a shell timeout, rerun only the missing case
IDs with the same `--outdir`. The runner rebuilds `benchmark.json` and
`regression_summary.json` from every completed case report already present in
that directory; do not treat the final tail command as a two-case benchmark.

## Variant Search

Use `--variant-search` during training and official regression when the base generated package compiles but fails page geometry or visual thresholds. The search is bounded and evidence-oriented: it tries paper size, single/double column density, compact body settings, dotted section labels, compact heading profiles, and plain/empty page-style profiles, then chooses by this order: strict pass, hard gate, page count, page size, missing zones, page-count delta, layout penalty, average diff, max diff.

Each PDF comparison writes `layout_profile/layout_diagnostics.json`. Use its `top_causes` and `layout_penalty` to decide what to fix next before adding more template variants. Accept anchor diagnostics only when both PDFs contain the same fixture and the report records the expected `anchor_profile_version`; generic zone words are invalid anchors because they create false first hits in prose or references.

Before comparison, validate that the rendered official LaTeX PDF contains every
required zone from the fixed fixture. A successful TeX command is insufficient
when custom title or abstract macros still show the publisher's example text.
If the official PDF is incomplete, use the normalized official Word render as
the reference only after it passes the same zone check. If neither reference
contains the complete fixture, mark the case `not_comparable`. Never compare a
partial PDF emitted before a fatal TeX error; `compile_latex_package.py` exposes
such an artifact only as `partial_pdf`, not `pdf`.

Even complete official Word and LaTeX templates may represent different layout
families. Render the normalized Word fixture and compare first-page size and
total page count with the official LaTeX golden. Use the LaTeX golden only when
both are compatible within the page-size tolerance and have the same fixture
page count. Otherwise use the complete Word render as the primary target,
because the skill reconstructs the Word template; retain the official LaTeX
result as auxiliary evidence.

Use `--source-font-probe` when the selected Word body style names a Latin font
but the ordinary package deliberately retains the conservative fallback stack.
It compares only the base package and a `font_family_mode: render_verified`
candidate, with `\IfFontExistsTF` preserving compile safety. Promote the source
font only when this same-content comparison selects it; a matching Word font
name alone is not proof of matching TeX glyph metrics or pagination.

Use `--heading-color-probe` when a selected Word heading role has a concrete
non-black RGB value. It compares the ordinary black-heading package with one
candidate that enables all source-backed heading colours. Keep colours inactive
unless the same-content comparison selects the candidate: instructional
template colours can be absent from the actual normalized manuscript style.

Use `--reference-layout-probe` when Word reference entries contain a fixed
left inset, hanging indent, or after spacing. It compares the ordinary
reference-font-only package with a candidate that maps those values to the
standard `thebibliography` list. Reference label widths and late-page flow are
too backend-sensitive to make this geometry an ordinary-delivery default.

When a Word template contains inline body drawings and float placement is the
specific uncertainty, prefer the lightweight probe before full variant search:

```powershell
python "$skillRoot\scripts\run_regression.py" `
  --manifest "$corpusRoot\manifest.json" `
  --outdir "$corpusRoot\iteration-figure-probe" `
  --cases <case_id> `
  --figure-placement-probe
```

It compares only the normal floating package and an explicitly non-floating
candidate. Word XML anchor state is candidate evidence, not proof of either
policy; only the comparison result may promote a placement choice.

For representative Word tables, use `--table-placement-probe` to compare the
ordinary floating `journaltable` with a source-derived non-floating candidate.
Keep the candidate only when rendered same-content evidence selects it; the
presence of a Word table alone does not establish a journal-wide non-floating
LaTeX policy.

The strict promotion gate has two modes. Use `stable_visual_calibration` when
the ordinary package already matches the reference page count; page geometry
must remain stable and the candidate must improve visual metrics. Use
`page_count_repair` only when the ordinary package has the wrong page count and
an isolated source-backed placement candidate matches the complete Word
reference. The repair must also match paper size, preserve semantic anchors,
remove anchor page shifts, improve layout and placement diagnostics, and keep
pixel-score deterioration inside bounded tolerances. Do not require a repaired
candidate to preserve the ordinary package's incorrect page count.

Use `--float-spacing-probe` only when
`page.float_spacing_evidence.status` is `source`. It compares the ordinary
package with one candidate that maps eligible Word object/body-text outer
boundaries to `textfloatsep`, `intextsep`, and `dbltextfloatsep`. Caption,
object-note, heading, abstract, keyword, and reference neighbors remain in the
raw ledger but do not contribute. The probe never changes the ordinary package;
run the strict promotion gate before retaining the calibration.

When a representative table has source grid widths, use
`--table-geometry-probe` to compare the base column budget with precise and
full-width candidates. This is specifically for the interaction between
printable borders and Word's grid widths. The base package remains unchanged;
promote a candidate only when it wins the same-content PDF comparison without
creating overflow or pagination regressions. Never infer printed borders from
Word's editor-only table grid; preserve a named `TableGrid` style as separate
evidence because it may provide the printable rules.

When a generic Word body style conflicts with several visible flow paragraphs,
use `--body-style-probe`. It compares the ordinary named-style package with a
candidate that applies the stored visible-flow formatting. Keep the candidate
only when the same-content PDF comparison improves without page or zone
regressions; the conflict remains a candidate in ordinary conversion.

The same probe also emits body-scoped paragraph-spacing candidates when a
non-table Word body role has a resolved boundary of at least 6pt. Resolve the
boundary once as `max(space_before, space_after)` and test only 0.5, 0.75, and
1.0 multiples. Do not apply the result globally: `journal-template.cls` must
keep title/front matter unaffected and enable the candidate only inside the body
environment. A candidate that changes the incorrect ordinary page count may be
promoted only through `page_count_repair`; page-count equality alone is not
enough, and a candidate with anchor shifts or worse layout remains rejected.

Use `--appendix-boundary-probe` only after the ordinary layout diagnostics show
that appendix is the sole shifted anchor and every title-through-reference
anchor page is stable. The candidate activates `\clearpage` through the
editable `\journalappendix` class command; it does not alter a bare manuscript
globally. Promotion requires one active calibration path, complete-reference
pagination and page size, no remaining shifts or missing zones, improved
structural-flow score and mean visual difference, and at most 0.1 total layout
penalty deterioration caused by profiling the newly correct page. A candidate
that still shifts references or another earlier zone must be rejected.

When the source contains anchored Word text boxes, use
`--text-box-placement-probe` to compare the ordinary package with an explicit
candidate that activates only page/margin-relative coordinates. The probe
records native width/height and relative offsets in the source spec, keeps
column/paragraph-relative shapes out of executable placement, and selects a
candidate only through the same-content PDF gates. Normal conversion still
leaves `textboxes.tex` commented and requires visual confirmation before any
shape is promoted.

For a small, stable page-frame displacement, first call
`suggest_page_calibration.py`, then materialize its pending proposal into a
separate candidate spec with `materialize_page_calibration_candidate.py`.
Generate that package only with `--apply-render-probe` and compare it with the
ordinary package. Never replace the ordinary source spec or mark its
calibration verified merely because a candidate compiles.

For a residual body-density mismatch, rerun `profile_pdf_layout.py` so the
diagnostics include same-column baseline steps. Use `suggest_body_calibration.py`
only after page count, body width, and anchor pages are stable, then materialize
the pending proposal with `materialize_body_calibration_candidate.py`. Generate
the isolated candidate with `--apply-render-probe`. Accept it only when page and
zone gates remain stable and both layout and pixel comparison improve relative
to the base package. Reject a candidate that merely compiles, is neutral, or
makes any comparison metric worse; do not tune its bounds repeatedly against a
single publisher.

When source-backed Word header text is present and the remaining diagnostic is
the vertical page frame, use `--furniture-geometry-probe`. It compares the
base package with a candidate derived from the Word top margin and header
distance. The candidate is never enabled for ordinary delivery until the PDF
comparison selects it.

When Word has an active `first` header/footer variant, use
`--first-page-furniture-probe`. It compares only the base package with a
candidate that enables the class's distinct first-page style. The runner
regenerates the candidate with the official Word source so first-page assets
are available. Keep the candidate only when the same comparison target selects
it; a logo or submission notice must not leak into later-page furniture.

Do not treat variant search as permission to relax the gate. A selected variant still fails if any compile, page count, page size, required-zone, or visual threshold fails.

For IMS/Baltzer-style legacy classes, the runner detects `\documentclass{imsart}`/`\documentclass{baltzer}` or the `frontmatter + aug + kwd` pattern. Because those old front-matter macros can fail on modern TeX before labels are resolved, the adapter uses stable `maketitle` plus explicit Abstract/Keywords text while preserving the official class and preamble.

## Thirty-Case Training Loop

For repeatable offline runs, retain official LaTeX source archives under the
corpus-level `official_sources/<case>/latex/` cache. The runner restores only
these raw artifacts under `--skip-network`, then re-extracts and recompiles
them in the current iteration. Never cache or reuse a prior official PDF,
normalized project, or comparison result as a golden output.

Compile the official golden with its own engine requirements, independently of
the generated package. A manifest engine is tried first; when it fails and the
official class/style contains an unambiguous PDFTeX-only primitive such as
`\pdfobj`, retry the golden with PDFLaTeX and retain both compile reports.
Class-specific title metadata or end markers required by a known official
class belong in its regression adapter, never in the generated Temp2TeX class.

Use `$corpusRoot\manifest.json` as the
canonical 30-case training surface. The separate CJK direct-format extension
is tracked in that manifest's `extensions` field.

After a run, aggregate the training signal:

```powershell
python "$skillRoot\scripts\analyze_regression_training.py" `
  --run canonical30="$corpusRoot\iteration-next-30case" `
  --run cjk="$corpusRoot\iteration-next-cjk" `
  --output-json "$corpusRoot\training_signal_30case.json" `
  --output-md "$corpusRoot\training_signal_30case.md"
```

When aggregating more than one iteration, treat a change between
`official_latex` and `word_render_fallback` as a reference-mode switch, not a
Temp2TeX quality delta. The analyzer reports these cases explicitly; compare
visual and layout metrics only within a stable mode.

Use this priority order for skill edits:

1. Restore comparability: source discovery, official LaTeX normalization, and compile-engine adapters.
2. Fix generated page geometry: paper size, margins, column mode, font size, and line spacing.
3. Fix structural zones: title, abstract, keywords, heading levels, references, appendix.
4. Tune visual differences only after page count, page size, and required zones are stable. Use layout diagnostics to choose the axis: front-matter spacing, page frame/body box, body density, table/figure caption or float placement, or header/footer behavior. Prefer general axes such as heading-label punctuation, compact heading profiles, page-style profile, caption spacing, and title/abstract spacing before journal-specific overrides.

Do not optimize against one journal by hard-coding its visual output unless the change generalizes to a source-evidence rule such as two-column detection, legacy Word conversion, DVI-era compilation, or class-specific official front matter.
