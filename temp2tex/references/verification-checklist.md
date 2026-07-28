# Verification Checklist

## Contents

- [File-Level Check](#file-level-check)
- [LaTeX Compile Check](#latex-compile-check)
- [PDF Visual Check](#pdf-visual-check)
- [Official-LaTeX Regression Check](#official-latex-regression-check)

Use this checklist before handing off a normal Temp2TeX package. The package can be delivered even when local render tools are missing, but the verification status must be clear.

## File-Level Check

Confirm the output folder contains:

- `main.tex`
- `journal-template.cls`
- `references.bib`
- `figures/`
- `assets/`
- `template_spec.json`
- `word_format_ledger.json` when the Word source was readable as an OpenXML package
- `manual_evidence_ledger.md` and `manual_mapping_audit.md` when structured
  Word inspection or audit helpers were unavailable
- `format_gap_log.md`
- `HANDOFF_STATUS.md`, stating the current phase, ordinary-handoff boundary,
  completed checks, and exact next action
- `front_matter_semantic_confirmation.json` when
  `word_format_ledger.json.front_matter_sequence_review` requires semantic
  confirmation; it must match the ledger fingerprint and confirm every ordered
  front-matter evidence record exactly once
- `README.md`
- `source_feature_coverage.json` when `source_inventory.json` is present

Run `validate_latex_package.py <package-directory>` when available. Without
`--output`, it writes `package_validation.json` inside that package rather than
the caller's working directory. Treat `valid: false` as a handoff blocker;
either fix every reported contract error or explicitly label the result a
continuation checkpoint rather than an ordinary completed conversion. Treat
warnings as items to resolve or document. The check does not prove PDF
fidelity, so retain the compile and visual stages below.

Before relying on a prior `valid: true` report, confirm that its
`schema_version` is supported and that `package_contract_fingerprint` matches
the current package. A report becomes stale after an editable class, fixture,
source-evidence, asset, specification, README, or gap-log change; rerun the
validator instead of carrying its result forward.

The initial `HANDOFF_STATUS.md` must remain a blocked continuation checkpoint.
For ordinary delivery, validate the completed package first, then mark
`Ordinary handoff: ready`, `Package validation: valid`, and copy the current
16-character package fingerprint from the validation report into
`Package fingerprint`. Run the validator again after that update. The status
file is excluded from the fingerprint, so this final status update is stable;
any later editable package change makes the status fingerprint stale and
returns the package to a continuation checkpoint.

If source capture, mapping, ownership, and package structure are complete but
the local validator, TeX engine, or renderer is unavailable, a package may be
delivered with `Ordinary handoff: ready_with_pending_local_verification`.
That state requires `Package validation: pending`, `Package fingerprint:
pending`, `Verification environment: unavailable`, and exact rerun commands
under `Required Next Action` and in `README.md`. It does not authorize a
missing source-mapping decision, an unresolved package-contract error, or a
visual-fidelity claim.

Also check:

- `main.tex` loads the delivered `journal-template.cls` through
  `\documentclass{journal-template}` (with only ordinary class options or a
  package-relative `./journal-template` prefix). A present but unused class
  file is not a class-based template package.
- `HANDOFF_STATUS.md` uses machine-readable values for ordinary handoff
  (`ready`, `ready_with_pending_local_verification`, or `blocked`), package
  validation (`valid` or `pending`), verification environment (`available`,
  `unavailable`, or `pending`), and a current 16-character package fingerprint
  when validation is valid. A ready handoff with a pending validation result,
  unavailable environment, or stale fingerprint is not an ordinary delivery.
  The pending-local-verification state requires the paired pending fields and
  an unavailable environment; it is not a substitute for mapping completion.
- Read `source_feature_coverage.json` before rendering. Generate it again after
  strict atomic audit with `--atomic-audit atomic_mapping_audit.json`. Resolve or explicitly
  retain its `critical` and `high` `needs_mapping` entries; do not use PDF
  micro-calibration to compensate for a missing title, line-number, page
  furniture, or run-typography mapping.
- When `word_format_ledger.json` is present, confirm every source-backed role
  decision names its paragraph/run evidence IDs and its editable LaTeX owner.
  Resolve numbered pre-abstract affiliation lines before heading candidates;
  do not let them become sections.
- When `word_format_ledger.json.source_conversion.status` is
  `converted_for_inspection`, confirm its original source hash and the
  package-relative retained derived DOCX both exist and match their recorded
  hashes. Treat the derived file as inspection evidence only; compare it with
  an original legacy render or a trusted official PDF before a source-fidelity
  claim.
- Perform the atomic reconstruction audit from
  `references/atomic-reconstruction.md`: first confirm
  `word_format_ledger.json.coverage.all_visible_text_units_captured` is true.
  Every selected paragraph/run, table cell, drawing, note, page-furniture, and
  text-box record must be `mapped`, `default`, `guidance`, `unresolved`, or
  `not_observable`. A generated package with unreviewed
  proposed mappings is not ready for visual calibration.
- Generate `atomic_mapping_decisions.json` from the Word ledger and run
  `audit_atomic_mapping.py` in strict mode. Confirm its
  `atomic_mapping_audit.json` has zero `needs_decision` and
  `invalid_decision` entries and that `source_capture_complete` is true. Do not accept a paragraph-level decision as a
  substitute for a visible local run that has different formatting or semantic
  status.
- For every `mapped` or `default` atomic decision, confirm `latex_file` is a
  package-relative `.cls` or `.tex` file and that `latex_token` appears outside
  comments in that exact file. A generic command found elsewhere in the package
  is not proof of the claimed editable owner.
- For every `guidance` decision, confirm `guidance_kind` is exactly one of
  `author_instruction`, `editorial_note`, `placeholder_example`,
  `template_scaffold`, or `non_manuscript_furniture`, and that the reason
  explains why it does not define a LaTeX formatting rule. Do not use
  `guidance` as a substitute for an unresolved format mapping.
- Confirm `source_feature_coverage.json.summary.ledger_source_capture_complete`
  and `.atomic_mapping_audit_complete` are both true. The report must retain
  ancillary role entries for running furniture, notes, and floating text where
  observed, and `.atomic_mapping_audit_matches_ledger` must be true; body-only
  coverage or an audit from another Word template is not an alternative gate.
- Confirm local run formatting stays local unless all role-matched visible
  runs support promotion. In particular, a trailing red instruction in an
  author sample cannot colour the author class rule, and an instructional
  caption cannot define the figure or table caption format.
- Confirm `source_feature_coverage.json.ledger_role_audit` has no
  `needs_mapping` record before visual calibration. A
  `mapped_pending_visual_confirmation` role has an editable implementation,
  but is still an explicit evidence/render task and must not be described as
  visually matched.
- Before visual calibration, create a role-level same-content anchor contract
  for every applicable fixture zone. It must cover front matter, heading/body,
  table/caption/note, figure/caption, notes, references, and appendix where
  present. Every declared anchor must appear in both PDFs; a partial match is
  a fixture failure, not permission to tune the class.
- Do not declare a full-document contract merely because the normalizer
  injected a table or figure. If the official Word source has no observable
  table or body-artwork evidence and the two paths have not independently
  established the same structure, keep those defaults outside the full
  calibration scope. Use a `partial_zone` diagnostic, record the limitation,
  and do not tune global page, body, float, caption, or table rules from it.
  A shared neutral raster placeholder may be used only to compare its frame;
  its interior can be masked after both paths use the same declared dimensions.
- Select anchor phrases from the actual fixture language and profile. An
  English stress-body map cannot validate a Chinese or bilingual fixture, and
  a Chinese phrase absent from the generated package cannot be ignored just to
  make the contract pass. Save the map with the comparison report, identify
  its language/profile, and use short unique phrases from the rendered roles.
  For the supplied CJK `latex-default` fixture, request the normalizer's
  `--anchors-output`; do not substitute the English default map.
- A header/footer-only diagnostic may use an explicit `partial_zone` map with
  named `page_fixed` zones, each declaring its source page and normalized `rect_ratio`.
  Bind every furniture phrase to its zone and give each placement-sensitive
  phrase a conservative `max_bbox_delta_pt`. For a logo or other artwork,
  set `required_image_count` and, when the source uses an image box,
  `max_image_box_delta_pt`. A local candidate is eligible only when
  `local_zone_gate_status` is `passed`; text merely occurring somewhere in
  either PDF is not enough. Its result may assess only the declared local
  furniture; it is not a full-document same-content contract and must not
  promote margins, body density, captions, floats, pagination, or a general
  fidelity claim.
- A manuscript-flow diagnostic must not reuse a page-fixed rectangle. Declare
  `placement_model: flow_relative`, name a unique already-declared
  `context_anchor`, and bind each local phrase with a conservative
  `max_bbox_delta_pt`. Confirm the context and each target occur on the same
  page in both PDFs and inspect `relative_bbox_delta`; a missing context, a
  cross-page target, or `failed_flow_context_anchors` blocks the local result.
  That result can verify only the stated local relationship, never global
  pagination, margins, density, or header/footer placement.

- The template does not depend on stale `journal-template.sty` unless deliberately used as a compatibility shim.
- `main.tex` compiles from the package root without absolute local paths.
- Figures use relative paths under `figures/` or `assets/`.
- If Word text boxes exist, confirm `textboxes.tex` preserves their source
  labels, text, and any available width/height/relative-offset/wrap geometry;
  keep it commented/not auto-input and marked pending until a rendered
  comparison confirms manuscript role and placement. Do not count duplicate
  XML views of one shape as separate manuscript objects.
- If Word has multiple sections, confirm `section-flow.tex` preserves their
  order and break types, keeps continuous boundaries free of automatic page
  breaks, and remains commented/not auto-input until semantic boundary and PDF
  pagination checks are complete. Confirm `page-frame.tex` preserves each
  section's paper size and margins; do not apply a later section frame to the
  whole document without rendered evidence.
- For a one-column-to-multicolumn transition, verify the adjacent Word section
  pair rather than only the document-wide column count. A `continuous` break
  may use a wide front-matter transition; a `nextPage` break must retain a
  one-column front-matter page before the multicolumn body. Do not use a
  LibreOffice-rendered DOCX as the visual calibration reference for the latter
  case: record it as `not_comparable` unless Microsoft Word rendering is
  available, but still compile and structurally audit the generated package.
- If active Word header/footer parts differ by section, confirm
  `page-furniture.tex` records each section and active part as a commented
  editable candidate. Do not replace the ordinary global page style with a
  section candidate until the corresponding manuscript boundary and rendered
  reference are confirmed.
- `README.md` lists compile command, required engine, optional render comparison command, and known gaps.
- `template_spec.json` and `format_gap_log.md` agree on defaults and missing evidence.
- When `source_inventory.json` records source files but no inspectable Word
  paragraph/run ledger, retain non-empty `manual_evidence_ledger.md` and
  `manual_mapping_audit.md`. The first must use the required source-location,
  observed-format, role, status, owner, and next-check fields; the second must
  keep a zone/status/ledger/pending audit. Do not create a fake empty
  `source_feature_coverage.json` merely to look like the structured path.
- When `template_spec.json assets.extraction_required` is true, retain
  `assets/word_asset_manifest.json` and every manifest output file under
  `assets/`. Check its source-media paths, output filenames, and byte counts.
  If extraction tooling was unavailable, do not invent a manifest: state the
  asset-extraction rerun action in `format_gap_log.md`. This preserves media
  evidence without forcing manuscript body artwork into the editable fixture.
- Confirm `main.tex` exercises at least one citation command and either an
  inline bibliography entry or an explicit bibliography backend. Keep at least
  one editable BibTeX entry in `references.bib`, even when the default fixture
  uses `thebibliography` to avoid assuming a publisher backend. An empty
  reference section or database does not exercise citation formatting.
- Confirm the uncommented `main.tex` also exercises title creation, abstract,
  heading, table, figure, equation, and, unless `footnotes.enabled` is false,
  footnote or author-note interfaces. A class definition, a commented example,
  or an empty placeholder directory is not fixture coverage. Custom class
  commands are acceptable when they actually invoke the corresponding editable
  role in `main.tex`.
- Unless the corresponding `front_matter` or `abstracts.keywords` field is
  explicitly false, confirm `main.tex` invokes editable author, affiliation,
  and keyword interfaces. Keep observed publication identifiers, dates,
  funding, and contributor notes in the commented `metadata.tex` skeleton
  rather than copying filled article values into the default fixture.
- When `front_matter.metadata_style.kind_styles` contains source-backed kinds,
  require a non-empty `metadata.tex` skeleton that names each kind and retain a
  commented `\input{metadata.tex}` in `main.tex`. This is evidence of an
  editable metadata interface, not permission to copy source article values.
- `main.tex` exercises each applicable module with real, compileable content: title/authors, abstract/keywords, headings/body, at least one table, figure, equation, footnote, bibliography citation/reference, and appendix. Class commands or empty placeholders do not count as coverage.
- When `template_spec.json.body.lists.systems` has more than one entry, `main.tex` exercises every observed list family and nesting level. Verify label text, counter start/restart, left and hanging indentation, and item spacing; a bullet or number alone is not a list-format pass.
- When Word OMML equations are present, check every `equations.latex_candidates` record against a corresponding `equation.instance` decision. Verify display versus inline placement, number/tag form and position, paragraph alignment, and appendix counter behavior separately from formula syntax.
- When `page.block_decorations.present` is true, each source paragraph border/shading/frame needs a `block.decoration` decision and a rendered check of border sides, stroke, fill, padding, width, anchor, and surrounding flow. A generic LaTeX box is only a starting point, not confirmation.
- Confirm `main.tex` orders declarations/statements, references, then appendix; a bibliography fixture after `\journalappendix` is a hard package error.
- For `zh` or `mixed` sources, retain Word Latin and East Asian fonts separately.
- For `zh` or `mixed` sources, require `template_spec.json`
  `document.engine: "xelatex"` and use that same engine in the README compile
  command. A PDFLaTeX or LuaLaTeX success does not satisfy this Temp2TeX
  package contract unless the language classification itself is corrected.
- For `zh` or `mixed` sources, ensure `main.tex` exercises visible CJK fixture
  text in the title, abstract, body, or another applicable template role. A
  Chinese label hidden only in the class or an ASCII-only smoke fixture does
  not verify source-script font selection, line breaking, or baseline behavior.
- When `page.body_paragraph_spacing_evidence.status` is `source`, confirm the
  saved instruction explicitly requires continuous body paragraphs and that the
  class uses its recorded zero skip. A generic style after-space alone must not
  override this source rule.
  If a named CJK font is not locally available and render-verified, keep the
  CTeX fallback and record the font gap instead of declaring it reproduced.
- When Word uses an 8pt or 9pt body, confirm the generated class applies that
  non-standard size explicitly. Standard LaTeX/CTeX class options only support
  10pt, 11pt, and 12pt.
- Preserve half-point Word body sizes such as 10.5pt as explicit LaTeX font
  settings rather than rounding them to a class option. For Word `exact` line
  spacing, keep the physical source metric and require rendered calibration;
  do not treat its raw twip value as a generic `\linespread` ratio.
- For integral source sizes, inspect the generated class option: it must be
  exactly `10pt`, `11pt`, or `12pt`, never `10.0pt` or `11.0pt`, which standard
  `article` and `ctexart` silently ignore.
- When `template_spec.json` contains `template_style_candidate`, ensure
  `format_gap_log.md` lists the affected roles and that the handoff does not
  claim visual matching before a populated same-content Word reference exists.
- When `page.source_body_style.visible_flow_override_candidate` exists, keep
  the named style and visible Word exemplar immutable in ordinary output. Test
  the explicit body-style probe through
  `document.render_calibration.body_style_mode: visible_flow_exemplar`, first
  with `status: render_probe` and then only after strict promotion with
  `status: render_verified`. Reject it when page count, required zones, or
  layout penalty worsens even if its mean pixel diff is smaller; never write a
  render mode into `page.source_body_style`.
- Apply `page.render_calibration` only after a same-content PDF comparison
  improves page-frame/body-box metrics without breaking page size, page count,
  or required structural zones. Keep the Word-derived margins and column gap
  unchanged as source evidence; the verified calibration is a separate layer.
- Treat a stable horizontal body-box mismatch as page-frame evidence. When
  later anchors move vertically or across pages while the front matter remains
  close, classify it as pagination/structural flow and repair column
  transition, float/caption flow, or forced breaks before changing margins.
- Apply `document.render_calibration` only through a separate body-density
  candidate after page count, body-box width, and anchor pages are stable.
  The sole pagination exception is an isolated tightening probe when generated
  output is longer, at least two pages compare, all anchors move later, width
  delta is at most 30pt, and font excess is stable and at least 1pt.
  Require measurements from at least two comparable pages and reject unstable
  cross-page font/baseline deltas. Compare candidate against the ordinary
  package: compile success is insufficient. The pagination exception must
  repair page count and all anchor shifts, improve density and layout scores,
  and leave any existing body-box width mismatch non-worse. Keep original Word font size and
  line-spacing evidence unchanged even when the candidate is render-verified.

## LaTeX Compile Check

If TeX is available:

1. Make all intended `main.tex` and class edits first, then compile from a clean directory. Do not report an earlier PDF as verification of later edits.
2. Prefer the engine required by the template, usually XeLaTeX for Chinese or mixed-language sources.
3. Use `compile_latex_package.py` when available. Its default MiKTeX mode disables automatic installer prompts; treat `diagnostics.failure_category: missing_tex_dependency` as an environment requirement, record the missing `.sty`/`.cls` name, and do not misclassify it as a Word-to-LaTeX reconstruction defect. Use `--allow-auto-install` only when an interactive local installation is intentional.
4. Record fatal errors, missing packages, missing figures, bibliography warnings, overfull boxes that affect layout, and output PDF path.
5. Fix template fatal errors before delivery. A missing local TeX dependency may remain a clearly documented pending verification item, but it cannot support a compile-success or PDF-comparison claim.

If TeX is unavailable:

1. Do not stop the conversion.
2. Put exact compile commands in `README.md`.
3. Mark compile verification as pending in `format_gap_log.md`.

## PDF Visual Check

If a reference PDF and PDF tools are available, compare in this order:

1. Page size and orientation.
2. Page frame, margins, columns, header/footer, page numbers.
   Verify header/footer text, rules, logos, and first-page exceptions against
   the original page image; confirm every referenced path exists under `assets/`.
   When Word supplies an `even` header/footer variant, confirm the generated
   class uses `twoside` and inspect at least one odd and one even rendered
   page. For a first-page logo beside masthead text, confirm that both the
   asset and every ordered text paragraph remain visible; an asset-only header
   is a failed reconstruction even when the PDF compiles.
   Preserve a nonstandard Word page size exactly, use the source column gap,
   and check any Word gutter or mirrored-margin setting before comparing the
   body box. Treat Word header/footer distances as placement evidence that
   still requires a visual confirmation.
   Confirm that generated header/footer text comes from the active Word
   section variant. A `PAGE` field may become a dynamic page number. A
   literal numeric token may also become `\thepage` only when multiple active
   section variants demonstrate a changing page-number sequence, including
   alternating left/right page positions. Pure text/page-field furniture and
   deterministic rules may be enabled when each active Word part is
   unambiguous; an unsafe image-bearing part must not disable a separate safe
   text/page-field part. Keep extracted header/footer images and first-page
   drawing placement pending until the reference PDF confirms their position
   and visibility. When the comparison target is an official
   LaTeX golden, it may intentionally omit Word submission furniture: retain
   the extracted commands but reject that candidate rather than forcing it
   into the final class. For each explicit Word `w:pgNumType`, verify its
   LaTeX number format and counter restart at the same semantic section
   boundary. Front-matter Roman numbering and article Arabic numbering must be
   tested across the transition; do not accept a globally correct `\thepage`
   as evidence of a restart rule.
   Compare first-page furniture separately from later running furniture. Check
   the first page for publisher masthead, logo, issue/copyright metadata,
   received/accepted information, licence text, and citation blocks; then
   inspect one odd and one even later page for their distinct running text and
   page-number slots. A first-page block must not be merged into `\pagestyle`
   for all pages, and a default/odd header must not stand in for an unreviewed
   even-page header. When the source contains several first-page footer
   paragraphs, verify their order and presence as a block rather than accepting
   only the first line. Treat image interiors as out of scope, but verify their
   frame, size, anchor, and relationship to adjoining rules or text.
   When a Word first-page footer is visibly positioned above the physical page
   bottom, do not infer that an ordinary `fancyfoot` placement is faithful.
   Keep it as a separately calibrated first-page footer candidate; apply a
   `first_page_footer_slot_raise_pt` value only from a render-verified local
   zone report, and retain the zero-offset ordinary package otherwise.
3. Title block and author block.
   Before it, determine whether the Word first-page variant is a standalone
   cover or merely title-page furniture. Verify this against the rendered first
   page before enabling a cover environment. Check each front-matter boundary appears exactly once in the class and
   matches `front_matter.spacing_boundaries`; no affiliation-local plus
   post-maketitle duplicate is allowed.
4. Abstract and keywords.
   Confirm label-only, inline-label, and no-label Word structures remain
   distinct, with separate label/content styles and paragraph indexes. The
   generated class must redefine the abstract environment in every mode and
   must not inherit `article`'s quotation width, heading, or skips. Verify the
   abstract-to-keywords boundary is emitted once.
5. Contents.
   If a TOC field was detected, compile twice and compare its title, depth,
   page break, and page-number behavior before treating it as complete.
6. Heading hierarchy and spacing.
   Verify each heading level against a used Word style, a direct-format
   exemplar, or an official instruction. Keep literal sample prefixes such as
   `1 Introduction` separate from automatic Word numbering: enable LaTeX
   counters only when a representative `w:numPr`, a used numbered heading
   style, an instruction, or repeated rendered pages establishes the mechanism.
   If heading evidence is absent, record the selected Chinese or English
   fallback and make the populated Word comparison copy use that same fallback;
   a plain-Word injected heading is not a valid reference for a styled LaTeX
   default. Compare label visibility, numbering, size, weight, case, before and
   after spacing, and run-in behavior separately. When an enabled Word
   `keepNext` exists on a heading level, confirm that only that level receives
   the bounded heading-plus-one-line page guard; an explicit `w:val="0"` must
   not activate it.
7. Body paragraph density, indentation, and line spacing.
   If the Word body font is installed locally, the generated class may use it
   behind a compile-safe `\IfFontExistsTF` fallback. Compare it as a measured
   candidate against the fallback before claiming visual fidelity; a matching
   font name alone does not prove matching metrics.
   Prefer same-column top-to-top baseline steps over raw adjacent-line gaps for
   PDF density diagnosis. Do not propose global font/baseline calibration while
   page count differs, body width is unstable, or later anchors change pages.
   Resolve body paragraph boundaries once as `max(space_before, space_after)` and
   apply any resulting `\parskip` only inside the class body environment. For a
   Word boundary of at least 6pt, allow only isolated 0.5, 0.75, and 1.0 render
   probes; do not alter the ordinary source evidence.
   Never promote a page/body render probe because it compiles or improves one
   page. Under `stable_visual_calibration`, confirm the candidate changes only
   calibration paths, uses the same reference PDF, preserves page count and page
   size, introduces no anchor failures, lowers mean diff, and does not worsen
   maximum diff or layout penalty. Under `page_count_repair`, require the
   candidate to match the complete reference page count and page size, preserve
   all required zones, remove anchor page shifts, improve layout, and remain
   inside bounded pixel tolerances. Keep a rejected probe out of the final spec
   and package.
8. Tables: caption, rules, notes, width, alignment.
   Confirm that `main.tex` places each representative caption according to
   `caption_position_evidence`. A source-backed order needs an external,
   adjacent/nearby Word relation; table-cell text, a distant caption, or generic
   instructional prose must leave the default documented in the gap log.
   Compile a multi-column representative table: `\journaltablewidth` must be a
   real LaTeX length so fractional column widths cannot expand into an illegal
   unit.
   In a two-column package, confirm that a column-sized Word table resolves
   against local column width and is not shrunk by a page-wide ratio. Require
   source-backed local-section evidence before the fixture uses
   `journaltablewide`/`table*`.
   Inspect `caption_spacing_evidence`: the selected side must face the table,
   the raw twips and resolved points must agree, and the class must emit the
   boundary once. A below-table caption must not use its own space-after as the
   table-to-caption gap; preserve that value separately as the outer skip.
9. Figures: placement, size, caption, subfigures if present.
   Compare Word table grid/merged-cell evidence and image dimensions before
   applying a template-wide width. Confirm any Word inline or anchored image
   placement against the PDF; XML anchor state alone does not justify changing
   the class-wide float policy. Retain source media in `assets/` even when its
   final LaTeX position remains pending. Do not insert a filled sample
   manuscript's body artwork into the default `main.tex` fixture; use an
   editable placeholder so the delivered package is a template rather than a
   partially converted article.
   Inspect `figures.layout_evidence.selection_status`. A caption-attached
   drawing may support geometry and caption relation. An uncaptioned inline
   drawing may support geometry only. An uncaptioned anchored drawing must
   remain evidence-only and must not set the representative figure width,
   caption position, or float policy. Each uncaptioned selection requires a
   matching `format_gap_log.md` entry.
   Confirm an unverified non-floating option is stored only as
   `placement_calibration.status: render_probe` and leaves the generated class
   floating. Promote exactly one placement path at a time; require the same
   reference, successful compile, stable geometry and anchors, lower mean diff,
   non-worse maximum/layout metrics, and a non-worse float diagnostic score.
   Only the resulting `render_verified` acceptance may activate non-floating
   `journalfigure` or `journaltable` output.
   A table and figure placement probe may be combined only when the same Word
   evidence packet shows both object classes in the manuscript stream and each
   isolated probe has already been evaluated against the same fixture. Treat
   the combination as one bounded `render_probe`, not a parameter search or a
   new source rule. It must beat the ordinary package and both isolated probes
   on the required structural gates and visual/layout metrics before it can be
   promoted. A partial improvement remains rejected and stays out of the final
   spec and class.
   When promotion accepts a candidate, regenerate the deliverable from
   `verified_spec.json` plus `promotion_report.json`, then compile and run the
   package validator on that regenerated directory. Never deliver the temporary
   regression candidate as the final package.
   Confirm the selected drawing's paragraph maps to the recorded Word section.
   A near-column drawing should be about `\linewidth`, not half a column; only
   a clearly spanning source object may use `journalfigurewide`/`figure*`.
   For an above caption compare caption-after/object-before; for a below
   caption compare object-after/caption-before. Confirm the larger measured
   side is used once. If order or both facing sides are missing, require an
   explicit default and a gap-log entry instead of using the outside side.
   Confirm the opposite caption side maps independently to the outer skip and
   is not lost when the internal gap changes.
   Inspect `page.float_spacing_evidence` separately. Confirm only body-text
   neighbors contribute; another caption, object note, heading, abstract,
   keyword, or reference role must remain in the raw ledger but be excluded
   from the aggregate. Ordinary output must not set TeX float-spacing lengths
   from this evidence. A candidate may set `textfloatsep`, `intextsep`, and
   `dbltextfloatsep` together only for same-content comparison. Promote it only
   when it is the sole active path and all structural, visual, and float-score
   gates pass.
   Check appendix and unrelated examples remain ordinary even when the selected
   representative object is wide.
10. Footnotes and author notes.
   Verify marker sequence, footnote font, paragraph format, separator rule,
   and first-page author-note behavior. Do not infer these from Word separator
   nodes alone; use visible footnote samples or a rendered manuscript.
11. References and citation style.
   Check bibliography font, left margin, label width, and hanging indent
   against the chosen backend rather than assuming Word paragraph indents map
   one-to-one.
12. Appendices and appendix numbering.
   Verify the appendix boundary and equation/table/figure labels such as
   `A.1` against a rendered source sample.
   Do not add `\clearpage` from page appearance alone. An appendix-new-page
   probe is eligible only when appendix is the ordinary output's sole shifted
   semantic anchor and every pre-appendix anchor page already matches. Require
   the candidate to match page count and size, remove all shifts, improve
   structural flow and mean visual difference, and remain within the bounded
   appendix layout tolerance. Keep any rejected boundary out of the class.
   Before that check, test `\journalbackmatter` only when generated output is
   shorter and acknowledgements/data/references/appendix all shift together
   while every earlier anchor remains stable. Require repaired page count and
   size, no shifts or missing zones, and improved structural, mean-visual, and
   aggregate-layout scores. Keep the ordinary command continuous otherwise.

Do not chase pixel-perfect text differences before required structural zones are present.

For Word sources that use direct paragraph formatting rather than named styles,
verify the title, author, affiliation, abstract label, and first three heading
levels against the rendered source. A paragraph-level `w:pPr/w:rPr` font or
alignment is evidence even if its style is `Normal` or absent.

If PDF comparison tools are unavailable:

1. Deliver the package.
2. Save rerun commands in `README.md`.
3. List pending visual checks in `format_gap_log.md`.
4. When structured inspection was also unavailable, confirm the manual ledger
   has a source reference and explicit status for every applicable zone before
   handoff; tool absence never converts a missing zone into a passed check.

## Official-LaTeX Regression Check

Use this only when the user asks for official Word-vs-LaTeX comparison or when training the skill. The primary comparison is official LaTeX golden PDF vs Temp2TeX-generated PDF, both built with the same normalized manuscript body.

For Word-render fallback cases, use the same canonical stress content on both
sides. An offline local Word source may count as official provenance only when
the case manifest also records its official download URL and source-page URL.

Do not apply the 30-case regression requirement to ordinary conversion tasks.
