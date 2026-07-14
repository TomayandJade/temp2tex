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
- `format_gap_log.md`
- `README.md`

Run `validate_latex_package.py` when available. Treat a contract failure as a
handoff blocker; treat its warnings as items to resolve or document. The check
does not prove PDF fidelity, so retain the compile and visual stages below.

Also check:

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
- If active Word header/footer parts differ by section, confirm
  `page-furniture.tex` records each section and active part as a commented
  editable candidate. Do not replace the ordinary global page style with a
  section candidate until the corresponding manuscript boundary and rendered
  reference are confirmed.
- `README.md` lists compile command, required engine, optional render comparison command, and known gaps.
- `template_spec.json` and `format_gap_log.md` agree on defaults and missing evidence.
- `main.tex` exercises each applicable module with real, compileable content: title/authors, abstract/keywords, headings/body, at least one table, figure, equation, footnote, bibliography citation/reference, and appendix. Class commands or empty placeholders do not count as coverage.
- Confirm `main.tex` orders declarations/statements, references, then appendix; a bibliography fixture after `\journalappendix` is a hard package error.
- For `zh` or `mixed` sources, retain Word Latin and East Asian fonts separately.
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
  the named style in ordinary output and compare the explicit body-style probe
  before enabling `render_mode: visible_flow_exemplar`. Reject it when page
  count, required zones, or layout penalty worsens even if its mean pixel diff
  is smaller.
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
3. Record fatal errors, missing packages, missing figures, bibliography warnings, overfull boxes that affect layout, and output PDF path.
4. Fix fatal errors before delivery.

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
   into the final class.
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
   final LaTeX position remains pending.
   Confirm an unverified non-floating option is stored only as
   `placement_calibration.status: render_probe` and leaves the generated class
   floating. Promote exactly one placement path at a time; require the same
   reference, successful compile, stable geometry and anchors, lower mean diff,
   non-worse maximum/layout metrics, and a non-worse float diagnostic score.
   Only the resulting `render_verified` acceptance may activate non-floating
   `journalfigure` or `journaltable` output.
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

## Official-LaTeX Regression Check

Use this only when the user asks for official Word-vs-LaTeX comparison or when training the skill. The primary comparison is official LaTeX golden PDF vs Temp2TeX-generated PDF, both built with the same normalized manuscript body.

For Word-render fallback cases, use the same canonical stress content on both
sides. An offline local Word source may count as official provenance only when
the case manifest also records its official download URL and source-page URL.

Do not apply the 30-case regression requirement to ordinary conversion tasks.
