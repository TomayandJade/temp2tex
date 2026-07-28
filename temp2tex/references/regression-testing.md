# Official LaTeX Regression Testing

## Contents

- [Goal](#goal)
- [Corpus Rules](#corpus-rules)
- [Admission Preflight](#admission-preflight)
- [Acceptance Order](#acceptance-order)
- [Standard Command](#standard-command)
- [Variant Search](#variant-search)
- [Admitted-Corpus Training Loop](#admitted-corpus-training-loop)

Use this reference when a task asks whether Temp2TeX matches official journal template evidence, or when the user is improving the skill from the fixed corpus. This is not the ordinary single-journal conversion workflow.

Do not run the full regression suite for a normal user request that only asks for a LaTeX package from a Word/PDF/web template. In that case, deliver the package and optional verification artifacts described in `SKILL.md`.

## What This Runner Measures

`run_regression.py` is a deterministic **tooling baseline**. It exercises
source discovery, Word extraction, normalizer fixtures, package generation,
LaTeX compilation, and PDF comparison. It does not load an LLM, consume model
tokens, or resolve the evidence-bound atomic decisions that an agent must make
after loading Temp2TeX. Its `tooling_baseline` benchmark configuration may
identify a reproducible extractor, generator, compiler, or comparator defect;
it must never be reported as a `with_skill` model result or proof that the
skill followed its instructions.

Use `references/llm-skill-evaluation.md` to evaluate actual agent behavior.
The two evaluation layers complement each other: the tooling baseline supplies
reproducible artifacts and known source conditions, while an LLM evaluation
tests evidence discipline, editable class design, scope control, and honest
handoff.

Before a skill-level corpus regression that changes Word object/caption
extraction, run `audit_caption_relations.py <corpus-root> --inputs-only` for
each fixed corpus batch. A duplicate confirmed caption assignment is a source
extraction failure, not evidence that multiple figures or tables share one
LaTeX caption. Resolve it or preserve it as `ambiguous`/`label_mismatch` before
using the corpus to tune caption position, spacing, float placement, or PDF
anchors. This source audit is narrower than the PDF regression and does not
replace same-content rendering.

## Goal

When official LaTeX exists, compare two PDFs built from the same regression manuscript:

1. The official LaTeX template, with its original class/style/preamble retained.
2. The Temp2TeX-generated LaTeX template, generated from the official Word/DOCX template.

Replace the body of both LaTeX projects with `assets/regression/stress_body.tex` and inject `assets/regression/stress_preamble.tex` before `\begin{document}`. This makes the comparison about template behavior instead of differences between official sample documents. Preserve any source-backed structural wrapper around the injected body: for example, when a package uses `\twocolumn[...]` for single-column front matter followed by a two-column body, inject the stress title/author/abstract/keyword prefix inside that bracket and the stress body after it. When a source instead uses a plain `\twocolumn` transition or `\begin{multicols}{n}` around its body, retain that exact outer transition or environment around the corresponding stress-body segment. Do not flatten the normalized project to one column, because that invalidates the layout comparison.

Before treating an official LaTeX PDF as a golden, compare its retained wrapper with the Word source's ordered section evidence. A Word one-column-to-two-column `nextPage` transition and an official LaTeX continuous `multicols` body are conflicting template systems, even when their paper size and page count happen to match. In that situation, the Word template is the conversion target: mark the official-LaTeX pair `not_comparable`, retain both artifacts and the conflict report, and use a Word-rendered reference only when the renderer preserves the Word transition. Do not tune the generated class toward the conflicting official LaTeX layout.

## Audited Decision Handoff

When a model has completed an `atomic_mapping_decisions.json` review, a regression may reuse it with `--atomic-decisions-dir <directory>`, where each selected case is named `<case-id>.json`. The runner rebuilds the Word ledger first, then invokes `reconcile_atomic_mapping_decisions.py`; only exact or uniquely identity-matched final decisions are carried forward. It also re-audits each declared LaTeX token against the freshly generated package and checks the matching system-format triage. A missing, invalid, stale, ambiguous, or token-invalid decision file leaves the affected units pending and blocks calibration. The handoff does not alter `main.tex` or `journal-template.cls`; it records whether an already-reviewed mapping is eligible to support a later render decision.

For Word-render fallback comparisons, use `normalize_word_stress.py` to place the same fixed manuscript into a *copy* of the official Word file, then generate the Temp2TeX package with `generate_latex_package.py --fixture-profile regression-stress`. `regression-stress` is regression-only and currently covers English fixtures. It must never replace the ordinary editable `main.tex` delivered to a user. The runner applies this profile automatically for English cases. A comparison is eligible for calibration only when its report has `same_content_contract_status: passed`, `text_contract_status: passed`, and `geometry_contract_status: passed`; a successful compilation alone is insufficient.

The runner also enables `--comparison-fixture-artwork` for its generated
comparison package. This writes neutral single-panel and paired-panel raster
frames that match the Word normalizer's declared 4.7-inch by 1.875-inch image
boxes. Their interiors may be masked only after their frames, captions, and
surrounding flow are compared. This regression-only option never changes the
ordinary editable package, which keeps a neutral empty figure frame.

Before accepting a Word-render fallback, inspect the normalized Word
section-flow report. If it contains a `new_page` one-column-to-multicolumn
transition and the selected renderer is LibreOffice, the PDF is not an eligible
layout-calibration reference. Mark the case `not_comparable`, retain its Word
XML transition evidence, and still compile the generated package. LibreOffice
may be used for ordinary DOCX conversion checks, but it must not override
Microsoft Word's section-boundary semantics in this regression gate.

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
   fixture language as the LaTeX test (`--fixture-language zh` for Chinese and
   `--fixture-language mixed` for bilingual templates) while preserving the Word
   template's selected role styles. When the generated package uses the standard
   editable fixture, add `--fixture-profile latex-default` so the two PDFs use the
   same front matter and content order. The original download is evidence and must
   remain unchanged.
2. Render that normalized Word copy to PDF with the best available renderer.
3. Compile the Temp2TeX-generated LaTeX package to PDF.
4. Compare the Word-rendered PDF against the generated PDF.
5. Record the mode as `word_render_fallback` so it is not confused with an official-LaTeX strict pass.

For every Word source that yields a structured ledger, the runner also places
`word_format_ledger.json`, `atomic_mapping_decisions.json`, and
`atomic_mapping_audit.json` in the base generated package before comparison.
The decisions file is intentionally pending: it is a model worklist, not a
claim that the generator reconstructed every paragraph/run. The accompanying
coverage report must retain `atomic_mapping_audit_complete: false` until an
agent has reviewed decisions against the package and rerun the audit in strict
mode. Regression visual scores never convert pending atomic mappings into
verified template rules. The runner may compile and compare the base package
to preserve a diagnostic baseline, but it disables variant search and every
placement/spacing/page-flow probe until the strict audit is complete. An
otherwise passing visual pair is reported as `pending_atomic_audit`, not as a
strict regression pass.

`pending_atomic_audit` is a third regression outcome, distinct from `passed`
and `not_comparable`. It means the source artifacts and generated package may
have compiled, but the model has not completed the ledger-matched mapping work
needed to interpret PDF differences. The runner records it in a separate
`pending_atomic_audit` summary bucket and marks the benchmark result
`incomplete`; do not count it as a source/reference failure or replace the
case. The command still returns nonzero until that work is completed, so a
training run cannot be mistaken for a strict pass.

For true legacy DOC/DOT/RTF sources, `run_regression.py` directs
`build_word_format_ledger.py` to retain a LibreOffice-derived inspection DOCX
under `derived/legacy-inspection.docx`. The ledger records both original and
derived SHA-256 hashes, and the generated package copies that file before any
later audit or comparison. The original binary remains the official evidence.
If conversion cannot produce a valid OpenXML package, or the retained derived
file/hash is absent, the case may retain compile/render diagnostics but cannot
receive a strict regression pass or any layout-calibration probe.

A blank template PDF versus a populated LaTeX test is `not_comparable`. The
same applies to an instruction-only Word template when the normalized working
copy would carry formatting guidance, placeholder text, or example reference
rules into the test manuscript rather than a complete role-matched fixture.

The normalized Word reference must preserve the selected role's own style. A
direct paragraph/run format may be copied only when its source paragraph has
the same Word style ID as the target role; otherwise record the mismatch and
retain the target style. This prevents a long abstract, instruction, or
reference paragraph from contaminating the canonical body manuscript.

For directly formatted Chinese templates, numbered paragraphs before the first
visible Chinese or English abstract are front-matter candidates. Do not use
them as body-heading exemplars merely because they begin with `1.` or `2.`:
they are commonly numbered author affiliations. Use a visible post-abstract
manuscript heading, or retain the heading mapping as unresolved evidence.

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
  --manifest "$corpusRoot\manifest-60.json" `
  --outdir "$corpusRoot\preflight-60case"
```

A candidate is admitted only when its official source metadata exists, the downloaded Word artifact has a valid DOC/DOCX/DOT/DOTX/RTF payload, a SHA-256 hash is recorded, and the Word source renders to PDF. Missing official LaTeX selects `word_render_fallback`; it does not reject the case. Challenge pages, HTML saved as a document, inaccessible redirects, and non-renderable Word files remain outside the active corpus until fixed or replaced.

## Acceptance Order

1. Official source page is captured.
2. Official DOC/DOCX source is present.
3. If official LaTeX is declared, obtain and normalize it; otherwise render the official Word source as the reference PDF.
4. For readable OpenXML Word evidence, the copied ledger and strict atomic audit are complete and ledger-matched. Until then, only a base diagnostic comparison is permitted.
5. The selected official LaTeX or Word-render reference PDF is produced.
6. Temp2TeX-generated normalized PDF compiles.
7. Page count matches exactly.
8. Page size matches within 1 pt.
9. Required text zones are extractable from both PDFs: title, abstract, keywords, Introduction, Methods, Results, Discussion, References, Appendix.
10. PDF image comparison produces diff previews.
11. Average normalized visual diff is at or below 0.03 and max page diff is at or below 0.08 by default.

Record `pixel_exact`, `layout_penalty`, and likely layout causes separately. Pixel exactness is a stronger signal than the default gate, and layout diagnostics explain visual failures, but the default gate remains the strict layered acceptance standard.

## Standard Command

```powershell
python "$skillRoot\scripts\run_regression.py" `
  --manifest "$corpusRoot\manifest-60.json" `
  --outdir "$corpusRoot\iteration-1" `
  --variant-search `
  --review
```

Run failing cases again with `--cases <case_id>` after improving the skill, then run the representative set and the configured canonical 60-case manifest before declaring the full regression clean.

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

When the same Word evidence packet shows both captioned inline drawings and a
flowing representative table, enable both placement probes to evaluate one
bounded combined candidate after the isolated candidates. This is not a
cross-product search. Retain the combined result as `render_probe` unless it
passes every promotion gate and improves on the ordinary package and both
isolated probes; a partial visual improvement is recorded as a remaining
object-flow gap.

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
candidate that applies the stored visible-flow formatting. Keep the Word named
style and exemplar immutable: the candidate must set only
`document.render_calibration.body_style_mode: visible_flow_exemplar` with
`status: render_probe`. Keep it only when the same-content PDF comparison
improves without page or zone regressions and strict promotion writes
`render_verified`; the conflict remains a candidate in ordinary conversion.

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

## Admitted-Corpus Training Loop

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

Use `$corpusRoot\manifest-60.json` as the canonical admitted training surface.
The earlier 30-case manifest and any direct-format CJK extensions remain
historical or targeted subsets; they do not replace the current full corpus.

After a run, aggregate the training signal:

```powershell
python "$skillRoot\scripts\analyze_regression_training.py" `
  --run canonical60="$corpusRoot\iteration-next-60case" `
  --run cjk="$corpusRoot\iteration-next-cjk" `
  --output-json "$corpusRoot\training_signal_60case.json" `
  --output-md "$corpusRoot\training_signal_60case.md"
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

## Object/Caption Source Gate

Before using table/figure visual failures as a training signal, run
`audit_caption_relations.py` across the affected official Word inputs. Its
`evidence_disposition` is a prerequisite to interpreting a visual difference:

- `confirmed_source_relation` may produce a bounded caption-order, object-gap,
  or object-specific anchor candidate.
- `remote_caption_candidate` is diagnostic only. It may inform a separately
  selected typography exemplar, but cannot train attachment, spacing, float,
  or anchor behavior.
- `label_mismatch`, `ambiguous_source_relation`, and
  `no_observed_caption_relation` cannot train caption or float behavior. Keep
  their restrictions in the gap log and resolve them from a rendered Word page
  or independent source evidence.

Aggregate visual metrics only from cases whose relevant object evidence is
eligible for the decision under test. An image's raster interior may be masked
for image-insensitive comparison, but its frame, caption, surrounding flow,
and all table geometry remain in scope.

## Page-Furniture Rule Guard

Treat every visible Word header/footer line as a separate page-furniture
requirement. A DrawingML line and its VML compatibility representation are one
physical rule, not two requirements. Record the active Word part, rule width,
relative geometry, and whether the rule belongs to a header or footer.

Do not derive a footer rule from a header rule or use an inactive section part.
Source-backed rule width may be emitted as an editable class candidate when the
active part is unambiguous. Its baseline, section scope, and horizontal span
remain render checks. In particular, a two-column LaTeX PDF whose footer line
spans only one column fails this guard even when compilation succeeds and the
line width itself is correct. Record it as a furniture-geometry gap and keep it
out of a full-fidelity claim until a same-content reference comparison confirms
the intended page-wide extent.

A header/footer-only `partial_zone` comparison may assess that local rule and
its nearby running text. It cannot calibrate margins, columns, body density,
float placement, or the general class.
