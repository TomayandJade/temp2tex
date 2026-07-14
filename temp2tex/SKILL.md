---
name: temp2tex
description: Convert official journal website non-LaTeX templates, especially Word .doc/.docx/.docm/.dot/.dotx/.dotm author templates, into editable Overleaf-ready LaTeX template packages. Use this skill whenever the user asks to rebuild a journal template from official Word/PDF/web author instructions, including sparse or blank Word templates that define formatting through named styles; reproduce cover/title/abstract/table/figure/heading/footnote/reference/appendix/body formatting in LaTeX; create a class-based `.cls + main.tex` package; handle Chinese or English journal defaults when official rules are incomplete; or optionally verify the result with PDF rendering or official Word-vs-LaTeX regression.
---

# Temp2TeX

## Purpose

Transform a journal's official non-LaTeX author template into a compile-ready, editable LaTeX template package. Treat the task as evidence-backed template reconstruction for an LLM agent, not as a local automation pipeline.

The usual input is a journal DOC/DOCX author template from an official website. Use official author instructions, PDF samples, artwork rules, and reference rules as supporting evidence. If official requirements are incomplete, apply conservative Chinese or English journal defaults and record the fallback instead of presenting it as an official rule.

## Skill Loading Contract

When this skill is loaded, the agent's goal is to produce a usable LaTeX template package from official evidence. Local scripts, renderers, and the 30-case corpus with per-case admission status are support resources, not the definition of success for ordinary user work.

The agent should:

1. Reconstruct the template from source evidence before writing LaTeX.
2. Default to `journal-template.cls + main.tex`. Use `.sty` only as a legacy compatibility shim or when preserving an official class is the safer source-backed choice.
3. Deliver editable LaTeX files as the primary output, even if Word, LibreOffice, TeX, or PDF comparison tools are unavailable.
4. Record official rules, inferred defaults, and unsupported gaps in `template_spec.json` and `format_gap_log.md`.
5. Use PDF render comparison when possible, but treat missing render tooling as a verification gap, not as a reason to stop.
6. Use official-LaTeX regression only when the user explicitly asks for Word-vs-LaTeX comparison or when improving this skill from the regression corpus.

## Model Workflow

1. **Classify the task**
   Decide whether this is an ordinary template conversion, an explicit official Word-vs-LaTeX comparison, or skill training/regression work. Then classify the actual source container and evidence condition with `references/input-triage.md`; do not trust the filename extension alone. Ordinary conversion should produce the package without running the full corpus. An unreadable, protected, or damaged Word file limits what can be claimed, but it does not justify inventing rules or withholding a default-backed editable package when official web/PDF evidence is still usable.

2. **Confirm official sources**
   Gather the journal page, DOC/DOCX template, author instructions, PDF sample, artwork rules, reference rules, and assets. Prefer official publisher or journal pages over third-party template sites. Record URLs, access date, local paths, and hashes when files are available.

3. **Build a layout evidence packet**
   Do not map Word XML properties straight into a class. First identify representative rendered evidence for every applicable zone: page frame, page furniture, title/author block, abstract, body, headings, table, figure, notes, references, and appendix. For anchored drawings and text boxes, also retain native width/height, relative coordinate systems, offsets, wrapping, and shape identity before deciding whether they belong in flow. Reconcile the Word style chain, direct formatting, visible source page, and official instructions. Use `references/reconstruction-protocol.md` and `references/model-playbook.md` for the decision order.
   When a heading exemplar or named heading style has no explicit size, inspect
   role-matched official template prose for a stated heading, subheading, or
   tertiary-heading size. Preserve the sentence and paragraph index, and fill
   only that missing size; never borrow an unrelated point value or override
   explicit Word formatting.
   Keep paragraph-level role formatting separate from local run overrides: a
   bold `Abstract` label or correspondence marker must not make the entire
   abstract or affiliation block bold. Promote run typography to a role only
   when all visible runs agree, and keep abstract and keyword role evidence
   separate. Distinguish a standalone abstract-label paragraph, a true
   label-and-content paragraph, and content with no visible label. Indentation
   alone does not prove a run-in label. Do not discard visible front-matter
   roles merely because the publisher placed them in a borderless Word layout
   table; preserve their document-flow order and cell-local evidence. Record
   each front-matter boundary once
   as the larger of the preceding Word space-after and following space-before;
   never add both values in LaTeX. Active text/page-field furniture and
   deterministic rules may be mapped directly on a per-header/footer-part
   basis; one unsafe logo or text-box variant must not suppress an unrelated
   safe running-text variant. First-page drawings and image placement remain
   render-confirmed candidates. Preserve unequal Word `w:col` widths and
   paragraph-level `w:br type="column"` breaks; do not silently reduce them to
   equal-width `twocolumn` output. Use the generated unequal-column macros
   only as a separately rendered candidate. If a generic `Normal`/`Body Text`
   style conflicts with multiple visible body paragraphs, preserve the named
   style as the default and record a visible-flow body candidate; promote it
   only after same-content PDF comparison.
   For tables and drawings, record the paragraph index of the object and every
   caption candidate. Attach a caption only when a visible label or semantic
   caption style is outside table cells and adjacent/nearby in Word document
   flow. Use that relation for caption-above/below order; otherwise keep the
   language-neutral default and log it. A caption-like table header, distant
   instruction, or generic prose must not define the journal-wide order.
   Resolve the caption/object gap from the two paragraph sides that face each
   other: caption space-after plus object space-before when the caption is
   above, or object space-after plus caption space-before when it is below.
   Emit the larger available value once. If order or both facing sides are
   missing, use and log the caption-gap default; never substitute the caption's
   outside spacing. Preserve that outside caption side separately as the class
   outer-caption skip; do not discard it or merge it into the object gap.
   Treat Word inline/anchor state as placement evidence, not as a LaTeX float
   command. Record a non-floating option only as
   `placement_calibration.status: render_probe`; activate it only after the
   strict same-content promotion gate writes `render_verified` acceptance.
   Keep float/text spacing separate from caption/object spacing. Measure the
   outer boundary only when the neighboring Word paragraph is body-text-like;
   exclude another caption, table/figure note, heading, abstract, keyword, or
   reference role. Store the aggregate as `page.float_spacing_evidence` with
   `mapping: candidate_only`, and activate TeX float lengths only through a
   promoted `page.float_spacing_calibration`.
   When Word has multiple section frames, retain a source-labeled `page-frame.tex`
   candidate alongside `section-flow.tex`; never apply a later section's paper
   size or margins to the entire document without rendered evidence.

4. **Draft `template_spec.json`**
   Convert the evidence packet into a structured spec following `references/spec-schema.md`. Treat this as the evidence ledger, not just a generator input. Clearly mark `source`, `inferred`, `default`, and `unverified` decisions. A section with no representative evidence must remain editable but cannot be claimed visually matched.
   A publisher-prefixed Word style is only a tie-breaker after its semantic
   role matches; if no matching role exists, record an explicit `default`
   role and gap instead of reusing a nearby style from the same family.

5. **Design the LaTeX architecture**
   Follow `references/latex-architecture.md`. Put class-level behavior in `journal-template.cls`: page frame, fonts, title macros, front matter, headings, page style, captions, float defaults, footnotes, bibliography style hooks, and appendices. Put example manuscript content and metadata usage in `main.tex`.

6. **Build the package**
   Create or generate the package, then edit it so a human can maintain it. `main.tex` must contain a compileable representative fixture for every applicable zone: title, authors, abstract, keywords, headings, body, table, figure, equation, footnote, references, and appendix. Class macros or empty placeholder environments alone do not satisfy this requirement. Keep examples long enough to exercise the template, but do not bury format logic in uneditable converted output.
   When source media extraction succeeds, use body-role assets in the editable
   figure example instead of replacing visible source artwork with an empty
   frame. Keep header/footer assets in their own class slots and activate them
   only after the first-page/later-page render comparison supports the placement.

7. **Self-check and optionally render**
   Use `references/verification-checklist.md`. Compile only after the final content and class edits. When a Word source is a sparse template, populate a *copy* with the same representative fixture used in `main.tex` before comparing PDFs; do not compare unrelated placeholder pages. If rendering cannot run, write exact rerun commands and a pending-check list in `README.md`.

8. **Use regression only for the right task**
   If the task includes official Word and official LaTeX templates, compare the Temp2TeX-generated PDF against the official LaTeX PDF built with the same normalized body. If the task is skill improvement, use the 30-case corpus as training signal after the affected case or representative batch, and exclude candidates that fail admission preflight.

## Reference Routing

- Read `references/input-triage.md` first for every conversion task; it defines source-container detection, version selection, sparse-template handling, and inaccessible-source behavior.
- Read `references/model-playbook.md` before ordinary conversion tasks or when deciding task scope.
- Read `references/reconstruction-protocol.md` before extracting a Word template into `template_spec.json`; it defines the evidence packet and the sparse-template comparison procedure.
- Read `references/word-evidence-to-latex.md` after inspecting a Word template and before translating its page, body, title, heading, table, figure, or reference styles into `template_spec.json` and `journal-template.cls`.
- Read `references/latex-architecture.md` before writing or revising `journal-template.cls` and `main.tex`.
- Read `references/spec-schema.md` before writing or editing `template_spec.json`.
- Read `references/format-defaults.md` when official evidence is missing or when selecting Chinese vs English defaults.
- Read `references/verification-checklist.md` before final handoff.
- Read `references/render-compare.md` only when PDF render comparison is possible or explicitly requested.
- Read `references/regression-testing.md` only for official Word-vs-LaTeX regression or skill training work.
- Read `references/system-architecture.md` when changing the bundled workflow or scripts.

## Output Contract

For an ordinary conversion task, deliver an Overleaf-ready folder or zip containing:

- `main.tex`
- `journal-template.cls`
- `references.bib`
- `figures/`
- `assets/`
- `template_spec.json`
- `format_gap_log.md`
- `README.md`

Include `source_inventory.json` when source inspection was performed or when enough evidence exists to make it useful. If PDF comparison was completed, also include:

- `render_compare_report.json`
- `layout_profile/`
- `diff_previews/`
- `promotion_report.json` when a page/body/placement/float-spacing render probe was accepted and the final spec contains `render_verified` calibration

For sources with active section-specific header/footer parts, also include the
generated `page-furniture.tex` candidate. It is an evidence-preserving,
commented file and must not be treated as globally active without a semantic
boundary and same-content PDF check.

For official-LaTeX regression or skill training runs, also deliver the relevant regression artifacts: `manifest.json`, `source_manifest.json`, `case_report.json`, `evaluation.json`, `grading.json`, `benchmark.json`, `benchmark.md`, and `review.html` when review generation is requested.

## Format Coverage Matrix

Before handoff, cover every applicable row. A missing source rule is not a
reason to omit the module; use the documented default and write the gap.

| Module | Source evidence to inspect | Editable LaTeX owner | When evidence is incomplete |
| --- | --- | --- | --- |
| Cover or first page | Word first-page section, `titlePg`, first header/footer, rendered page 1 | `journalcover`, title-page code in `journal-template.cls` | Record a first-page candidate; do not insert a standalone cover without rendered proof. |
| Metadata | Used title, author, affiliation, correspondence styles and direct paragraphs | `\title`, `\author`, `\affiliation`, `\maketitle` | Preserve Word default left alignment when no `jc` exists; centre only with evidence/default. |
| Abstract and keywords | Label/content paragraph indexes, inline/separate/no-label structure, content box, language order, distinct label/content/keyword styles, adjacent paragraph spacing | class-owned abstract environment and keyword helper | Do not inherit the base class abstract layout or infer run-in labels from indentation. Emit every adjacent role boundary once and log defaults. |
| Contents | Word TOC field or explicit author instruction | `\tableofcontents` in `main.tex` | A Contents heading alone is only a render-check candidate. |
| Body and headings | Effective Word style chain, page/body box, numbering, line spacing | class geometry, body helpers, `titlesec` rules | Preserve source evidence and use conservative language defaults. |
| Lists | Word paragraph/style `numPr`, `numbering.xml`, level, label format, and indent | `journalitemize`, `journalenumerate` | Do not confuse numbered list items with headings; retain restart/label geometry as a render-check candidate. |
| Equations | OMML display/inline context, visible number samples, table-cell wrappers | `journalequation`, `amsmath`, appendix counters | Do not pretend OMML was converted to source LaTeX; retain the equation fixture and log unverified number placement. |
| Tables and figures | Caption styles, object adjacency, facing-side spacing ledger, object paragraph and containing section, local column/page width, grid/merges, table header fill/repeat/height/alignment, body drawing dimensions, assets | ordinary and wide journal float helpers, table/header helpers, caption setup, assets | Resolve width against the local Word column and caption gap from the two facing paragraph sides. Use a wide helper only with source-backed span evidence. Keep uncertain geometry editable and verify flow by rendering. |
| Notes | Visible Word footnote paragraphs and author-note rules | `\footnote`, `\thanks`, footnote class setup | Separator nodes alone are not format evidence; retain normal LaTeX notes and log verification. |
| Endnotes | Visible Word endnote paragraphs, placement instruction, marker sequence | `\journalendnote`, `\printjournalendnotes` | Ignore Word separator-only nodes; enable endnotes only with visible text evidence and log placement verification. |
| References | Entry font, indents, citation guidance, official `.bst` | bibliography hooks, `references.bib` | Apply fixed source indent when backend-safe; keep label-dependent hanging indent pending. |
| Appendices | Section label, boundary, and equation/table/figure examples | `\journalappendix` | Verify `A.1` counters. Keep flow continuous unless an isolated same-content probe proves appendix is the sole shifted anchor and a new-page boundary passes strict promotion. |

## Completion Criteria

Ordinary conversion is complete when:

- The required package files exist and are editable.
- `journal-template.cls` owns class-level formatting and `main.tex` demonstrates correct usage.
- `template_spec.json` records official evidence, inferred rules, defaults, and source gaps.
- `format_gap_log.md` names unsupported or ambiguous requirements instead of hiding them.
- Every source-backed visual claim has a recorded evidence location; zones supported only by defaults are named as unverified defaults, not described as matched.
- `README.md` explains how to compile, how to rerun optional visual checks, and which verification stages were completed or pending.
- Required content zones are represented by compileable `main.tex` examples: title/cover when relevant, author metadata, abstract, keywords, headings, body paragraphs, tables, figures, equations when relevant, footnotes, references, and appendices. A class interface without an exercised example is incomplete.
- Chinese templates use CJK-safe XeLaTeX defaults; English templates avoid unnecessary CJK machinery.

Verification is complete when local tools allow it and:

- The generated LaTeX compiles without fatal errors after the final `main.tex` and class edits.
- The best available renderer produced a reference PDF from the original Word/PDF source when applicable.
- The generated PDF was compared against the reference PDF or official LaTeX golden PDF.
- The comparison report records page count, page size, required zones, visual diff previews, and prioritized layout issues.

Skill training or official-LaTeX regression is complete only under explicit benchmark work. A regression case passes only when official source evidence is recorded, both normalized PDFs compile, page count and page size gates pass, required zones are present in both PDFs, and visual thresholds pass. Keep `not_comparable` strict; replace or fix a case rather than lowering the gate.

## Optional Tooling

These bundled scripts are optional accelerators for deterministic extraction, rendering, generation, and regression. Use them when the execution environment supports them. If a script or dependency is unavailable, perform the same reasoning manually and record the unavailable verification stage.

- `scripts/inspect_sources.py <source> --output source_inventory.json`
  Extract source file metadata and DOCX/PDF structural signals. It detects OpenXML by package contents before trusting the filename; only true legacy `.doc`, `.dot`, and `.rtf` files use LibreOffice when available to create a temporary DOCX for structural inspection.
- `scripts/render_docx_reference.py <docx> --outdir reference-render`
  Render the original DOC/DOCX through available engines and choose a reference PDF.
- `scripts/draft_spec_from_inventory.py source_inventory.json --notes official_notes.txt --output template_spec.json`
  Draft a first `template_spec.json` from extracted source signals and official guide notes. When a heading style lacks a size, fill only that field from role-matched explicit Word template prose while retaining the instruction sentence and paragraph index.
- `scripts/generate_latex_package.py template_spec.json --outdir latex-package [--word-source official-template.docx] [--source-inventory source_inventory.json] [--promotion-report promotion_report.json]`
  Generate `main.tex`, `journal-template.cls`, bibliography placeholder, assets folders, and gap log. Add `--word-source official-template.docx` to copy embedded Word assets into `assets/` and write an asset manifest; add `--source-inventory source_inventory.json` to retain the audited evidence packet in the output package. Pass `--promotion-report` only with an accepted report and a `render_verified` spec; the generated README then records the verified calibration without claiming that future manuscript content was compared. Use `--apply-source-header-assets` only after render comparison confirms the later-page Word header/footer candidate geometry. Use `--apply-first-page-furniture` only for a separately confirmed first-page candidate; it activates a distinct first-page style instead of reusing its furniture on later pages.
- `scripts/extract_word_assets.py official-template.docx --outdir latex-package/assets`
  Extract embedded Word media and record whether each asset is referenced by the body, header, or footer. DOCX/DOTX/DOTM are read directly; legacy DOC/DOT/RTF are converted through LibreOffice when available, while retaining the original file as evidence. EMF/WMF assets receive a PNG companion when conversion succeeds; use `latex_output` from the asset manifest rather than embedding a metafile directly. Use before reproducing cover or page-style assets when generation is not invoked with `--word-source`.
- `scripts/compile_latex_package.py latex-package/main.tex --output compile_report.json`
  Compile the generated LaTeX package with latexmk or a direct TeX engine and record the result. It removes a same-named old PDF before compiling and publishes `pdf` only after every required command succeeds; a PDF written before a fatal TeX error is recorded only as `partial_pdf` and must never enter comparison.
- `scripts/validate_latex_package.py latex-package --output package_validation.json`
  Check the ordinary package contract before handoff: required editable files/directories, valid spec JSON, all required evidence sections, language/engine/page-frame decisions, fallback-record shape, unresolved generator placeholders, absolute local paths, and basic README/gap-log completeness. It does not replace compilation or PDF comparison.
- `scripts/compare_pdfs.py reference.pdf generated.pdf --outdir render-compare`
  Render both PDFs to page images and produce diff images plus a JSON comparison report.
- `scripts/profile_pdf_layout.py reference.pdf generated.pdf --outdir layout-profile [--anchors-json anchors.json]`
  Extract body-only text boxes, semantic anchors (including phrases wrapped across nearby overlapping lines), line gaps, same-column baseline steps, font-size medians, header/footer occupancy, and image counts from PDFs, then summarize likely visual-failure causes and non-automatic calibration hints. The built-in unique anchors match only the bundled regression fixture. For any other same-content manuscript, supply unique zone phrases with `--anchors-json`; never use generic words such as `Table`, `Figure`, or `References` as anchors.
- `scripts/suggest_page_calibration.py template_spec.json layout-profile/layout_diagnostics.json --output page_render_calibration_proposal.json`
  Produce a `pending` page-margin proposal from small, consistent text-box edge deltas. It never edits the spec or marks a calibration verified; large displacement is rejected as likely content-flow or float behavior that needs structural repair first.
- `scripts/materialize_page_calibration_candidate.py template_spec.json page_render_calibration_proposal.json --output candidate_spec.json`
  Create a separate `render_probe` spec for explicit regression only. Generate its candidate package with `generate_latex_package.py candidate_spec.json --apply-render-probe`; never replace the ordinary source spec unless the same-content comparison accepts the candidate.
- `scripts/suggest_body_calibration.py template_spec.json layout-profile/layout_diagnostics.json --output body_render_calibration_proposal.json [--allow-page-count-repair]`
  Propose a bounded body-font/baseline candidate when page count, body width, anchor pages, and cross-page measurements are stable. For an output that is too long, `--allow-page-count-repair` permits one isolated tightening candidate only when at least two pages are comparable, every measured anchor shifts later, body-box width is within 30pt, and the generated body font is stably at least 1pt too large. Other pagination signatures return `candidate_available: false`; never force them into the class.
- `scripts/materialize_body_calibration_candidate.py template_spec.json body_render_calibration_proposal.json --output candidate_spec.json`
  Create a separate `document.render_calibration.status=render_probe` spec, retaining whether it is stable calibration or body-density page-count repair. Generate it with `--apply-render-probe`, compare the same content against both the reference and ordinary package, and retain it only when structural gates stay satisfied and visual metrics improve.
- `scripts/promote_render_probe.py template_spec.json candidate_spec.json --ordinary-compare ordinary/render_compare_report.json --candidate-compare candidate/render_compare_report.json --ordinary-layout ordinary/layout_diagnostics.json --candidate-layout candidate/layout_diagnostics.json --candidate-compile candidate_compile_report.json --output verified_spec.json --report promotion_report.json`
  Close the page/body/placement/float-spacing/backmatter/appendix-boundary calibration loop without relying on informal model judgment. Compare the spec copies from the ordinary and candidate generated packages when `--word-source` added relative asset-manifest metadata; do not compare a pre-extraction source spec with a post-extraction candidate spec. The tool permits changes only under the documented calibration paths; requires the same reference PDF, successful candidate compilation, matching repaired page count and size, no new anchor failures, and the path-specific visual/layout improvements. It writes a portable `render_verified` spec only when every gate passes. A rejected probe produces only the report and must not replace the ordinary package.
- `scripts/preflight_corpus.py --manifest <manifest.json> --outdir <preflight-dir> [--cases <case_id> ...]`
  Admit corpus candidates before expensive regression by validating the official Word payload, recording its hash, and rendering it to a reference PDF. Missing official LaTeX is allowed; inaccessible or non-renderable Word sources are rejected or replaced.
- `scripts/normalize_word_stress.py official-template.docx --output normalized.docx --report word_normalization_report.json`
  For explicit regression only, create a working copy containing the fixed representative fixture while retaining role styles, explicit continuous front-matter-to-body column transitions, and inherited header/footer references. Never overwrite the official Word artifact. Reject or repair a normalized reference that changes section flow before using it to train the skill; treat unsuccessful normalization as `not_comparable`, not as a reason to compare unrelated placeholder pages.
- `scripts/run_regression.py --manifest <manifest.json> --outdir <iteration-dir> [--cases <case_id> ...] [--variant-search] [--source-font-probe] [--heading-color-probe] [--reference-layout-probe] [--body-style-probe] [--figure-placement-probe] [--table-placement-probe] [--float-spacing-probe] [--table-geometry-probe] [--text-box-placement-probe] [--backmatter-boundary-probe] [--appendix-boundary-probe] [--furniture-geometry-probe] [--first-page-furniture-probe] [--review]`
  Run the corpus only for explicit comparison or skill training. `--backmatter-boundary-probe` tests one new-page boundary before acknowledgements/data/references only when those late anchors shift together and generated output is too short. `--appendix-boundary-probe` is narrower and requires appendix alone to shift. Neither changes ordinary output without strict PDF promotion.
- `scripts/analyze_regression_training.py --run batch=iteration-dir ... --output-json training_signal.json --output-md training_signal.md`
  Aggregate multiple regression runs into a training-signal report for skill improvement.

Patch scripts only when source evidence or training results show a reusable need. Keep script outputs in the project folder so the conversion can be audited.

## Guardrails

- Do not turn a normal single-journal conversion into the 30-case regression suite.
- Do not invent official requirements. When evidence is missing, use defaults and label them as defaults.
- Do not stop merely because local render tools are missing. Deliver the LaTeX package plus a verification plan.
- Do not deliver an opaque converted manuscript as the template. The output must be maintainable LaTeX.
- Do not optimize one journal with brittle hard-coded layout rules unless the rule is source-evidence driven and generalizes.
