# Word Evidence To LaTeX

## Contents

- [Evidence Chain](#evidence-chain)
- [Units](#units)
- [Font Calibration](#font-calibration)
- [Role Mapping](#role-mapping)
- [Geometry Cautions](#geometry-cautions)
- [OMML Equations](#omml-equations)
- [Word Lists](#word-lists)
- [Table Header Evidence](#table-header-evidence)
- [Caption Evidence](#caption-evidence)
- [Sparse Template Styles](#sparse-template-styles)

Use this reference after inspecting an official DOCX, DOTX, DOTM, DOC, or DOT
template and before writing `template_spec.json` or `journal-template.cls`.

## Evidence Chain

For each visible role, resolve Word formatting in this order:

1. Direct paragraph or run properties on an actual sample paragraph.
2. The paragraph style's direct properties.
3. Its `based_on_style_id` chain.
4. `document_defaults`.
5. A documented Temp2TeX default only when the chain is incomplete.

Do not treat an unused built-in Word style as evidence. Do not select the most
frequent style without checking its sample paragraphs: bibliography, caption,
table-cell, list, and footer styles often dominate templates.

When creating a normalized Word reference for regression, use the selected
role style first. Copy direct paragraph/run properties only from a sample that
uses that same style ID. This keeps a template's Abstract or instruction
formatting from becoming the reference body style.

Reject misleading role-name matches. EndNote/bibliography/reference, footnote,
TOC, comment, annotation, and index styles can contain words such as `Title`
or `Author`, but are not manuscript front matter. Prefer an explicit
template-system role such as `MDPI_1.2_title` or a clean semantic style name.
For the article-title role, also reject `Table Title`, `Figure Title`,
`Caption`, `Equation`, and chart-title styles. In a sparse template, an unused
`Paper Title`, `Article Title`, or `Manuscript Title` style is stronger
evidence than a used table-title style; record it as
`template_style_candidate` until a populated source render is available.
When no semantic author style name exists, select a first-page author-like
paragraph only after excluding publication dates, received/accepted notices,
copyright text, correspondence lines, email addresses, abstracts, and
keywords. A comma alone is not author evidence: Word templates frequently use
it in date and publication metadata.

## Units

| Word evidence | Meaning | LaTeX decision |
| --- | --- | --- |
| `*_twips` | 1/1440 inch, 20 twips per point | Convert to `pt` or `mm`; retain the source value in the spec. |
| `size_half_points` | Half-points from `w:sz`, or source fallback `w:szCs` | Divide by 2 for the font size in pt. |
| `color` | Explicit Word RGB run/style colour | Map a six-digit non-black/non-white value to `\color[HTML]{...}` inside the role formatter; retain automatic/theme colours as evidence until resolved. |
| Word `PAGE` / `NUMPAGES` field | Current page / total page count in running furniture | Map to `\thepage` / `\pageref{LastPage}`; retain the field type rather than treating both as the current page. |
| `line_spacing_rule=auto` | 240 units is single spacing | Use `line / 240` as an initial `\linespread` value. |
| `line_spacing_rule=exact` | Exact baseline distance in twips | Map `twips / 20` to an initial physical LaTeX baseline; retain the Word metric and verify body density by render. |
| `line_spacing_rule=atLeast` | Minimum baseline distance in twips | For a visible title/author/affiliation/heading role, use `twips / 20` as an explicitly unverified initial role baseline; keep body-paragraph `atLeast` spacing on the conservative path until render comparison confirms it. |
| `first_line_twips` | First-line paragraph indent | Set `\parindent` when it applies to normal body paragraphs. |
| `hanging_twips` | Hanging indent | Preserve it as a `thebibliography` negative-`\itemindent` candidate relative to the reference continuation inset; enable only after PDF comparison verifies label width. Use it for references or list environments, not body `\parindent`. |

For active Word headers and footers, resolve inheritance by section and
variant (`default`, `first`, `even`) before mapping content. Absence of a
reference in a later `sectPr` normally means “inherit”, not “remove”. Preserve
explicit running-text size, bold, italic, and six-digit RGB colour inside the
corresponding `fancyhdr` slot. Keep automatic/theme colours unresolved, and
keep vertical edge-distance conversion behind rendered geometry calibration.

For adjacent front-matter roles, map one Word paragraph boundary to one LaTeX
vertical skip. Record both the preceding role's `space_after_twips` and the
following role's `space_before_twips`, resolve the boundary to their larger
nonnegative value, and emit it once. Do not add both values, since that doubles
one visible Word gap. Store paragraph indexes, both raw values, the resolved
point value, and source/default status in
`front_matter.spacing_boundaries`. Preserve generic inherited Normal-style
spacing as evidence, but do not let it override a role-specific default without
a rendered check.

For references, prefer an explicit visible label such as `[1]` or `1.` for a
numeric system. If unnumbered entries consistently begin with author names and
a parenthesized publication year, treat that as author-year evidence. A bare
decimal or a year somewhere later in an entry is not enough to infer either
system.

Map Word paragraph alignment semantically: `left`/`start` to left-ragged,
`right`/`end` to right-ragged, `center` to centred, and `both` to normal
LaTeX justification. `both` must not become `\raggedright`.

Map Word outline levels 0--4 to LaTeX `\section`, `\subsection`,
`\subsubsection`, `\paragraph`, and `\subparagraph`. Read the effective
format after the `basedOn` chain, not only direct style properties, for each
level's font, indentation, and before/after spacing. Use run-in paragraph
levels only as an editable default when the rendered source does not prove a
display heading.

For section counters, infer a Roman or alphabetic first-level profile only
when at least two visible, semantic Word heading roles use that label pattern.
Do not infer counters from a leading capital in a reference entry such as
`J. Smith`; a Heading style or Word outline level is required. Otherwise keep
the documented Arabic hierarchy and record it as a default.

Treat an observed `Appendix`, `Appendices`, `附录`, or `附錄` heading as a
document-boundary signal, rather than an ordinary body section. Emit the
class's `\journalappendix` interface once, then let later appendix content use
the appendix sectioning scheme. Do not reproduce the same boundary heading as
an earlier `\section`, or the output will contain two appendix starts. Keep
the original heading text and its evidence in `template_spec.json` and explain
any default appendix title in `format_gap_log.md`.

When Word contains a real TOC field, retain its field instruction. Parse an
`\o "1-3"` range as a source-backed LaTeX `tocdepth` of 3 before generating
`\tableofcontents`; do not infer a TOC merely because a paragraph says
“Contents”.

For `article` and `ctexart`, emit only `10pt`, `11pt`, or `12pt` class options.
Formatting a floating number as `11.0pt` is invalid and silently leaves LaTeX
at its default size. Apply 8--12pt nonstandard half-point sizes with an
explicit `\fontsize` setup after class loading.

## Font Calibration

A Word font name is source evidence, not proof that XeLaTeX will occupy the
same width, x-height, or baseline. Store it as `document.font_family` with
`font_family_mode: "evidence_only"`. The generator may attempt that named font
with `\IfFontExistsTF` and a compile-safe fallback when it is installed; keep
the mode as evidence-only until a render comparison supports a final fidelity
claim. Retain the original Word value even when the verified LaTeX choice is a
metric-compatible substitute.

When a role style has an explicit font baseline, do not merge a local run's
bold/italic/color override into the whole role. A short `Abstract` label or
`Correspondence` marker may be formatted differently from the paragraph body;
preserve that distinction in the evidence packet and class interface.

When no paragraph-level character properties exist, inspect every visible run
in the selected paragraph. Promote run typography to the paragraph role only
when all non-empty runs agree on the same font properties. If the label is bold
but the value is regular, keep the label local and do not make the entire
abstract, keyword line, affiliation, or caption bold. Store the uniform-run
decision in the source inventory so it can be audited.

## Role Mapping

| Word role/evidence | Put it in | LaTeX target |
| --- | --- | --- |
| Section page size, margins, columns, column gap | `journal-template.cls` | `geometry`, `twocolumn`, `\columnsep`, or a render-confirmed unequal-column candidate |
| Body font, alignment, line spacing, indent | `journal-template.cls` | font setup, `\linespread`, `\parindent`, explicit role `\parskip`, `\raggedright` only if source-backed |
| Title, authors, affiliations, dates, title-page spacing | `journal-template.cls` | metadata commands and `\maketitle` |
| Abstract and keyword styles | `journal-template.cls` | environments or class commands |
| Heading role, outline level, font/color/alignment, before/after spacing | `journal-template.cls` | `\titleformat` and `\titlespacing` |
| Table/figure width, object/caption document-flow adjacency, and caption examples | `journal-template.cls` and `main.tex` | float defaults, source-backed caption order, caption setup, table-note helpers |
| Reference style and hanging indent | `journal-template.cls` | bibliography/citation configuration |
| Appendix section and counter examples | `journal-template.cls` and `main.tex` | `\journalappendix`, section-bound equation/table/figure counters, appendix fixture |
| Example manuscript content | `main.tex` | calls to the class interface only |

Separate abstract structure from typography. A label-only Word paragraph such
as `Abstract` maps to a separate label role and the nearest adjacent content
paragraph maps to the content role. A delimiter form such as `Abstract:` plus
content, or an all-caps `ABSTRACT` label followed by content in the same
paragraph, supports an inline label. A content sentence beginning "Abstract
text..." and an indented abstract paragraph do not prove a label. When visible
content has no defensible label, use `label_mode: none`; do not invent one. The
class must redefine block, inline, and no-label abstract environments instead
of inheriting the base `article` abstract heading, quotation width, and skips.
Apply the same structure test inside borderless Word layout-table cells. A
visible label and adjacent content remain direct evidence there; table-cell
membership alone must not downgrade them to a no-label abstract.
Use the single boundary ledger for affiliation-to-abstract, optional
label-to-content, and abstract-to-keywords spacing.

Map keywords through their own role record, not through the abstract style.
The keyword line may have independent font weight, alignment, indents, and
before/after spacing. Keep its label and value in the same editable class
helper, but let a mixed-run label remain local when the value has no matching
format evidence.

Recognize `Keywords`, `Key words`, `Index Terms`, and `关键词` as keyword-role
labels. Preserve the visible label in `abstracts.keyword_label` and emit it in
the LaTeX helper; do not replace a source `Index Terms:` label with a generic
`Keywords:` string.

For body paragraphs, map only an explicit positive `space_after_twips` from a
non-table body role to `\parskip`. Keep template-style candidates and
table-cell body exemplars at zero until a rendered manuscript sample confirms
that their spacing belongs to ordinary flow text.

When a generic named `Normal`, `Body`, or `Body Text` style conflicts with at least two long
ordinary-flow paragraphs that share a stable effective font or paragraph
override, preserve the dominant visible body evidence and record the named
style conflict. Keep a publisher-specific style such as `Body Undented`
authoritative unless render evidence contradicts it. This prevents an unused
12pt style definition from replacing a consistently 10pt rendered manuscript
body without overriding an intentional journal role. Store the visible format
as a render-probe candidate; do not promote it into ordinary output solely from
XML frequency.

When a visible Word author exemplar is one paragraph, render multiple LaTeX
authors inline by treating `\and` as editable punctuation in `\maketitle`.
Use a tabular/multicolumn author layout only when the source evidence is
actually multi-cell, multi-paragraph, or otherwise lacks an inline exemplar.
Record the selected author sample text, the number of same-style author
paragraphs, and whether any sample is inside a table cell. A single flow
paragraph is evidence for inline layout; repeated same-style paragraphs or a
table-backed author block are evidence for stacked/tabular layout. The sample
does not by itself prove the exact LaTeX separator or line wrapping, so keep
that detail editable and render-verifiable.

For every selected Word table or drawing, first map its paragraph index to the
containing Word section. Compute that section's usable page width and local
column width, including explicit unequal `w:col` widths when available. In a
multi-column section, compare the object with the local column: a near-column
object maps to `\linewidth`; a smaller object maps to an editable local fraction
such as `0.681\linewidth`. Compare against the usable page width only after the
object clearly exceeds one local column. A source-backed spanning object uses
the explicit `journaltablewide` or `journalfigurewide` wrapper, implemented by
`table*` or `figure*` in a two-column class. If the object is in a one-column
section of an otherwise two-column document, or its width falls in an ambiguous
boundary band, keep `span_mode: uncertain`, use the local wrapper, and require a
rendered check. Do not infer universal column rules or vertical borders from a
single sample.

Retain table border evidence separately from width. A direct Word grid or a
`TableGrid` style is evidence for a grid-line example (`\hline` plus editable
vertical rules); do not replace it with `booktabs` by default. If the source
has no direct border evidence, use the conservative three-rule example and
record that the final table rule policy remains to be checked.

When a representative Word table exposes `grid_column_widths_twips`, expose
its ratios through `\journaltablerepresentativecolspec` using editable
`p{<ratio>\journaltablewidth}` columns. It is a representative helper, not a
required column specification for every table in the journal.

For a Word drawing with `width_emu` and `height_emu`, expose
`\journalfigurerepresentativewidth` as a fraction of its verified local
container width and `\journalfigurerepresentativeheight` in physical points. Preserve
inline versus anchored state in the spec. These are representative helpers:
use them after checking the drawing is a manuscript figure rather than a logo
or other page furniture.

Do not equate a Word drawing's inline versus anchored XML state with the
journal's universal LaTeX placement rule. Keep that state in the evidence
ledger and default `journalfigure` to an editable float wrapper, because it
preserves ordinary manuscript pagination. Use a non-floating default only when
a rendered official reference explicitly establishes that rule and the spec
records a separate `placement_calibration` with `mode: nonfloating` and
`status: render_verified`. Word inline/anchor state may create only a
`status: render_probe` candidate; it is not verification. Never use the legacy
`placement_mode` plus `placement_verified` shortcut.

### Float-to-text spacing

Do not derive float/text separation from a caption's object-facing or outside
side. Define the object block as the representative table/figure plus an
adjacent source-backed caption. Inspect the nearest visible Word paragraph on
each outer side. Classify the neighbor before using its spacing: captions,
object notes, headings, abstract/keyword roles, and reference roles do not
prove a float/text boundary. For an eligible body-text neighbor, retain both
raw paragraph sides and resolve the larger available value once. Store the
result under `page.float_spacing_evidence` with `mapping: candidate_only`.
Only a strict same-content render promotion may map it to
`page.float_spacing_calibration` and the LaTeX lengths `\textfloatsep`,
`\intextsep`, and `\dbltextfloatsep`.

For a visible Word footnote paragraph, map its font and line metric through
the class footnote formatter. Map `left_indent_twips` plus
`first_line_twips - hanging_twips` inside `\@makefntext` so continuation and
first lines retain the source relationship. Do not infer this from separator
nodes or footnote count alone.

For Word endnotes, ignore negative-ID separator and continuation nodes. A
non-negative endnote node is structural evidence only; enable an editable
endnote interface only when it contains a visible note paragraph with usable
formatting. Keep endnote placement and marker sequence as rendered-verification
work unless the source or author instructions make them explicit.

For references, treat a visible entry beginning with `[1]`, `1.`, or `1)` as
source-backed numeric-list evidence. Treat explicit author-date/author-year
guidance as author-year evidence. A standalone `et al.` occurrence, a year in
body prose, or a bibliography style name is not enough to choose an
author-year citation system; retain a documented default and gap when no
strong citation evidence exists.
Do not exclude a named `References` or `Bibliography` paragraph style when
extracting the reference-entry role itself. The same names are noise only when
selecting unrelated roles such as title or author.

## Geometry Cautions

- A body paragraph's left indent is not automatically a page margin. Compare it
  with title, table, and figure widths before changing `geometry`.
- Do not assume Word section one is the manuscript body. When a template has
  several section properties, select the most frequently repeated body frame;
  for a double-column manuscript, prefer repeated double-column sections over
  a single-column title section. Record its Word section index in
  `page.representative_section_index` and use that frame for margins, column
  gap, table width, and representative figure width.
- When Word's first section is explicitly single-column, or omits `w:cols`
  (the Word default) while a later representative body section explicitly
  records two columns, keep the front matter in a `\twocolumn[...]` title
  region and begin the body immediately after it. Do not infer a transition
  from a one-section document or when no later double-column body section
  exists.
  Do not apply the `twocolumn` class option globally, or call ordinary
  `\twocolumn` after confirmed single-column front matter: either choice
  forces the title/abstract into the wrong geometry or inserts a page break
  before the body.
- Resolve column count from the active Word section before consulting broad
  publisher-page prose. A page may mention retired, alternative, or
  peer-review-specific two-column templates while the supplied Word template
  is one column. Only use prose when the Word source has no usable section
  geometry and the wording is an explicit directive for the active manuscript;
  record that lower-confidence decision in the evidence ledger.
- When `w:cols` contains child `w:col` widths that differ, preserve the raw
  widths under `page.column_widths_twips` and mark ordinary equal-width
  `twocolumn` output as incomplete. The generated class may expose a
  `paracol` or equivalent candidate, but keep it render-confirmed because
  independent-column packages differ in float and page-flow behavior.
- When a paragraph contains `w:br type="column"`, preserve its paragraph
  index, role/style, text sample, and break type under
  `front_matter.column_break_evidence` or the relevant body evidence. Do not
  infer a section transition from this break alone.
- A table-cell paragraph style is not a body style, even when its font matches.
  The exception is a layout-table manuscript with no ordinary-flow body
  sample: a long, body-formatted cell paragraph may then be admitted as a
  `table_cell_body_exemplar` only after excluding instruction, caption, note,
  reference, and list content. Record the exception and verify its rendered
  container geometry; do not promote it to a universal table rule.
- A table-cell paragraph named `Table Title` can be a header cell, and generic
  prose beginning with `Figure 2` can be an instruction. Neither establishes
  external caption order. Match the selected table's first/last paragraph or a
  drawing paragraph to an external caption candidate, retain paragraph
  distance, and apply `above`/`below` only for adjacent/nearby evidence. Keep
  typography evidence even when attachment remains unresolved.
- Word templates can use text boxes, tables, or section breaks for front matter.
  Inspect page rendering before translating those offsets into margins.
- Treat Word/VML and DrawingML text-box text as non-flow evidence. Record its
  source part and visible text separately from manuscript paragraphs; do not
  turn it into a body heading, abstract, or title solely because its text is
  recognizable. Reconstruct its placement only after a rendered source page
  establishes whether it is cover furniture, title-page metadata, or repeating
  header/footer content. When available, also retain the shape width/height,
  page/margin/column-relative coordinate system, native offsets, wrap mode,
  z-order, and text insets. These fields identify a candidate but do not by
  themselves justify absolute placement. If rendering is unavailable, retain
  the editable class hook and record the placement as an unverified gap.
- Preserve page size and column mode before tuning font size, headings, or float
  placement. A page-count difference is usually an earlier-layer problem.
- Treat any Word margin above 40 mm, total vertical margins above 80 mm, or
  total horizontal margins above 70 mm as a render-check trigger. Preserve the
  source values initially, but record that they may represent a content box,
  title-page region, or renderer-specific section behavior rather than the
  final LaTeX geometry.

## Spec Evidence Record

## OMML Equations

Inspect `m:oMath` and `m:oMathPara` separately from ordinary Word runs. Record
the number of samples, whether each is display-like or inline-like, visible
number tokens such as `(1)`, and whether Word places the equation inside a
table cell. A number beside an equation is evidence for numbering, not by
itself proof of an exact LaTeX right-margin position.

Do not invent a mathematical LaTeX transcription from flattened OMML text.
Deliver an editable `journalequation` fixture backed by `amsmath`; use
`equation*` only when official evidence explicitly establishes unnumbered
display math. For unverified numbering or placement, preserve a numbered
editable default and record the rendered verification required. Appendix
equation counters remain a separate source/default decision.

## Word Lists

Treat a visible paragraph with `w:numPr` as a list item before applying any
textual heading heuristic. Also resolve `w:numPr` carried by the paragraph's
style in `word/styles.xml`; built-in `List Number` and `List Bullet` styles
commonly store numbering there instead of repeating it on every paragraph.
Read the resolved `numId` and `ilvl` against `word/numbering.xml` to record
bullet versus numeric format, level text, left indent, hanging indent, and
visible nesting levels. A list number such as `1.` is not heading evidence
unless the paragraph also has a semantic heading style or an outline level.

Expose `journalitemize` and `journalenumerate` as editable wrappers. Apply
the first visible indentation and label family only as a starting point; label
width, multi-level restart behavior, and exact nested spacing require a
same-content rendered comparison.

## Table Header Evidence

For a visible Word table, inspect its first row and row properties for
repeat-header status, row height, cell shading, vertical alignment, and
paragraph alignment/boldness. Prefer a small table with explicit header
formatting over a larger unformatted grid when selecting representative
table-style evidence.

Expose header color, typography, and a bounded row-height strut through named
LaTeX table-header helpers. Do not convert every table into a long table or
claim repeated headers, exact cell vertical alignment, or row-height behavior
without a rendered multi-page comparison.

## Caption Evidence

Prefer a visible caption paragraph that begins with a concrete label such as
Table 1, Fig. 1, Figure 2, or its Chinese equivalent over a generic Word
Caption style name. Keep table and figure evidence separate even when Word
reuses a style. Instructions such as “Tables should…” or “Figure captions…”
are not caption exemplars and must not drive caption typography.

When no concrete caption is visible, retain the named style as a template-style
candidate and log the missing rendered exemplar. Map only source-backed caption
font, alignment, position, and spacing to the LaTeX caption setup; float
placement still requires a same-content PDF comparison.

Keep caption outer spacing separate from the caption/object gap. When a caption
is above, the facing boundary is caption `space-after` against the drawing
paragraph `space-before`; when it is below, it is drawing paragraph
`space-after` against caption `space-before`. Resolve the larger available
value once, matching Word's adjacent-paragraph spacing behavior. Tables may not
have an external object paragraph, so use the caption's facing side when it is
source-backed. If order is default or neither facing side is available, record
the documented gap default. Never use a below caption's `space-after` as the
image-to-caption gap: that value is on the outside of the caption. Preserve it
separately as `outer_pt`. In the LaTeX `caption` package, map the internal
object gap to `aboveskip` and the outside caption side to `belowskip`; caption
positioning moves those logical skips to the correct physical sides.

For every source-derived setting, store the selected Word role, style ID, source
value, converted value, and confidence. Example:

```json
{
  "page": {
    "line_spacing": 1.17,
    "paragraph_indent": "21.2pt",
    "source_body_style": {
      "style_id": "MDPI31text",
      "source": "line_spacing=280 atLeast; first_line=425 twips",
      "confidence": "official-template"
    }
  }
}
```

If a conversion needs visual calibration, label the calibrated value `inferred`.
Never overwrite the original Word value or call the calibrated value official.
# Sparse Template Styles

When a publisher supplies an empty Word template, inspect its named paragraph
styles even if no article text uses them. Map explicitly semantic names such as
`Title`, `Author`, `Abstract`, `Keywords`, `Body Text`, `Heading 1`, and
`Caption` to their corresponding class roles, retaining the inherited effective
font and paragraph properties. Mark this mapping as
`template_style_candidate`; it is an official template rule candidate, not a
claim of pixel-verified rendering. Generic unused built-in styles remain weak
evidence and must not override an observed role.
