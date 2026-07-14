# Model Playbook

## Contents

- [Task Mode](#task-mode)
- [Evidence Priority](#evidence-priority)
- [Evidence Extraction](#evidence-extraction)
- [Word Style Semantics](#word-style-semantics)
- [Header, Footer, and Asset Evidence](#header-footer-and-asset-evidence)
- [Template File Identity](#template-file-identity)
- [Layout Reconstruction Order](#layout-reconstruction-order)
- [Content-Box Decisions](#content-box-decisions)
- [Defaults and Missing Evidence](#defaults-and-missing-evidence)
- [Chinese And Mixed-Language Evidence](#chinese-and-mixed-language-evidence)
- [Stop or Continue](#stop-or-continue)
- [Scope Control](#scope-control)

Use this playbook after Temp2TeX loads. The goal is to help an LLM agent decide what to do, what evidence is strong enough, and when to deliver a package with documented gaps.

## Task Mode

Classify the task before doing work:

1. **Ordinary conversion**: the user wants an official Word/PDF/web template rebuilt as LaTeX. Deliver the LaTeX package. Do not run the 30-case corpus.
2. **Official Word-vs-LaTeX comparison**: the user provides or requests both official Word/DOCX and official LaTeX templates for the same template system. Use regression-style PDF comparison after generating the package.
3. **Skill training**: the user asks to improve Temp2TeX itself from cases or benchmarks. Use affected cases, representative batches, and then the fixed manifests when script behavior changed.

If the user did not explicitly ask for official LaTeX comparison or skill training, assume ordinary conversion.

## Evidence Priority

Use sources in this order:

1. Official journal or publisher DOC/DOCX template.
2. Official journal author instructions page.
3. Official publisher template package, artwork rules, table rules, reference rules, and submission checklist.
4. Official filled sample article or PDF sample.
5. Recent published articles from the journal as weak evidence.
6. Defaults from `format-defaults.md`.

Record source URLs, local paths, file hashes when available, and access date. Do not use third-party template mirrors as official evidence unless the user explicitly accepts weaker evidence.

## Evidence Extraction

Before extracting individual properties, create the zone-by-zone evidence
packet described in `reconstruction-protocol.md`. A property from a blank
placeholder or unused Word style is only a candidate; it becomes a source rule
only when a used semantic role or a rendered page supports it.

Extract these decisions before writing LaTeX:

- Page setup: paper size, margin box, column count, column gap, header/footer, page numbering. Inspect every Word section in order: omitted `w:cols` is Word's one-column default. When that first section is followed by an explicit double-column manuscript-body section, make the title/front matter full width and begin the body with a `\twocolumn[...]` transition; do not apply two columns globally from page one. Also inspect child `w:col` widths and paragraph-level `w:br type="column"` elements. Unequal widths or explicit breaks are separate evidence; do not flatten them into ordinary equal-width `twocolumn` output.
- Page-style assets: header/footer text, rules, logos, issue metadata, page
  numbers, and first-page exceptions. Extract embedded Word media before
  recreating these elements. Map only the header/footer parts referenced by
  the active Word section, resolving a missing later-section reference as
  inheritance of the latest reference for that variant rather than absence;
  convert a genuine `PAGE` field to a page-number
  macro, but preserve literal template sample numbers as editable text.
  Preserve explicit running-text size, bold/italic state, and RGB colour in
  the slot formatter.
  Retain image assets by default and apply them only after PDF comparison
  confirms their rendered position.
- Font model: family, base size, line spacing, paragraph indentation, paragraph spacing.
- Front matter: cover/title page, running title, author order, affiliations, corresponding author, author notes, received/revised/accepted dates.
- Abstracts and keywords: placement, labels, indentation, bold/italic rules, bilingual variants.
- Contents: whether a table of contents is required or merely present in a template.
- Headings: level count, numbering, punctuation, casing, spacing, run-in behavior.
- Body: paragraph style, lists, equations, theorem-like blocks if present.
- Tables: caption placement, rules, width behavior, notes, merged or wide examples.
- Figures: caption placement, subfigure behavior, artwork size, file format rules.
- Footnotes and endnotes: markers, placement, author-footnote behavior.
- References: bibliography style, citation style, heading text, hanging indent.
- Appendices: heading style, appendix boundary, and equation/table/figure
  numbering reset.
- Language: English-only, Chinese-only, or bilingual/CJK needs.

When local inspection tools are unavailable, infer from the visible document text, screenshots, PDF pages, and official instructions. Mark uncertain values as inferred.

## Word Style Semantics

Treat Word paragraph styles as evidence about semantic roles, not merely as a list
of fonts. Before mapping a style to LaTeX, inspect representative paragraphs that
actually use it.

1. Map title, author, affiliation, abstract, keywords, body, each heading level,
   captions, references, and footnotes separately.
2. Prefer a journal-defined style used in article paragraphs over an unused built-in
   Word style with a similar name. For example, a template may use `Head1` and
   `Para` rather than Word's built-in `Heading 1` and `Normal`.
3. Compare a generic named style such as `Normal` or `Body Text` with long
   ordinary-flow paragraphs. If at least two such paragraphs share a stable
   effective font or paragraph override that conflicts with it, record the
   dominant visible evidence as a render candidate. Keep the named style in
   ordinary output until same-content comparison promotes it. Keep a
   publisher-specific style such as `Body Undented` authoritative unless
   stronger render evidence contradicts it.
4. Never infer the body style from raw frequency alone. Reference entries, lists,
   captions, tables, figure descriptions, acknowledgements, headers, and footnotes
   often occur more often than normal prose in a template sample.
5. Keep bibliography and body mapping distinct even when both use the same font.
6. When a visible heading exemplar lacks an explicit Word size, inspect the
   next few official template paragraphs for role-specific instructions such
   as `Headings are 10pt`, `Subheads are 9 pt`, or `Tertiary heads are 8pt`.
   Attach the size only to the matching heading level and retain the sentence,
   paragraph index, and source. Do not use an unrelated sentence containing a
   point value, override an explicit style size, or infer spacing from a size
   instruction.
   Their indentation, spacing, numbering, and page-break behavior frequently differ.
7. When a style role is ambiguous, record the candidates and reason in
   `template_spec.json`; do not silently turn a bibliography or caption style into
   body text.

7. Treat a publisher prefix as a tie-breaker, never as role evidence. A style
   named `MDPI_1.6_affiliation` is not a title, abstract, or caption style just
   because it belongs to the same template family. If no role-matching style or
   visible exemplar exists, record `evidence_status: default` and keep the
   documented fallback in `format_gap_log.md`.

8. Inspect run-level typography before treating a direct paragraph sample as a
   role-wide font rule. Promote it only when all non-empty runs agree. A mixed
   `Abstract:` or `Keywords:` label is local formatting, while a uniformly
   formatted keyword line is valid keyword-role evidence. Keep abstract and
   keyword records separate even when both use `Normal`.

9. Recognize `Keywords`, `Key words`, `Index Terms`, and `关键词` as the same
   semantic keyword role, but retain the source label text in the spec and
   generated class. Semantic normalization must not rewrite the journal's
   visible label.

For source-derived manuscript scaffolds, preserve the Word paragraph outline
level (or an explicit `Heading n` style) separately from title text. Map levels
0--4 to section through subparagraph in `main.tex`. Exclude title, author,
affiliation, abstract, and keyword front-matter roles even if their Word
paragraph happens to carry an outline level.

Also exclude bibliography/reference/citation, caption, equation, table, figure,
and footnote styles from the heading scaffold. A bare leading letter or number
is weak evidence: reference entries such as `J. Smith` and conversion-table
rows such as `1 Mx` are not headings. Accept alphabetic numbering only when
Word explicitly supplies a heading/outline role.

When `source_inventory.json` contains OOXML metrics, read a style's direct
format, then its `based_on_style_id`, then `document_defaults`. A missing direct
font size or indentation is not permission to use a journal default before this
inheritance chain has been checked.

Use the recovered semantic map to decide what belongs in `journal-template.cls`:
page frame and role-level formatting belong in the class, while `main.tex` should
only demonstrate the mapped content roles.

## Header, Footer, and Asset Evidence

Treat Word header/footer XML parts and their embedded images as template
evidence, not decorative leftovers.

1. Record every header/footer part, its visible text, and its image
   relationships in `source_inventory.json`.
2. Extract original Word media into the output package's `assets/` directory
   using the asset manifest. Preserve original filenames/roles in the manifest.
   When an asset is EMF or WMF, retain the original as evidence but use the
   manifest's converted `latex_output` PNG only when conversion succeeded.
3. Rebuild header and footer behavior in `journal-template.cls` with editable
   commands such as `\journalheaderleft{...}` and `\journalfooterright{...}`.
   Keep asset placement, dimensions, and first-page exceptions in the class.
4. Read every tokenized paragraph in an active Word header/footer part. Running
   text and a `PAGE`/`NUMPAGES` field may occupy separate paragraphs; map them
   to editable left/centre/right commands without assuming the first paragraph
   is meaningful. Pure text/page-field furniture and deterministic rules may
   be enabled directly on each safe active part; one unsafe logo or text-box
   variant must not disable an unrelated safe running-text variant. Keep
   first-page drawings and image placement as separately confirmed candidates.
5. Do not invent a generic running head when the source has custom or
   image-based page furniture. Preserve source-backed text/rules when they are
   deterministic, but leave image placement pending in `format_gap_log.md` and
   generate an explicit candidate for PDF comparison. Keep the candidate only
   when it improves the same comparison target; reject it when an official
   LaTeX golden intentionally differs from Word submission furniture.
6. Treat XML relationship order, Word table-cell order, and raw drawing
   alignment as placement candidates, not final proof. Word and LibreOffice can
   resolve first-page, mirrored, or right-to-left headers differently. Enable a
   candidate placement only after checking the rendered reference page.

7. When active header/footer parts change across Word sections, keep the
   section identity and part names in a commented `page-furniture.tex`
   candidate. Do not collapse a later section's running text into a global
   page style unless the manuscript boundary and same-content PDF comparison
   confirm that it is globally applicable.

For tables, record grid widths, fixed/autofit mode, alignment, and merged
cells from a representative source table, then expose editable table helpers
in the class. For figures, retain body drawing dimensions and inline/anchor
state, copy the original media into `assets/`, and expose editable figure
helpers. Do not convert a sample table or image dimension into a universal
rule until rendering supports it.

Decide object span from the object's local Word section, not from document-wide
column mode or page width alone. Attach a section index to each selected table,
drawing, and caption candidate. In a multi-column section, compare object width
with the actual local column width; near-column objects remain ordinary
`journaltable`/`journalfigure` content and use local `\linewidth`. Promote only
a clearly wider, source-backed object to `journaltablewide`/`journalfigurewide`.
An object in a one-column title/front-matter section of a two-column document is
ambiguous for body span semantics and must remain editable and unverified until
the rendered page confirms its role. Do not let one wide exemplar make appendix
or unrelated manuscript objects wide.

Treat float/text spacing as a boundary around the complete object/caption
block, not as caption spacing. For each representative object, inspect the
nearest paragraph before the block and after the block. Use a boundary only
when that outside paragraph is body-text-like. Another caption, table or figure
note, heading, abstract, keyword, reference entry, or bibliography role is not
float/text evidence. Resolve each eligible Word boundary as the larger
available adjacent paragraph side and emit it once. Aggregate eligible values
as evidence only; Word flow does not identify which LaTeX output-routine length
(`textfloatsep`, `intextsep`, or `dbltextfloatsep`) should own it. Test the
shared mapping as a separate render probe and retain ordinary LaTeX defaults
until strict promotion succeeds.

For references, keep the Word entry style separate from the bibliography
backend: source font can be mapped directly, while fixed left indent, item
spacing, and a negative `\itemindent` derived from Word hanging indentation
are same-content candidates for the standard `thebibliography` path. Final
label width and late-page flow must be calibrated by render before those list
geometry settings are enabled. For appendices,
keep the manuscript order as statements/declarations, references, then
appendices unless official evidence explicitly requires another order. Expose
`\journalbackmatter` before the first acknowledgement/declaration and keep it
continuous by default. If generated output is shorter and only
acknowledgements, data availability, references, and appendix anchors move
together to an earlier page, test one new-page backmatter boundary. Promote it
only when it repairs page count and size, removes every shift, preserves zones,
and improves structural flow, mean visual difference, and total layout. Do not
use it when body/table/figure anchors also move or generated output is longer.
For appendices,
use a named class command rather than a bare `\appendix` so source-required
equation, table, and figure numbering remains editable and consistent. Bind
each of those counters to the appendix section, then compile a fixture with at
least two appendix sections to confirm `A.1` and `B.1` restart behavior.
Do not infer an appendix page break merely because the rendered Word appendix
happens to start on a new page. Keep `\journalappendix` continuous by default.
Test a separate new-page boundary only when a same-content comparison has the
wrong page count, every title-through-reference anchor remains on the correct
page, and appendix is the sole shifted anchor. Promote it only if the candidate
matches page count and size, removes all shifts and missing zones, improves the
structural-flow diagnostic and mean visual difference, and keeps total layout
penalty within the appendix-boundary tolerance. A reference shift or any other
pre-appendix shift rejects this candidate even when it adds the missing page.

Treat Word `titlePg`, a first-page header/footer part, or a different first
section as a cover/title-page candidate only. Inspect the rendered first page
before inserting a standalone cover. The class should expose a separate cover
environment so the final choice remains editable.

Detect Word TOC fields through `instrText` or `fldSimple` rather than merely
matching the word Contents. When a real field is found, enable a generated TOC
and compile twice; otherwise record a heading-only candidate for rendered
verification.

## Template File Identity

Do not trust a download URL or filename suffix to identify a Word artifact.
Publishers frequently serve an OpenXML template through a legacy `.dot` URL, a
generic download endpoint, or `application/octet-stream`.

1. Validate the downloaded bytes before inspecting or converting them.
2. Inspect the OpenXML content type: distinguish document packages (`.docx`) from
   template packages (`.dotx`/`.dotm`).
3. Preserve the detected type in the source inventory and hash record. Convert a
   legacy template to a temporary `.docx` only for inspection, rendering, or
   asset extraction; retain the original template as evidence. The asset manifest
   must identify that LibreOffice conversion was used rather than claiming the
   legacy binary was directly parsed as OpenXML.
4. Treat HTML challenge pages, login pages, and mislabeled payloads as failed
   sources, not as documents that happened to have a Word-like filename.

## Layout Reconstruction Order

Rebuild visible layout from the outside in. This order prevents a locally neat
title block from hiding a wrong page frame or an extra page later in the body.

1. Set paper size, orientation, text block, margins, columns, column gap, and
   header/footer occupancy in `journal-template.cls`. Read the Word section
   dimensions first: when they are not a standard LaTeX page size, preserve
   the exact width and height with `paperwidth` and `paperheight` rather than
   approximating them as A4 or Letter.
   Distinguish page margins from an indentation applied by the body paragraph
   style: the latter changes the body box without necessarily changing title,
   table, or figure width.
2. Match base font family, font size, line spacing, paragraph indentation, and
   paragraph spacing. Check page count before tuning smaller details.
   For title, author, affiliation, and abstract boundaries, use the next
   role's explicit Word `space_before` in preference to the preceding role's
   `space_after`; map only one of them to the LaTeX skip. This preserves the
    Word boundary without double-counting spacing from two paragraph records.
    For ordinary body paragraphs, resolve one Word paragraph boundary as
    `max(space_before, space_after)` and never add both sides. Scope the resulting
    `\parskip` to the class body environment so title, abstract, keywords,
    references, and appendix controls do not inherit it. Because Word and TeX
    paragraph flow differ, keep ordinary generation conservative. When a page
    count mismatch remains and the body evidence is at least 6pt, test only
    bounded 0.5, 0.75, and 1.0 multiples as isolated render probes. Promote one
    only when it matches the complete reference page count and page size,
    preserves every required zone, removes anchor page shifts, improves layout,
    and satisfies the strict pixel tolerances. Otherwise retain the Word value as
    unresolved evidence rather than forcing it into the class.
    Keep the Word value as source evidence. If PDF comparison shows a stable
   renderer/metric mismatch, record a separate `render_calibration` with a
   measured reference body size and enable it only after the calibrated package
   improves the layered comparison.
   Treat Word `exact` line spacing as an initial physical baseline value, not
   as proof of a LaTeX `\linespread` multiplier. Keep the original paragraph
   metric in the evidence ledger and confirm the mapped baseline with a
   rendered same-content comparison. Treat Word `auto` spacing as a relative
   initial `\linespread` only: Word and TeX font metrics are not interchangeable.
   For `atLeast`, record a density gap until rendering establishes a stable
   baseline instead of applying a global ratio blindly.
   A normal body-density render probe is allowed only after page count, page
   size, body-box width, and document anchor pages are stable. One narrower
   page-count-repair probe is allowed when the generated PDF has more pages,
   at least two pages are comparable, every measured anchor shifts later, the
   body-box width delta is no more than 30pt, and the generated body font is
   stably at least 1pt larger than the reference. In that case derive one
   bounded smaller-font/compact-baseline candidate; do not search a grid.
   Reject the mode when output is too short, shifts are mixed, font excess is
   absent or unstable, or geometry is farther apart. Measure same-column
   baseline steps rather than relying only on whitespace between adjacent PDF
   lines, because multi-column extraction and paragraph boundaries distort the
   latter. Keep font-size and baseline changes bounded, materialize a separate
   candidate spec, and compare it against both the reference PDF and ordinary
   package. A normal candidate must preserve page count. A page-count-repair
   candidate must match the reference page count and size, remove every anchor
   shift, preserve all zones, improve body-density and total layout scores,
   keep pixel deterioration within repair tolerances, and not worsen any
   pre-existing body-box width mismatch.
   Compilation alone is never promotion evidence. Preserve the Word font and
   line metrics in their original fields even when a render-verified layer wins.
   Use only unique same-content phrases for PDF anchors. The bundled profiler's
   default phrases belong to the fixed regression manuscript. For another
   manuscript, create an `anchors.json` map for its title, abstract, keywords,
   main sections, table, figure, references, and appendix. Reject broad labels
   that can occur in prose, and never compare diagnostics with different
   `anchor_profile_version` values.
   Promote a page/body/placement/float-spacing probe through the strict promotion gate rather than by
   editing `status` manually. The candidate may differ from the source spec only
   under `page.render_calibration`, `document.render_calibration`,
   `page.float_spacing_calibration`, or exactly one figure/table
   `layout_evidence.placement_calibration`. Word inline or
   table-flow evidence may propose `mode: nonfloating`, but only as
   `status: render_probe`; it never proves the LaTeX float policy. Require the
   same reference PDF, successful compilation, stable page count and page size,
   no new anchor-page or missing-anchor failures, a meaningful reduction in mean
   visual diff, and non-worse maximum-page diff and layout penalty. For placement,
   also require a non-worse table/figure/caption/float diagnostic score. A rejected
   probe leaves the ordinary package unchanged. Keep detailed absolute audit
   paths in `promotion_report.json`; the promoted spec stores portable evidence
   names and hashes.
   Map explicit Word centre/right heading alignment into the corresponding
   `\titleformat` declaration. Preserve a concrete Word heading colour as
   evidence and enable it only when a same-content colour candidate improves
   PDF comparison: instructional template colours can disappear from actual
   manuscript headings. Do not infer decorative colour from a theme or
   screenshot; retain ordinary black when no verified rule is available.
   For a measured page-frame mismatch, store only the winning values in
   `page.render_calibration` with `status: render_verified`, the reference and
   generated PDF paths, and the before/after metrics. That layer may override
   `margins_mm` and `column_sep_mm` for class generation, but it must never
   overwrite the original Word section evidence or be enabled merely because a
   diagnostic variant compiled.
3. Rebuild the title, author, affiliation, abstract, and keyword blocks using
   their actual Word style roles and first-page spacing.
   An absent Word `jc` on a source-backed role means Word's left-aligned
   paragraph default, not an invitation to centre the block. Use centring only
   when `jc=center` is present or the role is a documented fallback.
   Treat abstract structure as document-flow evidence. A paragraph containing
   only `Abstract`/`摘要` is a separate label; attach the nearest adjacent
   content paragraph without merging their typography. A paragraph with a
   visible delimiter such as `Abstract:` plus content, or an all-caps label run
   plus content, supports an inline label. A content paragraph whose prose
   merely begins with the word "Abstract", or a paragraph with only an indent,
   does not. Preserve a source-backed no-label abstract without inventing a
   heading. The generated class must own all three layouts instead of inheriting
   `article`'s quotation width and vertical skips.
   Include visible paragraphs inside borderless layout-table cells in this
   decision. Many publisher Word templates implement the entire title and
   abstract area as a table; cell membership is not evidence that a visible
   `Abstract` label should be ignored.
   Build a spacing ledger for title-to-author, author-to-affiliation,
   affiliation-to-abstract, optional abstract-label-to-content, and
   abstract-to-keywords. Word resolves an adjacent boundary from both
   paragraphs; store the larger of previous space-after and next space-before
   and emit that value once. Do not also leave role-local skips at the same
   boundary.
4. Rebuild heading numbering, spacing, and run-in behavior; then check body
   density again because headings change pagination.
5. Rebuild table and figure width rules, float placement, captions, notes, and
   continued-float behavior. Do not solve a float mismatch by changing margins.
   Locate each selected object in its Word section before computing width. Use
   local column width for ordinary floats and usable page width only for a
   source-backed spanning object. Never divide a column-sized Word object by
   full-page width and then apply that fraction to LaTeX `\linewidth`; that
   halves correctly sized figures in two-column output.
   Treat caption typography and caption attachment as separate decisions.
   Record table first/last paragraph indexes and drawing paragraph indexes,
   then match only external caption candidates with a visible label or semantic
   caption style. An adjacent or nearby relation may establish `above`/`below`;
   text inside a table cell, distant prose, or an instructional sentence in a
   generic style cannot. Prefer a caption-attached representative object when
   choosing among layout tables and manuscript tables. If the relation remains
   ambiguous, use the documented table-above/figure-below default and expose it
   in the gap log rather than inventing a publisher rule.
   After order is source-backed, resolve the caption/object boundary like any
   adjacent Word paragraph boundary. For an above caption, compare caption
   space-after with the object's paragraph space-before. For a below caption,
   compare object paragraph space-after with caption space-before. Store both
   raw sides and emit the maximum once through the class caption setup. A
   caption's outside side is not a fallback for a missing object-facing side;
   use the documented gap default when order or both facing sides are absent.
   Store the caption's opposite outside side independently. Map the internal
   boundary to caption `aboveskip` and the outside side to `belowskip`; the
   `caption` package swaps their physical placement for top captions.
6. Match footnotes, running headers, footers, page numbers, references, and
   appendices after the main page flow is stable.

When a render comparison fails, diagnose the earliest failing layer first. Keep
the chosen values and their evidence in `template_spec.json`; do not hide a
page-count or page-size mismatch by relaxing a visual threshold.

Treat generic layout variants as diagnostic probes, not as template defaults.
If a compact, alternate page-style, or heading-label profile only makes a small
visual improvement, return to the Word evidence: section geometry, actual style
metrics, front-matter paragraphs, and float examples. Do not select a generic
profile merely because it produces the lowest image-diff score for one journal.

## Content-Box Decisions

Word's page margins and its role-specific paragraph indents are separate
evidence. Preserve both before deciding whether LaTeX needs a narrower content
box.

1. Record the physical page frame from `sectPr` independently from left/right
   indents on body, abstract, heading, caption, and reference styles.
2. Never turn a body style's left indent into a global `geometry` margin by
   default. First check whether the same inset is used by the title, abstract,
   headings, figures, and tables in the rendered source.
3. If only normal prose and headings share an inset, implement a named class
   environment or class-level paragraph block for that body box. Leave floats
   full-width unless their own evidence says otherwise.
4. If abstract or keyword styles have a different inset, define their
   environments separately. Do not approximate them with `\hspace` in
   `main.tex`.
5. Apply a content-box rule only when direct OOXML evidence and the rendered
   page agree. Otherwise keep it as `inferred` or `unsupported` in the evidence
   ledger and state the pending visual check.

When page count differs, compare body-box width and font size before adjusting
top skips or float placement. A wrong content box changes line wrapping across
the entire document; local spacing tweaks cannot repair that reliably.

## Defaults and Missing Evidence

Use defaults only after official evidence is missing or contradictory:

- English default: `xelatex` or `pdflatex` compatible article-like formatting, conservative margins, clear heading hierarchy, standard abstract/keywords/references.
- Chinese default: XeLaTeX with CJK-safe font setup, Chinese abstract/keywords labels when needed, and UTF-8 source.
- Mixed-language default: XeLaTeX, English and CJK text support, bilingual metadata fields only when the source requires them.

Every default must appear in `template_spec.json` with a reason and in `format_gap_log.md` if it affects visible formatting.

## Chinese And Mixed-Language Evidence

Use XeLaTeX and a CJK-safe class whenever visible source text contains Chinese.
Record the Latin font family and the Word East Asian font family separately in
`template_spec.json`; they are different pieces of evidence and are not
interchangeable. A paragraph that inherits Word `Normal` without an explicit
`w:pStyle` is still body-style evidence and must not be discarded as unstyled.
Classify `zh` or `mixed` from visible characters, rather than from an East
Asian font field alone.

For `zh` or `mixed` output, use `ctexart` with the source body point size when
available. Enable a named Word CJK font only when it exists locally and a
rendered comparison supports it. Otherwise retain the CTeX fallback chain and
record the Word family as evidence-only. For Chinese-first templates, use
Chinese abstract and keyword labels unless official evidence specifies a
different bilingual order.

When the source visibly contains both Chinese and English title-page metadata,
ship editable bilingual front-matter fields in `main.tex`; do not collapse the
template to one language. Keep bilingual title, author, affiliation, abstract,
and keyword layout in `journal-template.cls`, and follow the source order when
it is known.

Treat Chinese and English abstract samples as separate evidence fields. In a
Chinese-first mixed template, the Chinese `摘要` sample supplies the primary
abstract and the `Abstract` sample supplies the English abstract; neither
heading belongs in the numbered manuscript body. If the source order is not
visible, keep both editable fields, choose the documented Chinese-first default,
and record that order as a default rather than an official requirement.

Treat a Word template's example prose as formatting evidence, not manuscript
content. `main.tex` may preserve a source-backed heading hierarchy, but must
not copy title-page samples, abstract instructions, keyword examples, figure or
table instructions, or bibliography samples into the editable manuscript body.

Do not assume every official DOCX exposes meaningful Word style names. Some
publisher templates place the effective font, size, alignment, and spacing in
paragraph-level `w:pPr/w:rPr` properties. When that happens, extract those
properties as direct role evidence using visible labels and first-page order:
title, author, affiliation, `摘要`/`Abstract`, `关键词`/`Keywords`, then numbered
body headings. Keep numbered affiliations out of the heading tree. A source
paragraph beginning `摘要：` or `Abstract:` is evidence for a left-aligned
inline-label abstract, not the generic centered abstract environment.

For direct-format templates, do not select the longest paragraph as the body
style. Exclude title-page metadata, abstracts, captions, and references; use
the first credible manuscript heading and the reference-heading boundary to
scope body candidates, then choose the most frequently used direct-format
signature inside that body region.

Treat table-cell text as table evidence by default, even when it is long or
begins with a number. A cell can contain a submission instruction, a cover
layout block, a conversion matrix, or a formatted example; it is not body or
heading evidence unless Word also assigns a semantic heading/outline role.
Keep table-cell text available for front-matter and table reconstruction, but
exclude it from body-baseline selection and from textual heading fallbacks.
If the document has no credible ordinary-flow body exemplar, re-admit only
long, body-formatted table-cell paragraphs that are not captions, labels,
instructions, notes, references, or list items. Mark that decision as a
table-cell body exemplar and keep the container as an explicit verification
gap; never let a table cell win merely because it is the longest paragraph.

For author blocks, preserve sample cardinality as well as sample text. One
same-style author paragraph in normal flow supports inline rendering; repeated
same-style paragraphs or a table-cell author block supports stacked/tabular
rendering. Treat the punctuation used between LaTeX `\author` entries as a
separate editable/render-verification decision.

## Stop or Continue

Continue and deliver the package when:

- Official evidence is incomplete but enough exists to choose reasonable defaults.
- Word, LibreOffice, TeX, or PDF comparison tools are unavailable.
- Official LaTeX is absent in an ordinary conversion task.

Stop and ask or declare a blocker when:

- No official source or user-provided template exists.
- The task requires exact reproduction, but the only available source is inaccessible or encrypted.
- The user asks for official-LaTeX regression and one side has no official source after reasonable search.
- Licensing or access prevents using the template files.

## Scope Control

Do not expand scope silently. A single-journal conversion should end with a LaTeX package and verification plan. A benchmark should end with case reports and comparison artifacts. Skill training should modify the skill or scripts and rerun the appropriate regression surface.
