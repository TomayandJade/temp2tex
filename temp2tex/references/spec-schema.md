# Template Spec Schema

## Contents

- [Minimal Shape](#minimal-shape)
- [Required Decisions](#required-decisions)
- [Fallback Entry](#fallback-entry)
- [Area Checklist](#area-checklist)

`template_spec.json` is the bridge between source evidence and LaTeX generation. Keep it explicit and compact.

## Minimal Shape

```json
{
  "journal": {
    "name": "Journal Name",
    "publisher": "Publisher",
    "source_urls": [],
    "language": "en"
  },
  "document": {
    "paper": "a4paper",
    "paper_dimensions_mm": null,
    "columns": "single",
    "font_size_pt": 12,
    "render_calibration": {
      "status": "not_run",
      "reference_body_font_size_pt": null,
      "calibrated_font_size_pt": null,
      "source_body_baseline_pt": null,
      "body_baseline_pt": null,
      "before_metrics": {},
      "after_metrics": {},
      "evidence": ""
    },
    "font_family": null,
    "font_family_mode": "evidence_only",
    "cjk_font_family": null,
    "cjk_font_mode": "default",
    "engine": "xelatex",
    "class_strategy": "cls"
  },
  "page": {
    "margins_mm": {"top": 25, "right": 25, "bottom": 25, "left": 25},
    "header_distance_mm": null,
    "footer_distance_mm": null,
    "gutter_mm": null,
    "mirror_margins": false,
    "line_spacing": 1.15,
    "paragraph_indent": "1.5em",
    "column_sep_mm": null,
    "representative_section_index": null,
    "representative_section_source": "",
    "render_calibration": {
      "status": "pending",
      "margins_mm": null,
      "column_sep_mm": null,
      "source": ""
    },
    "header_footer_profile": "fancy-running-head",
    "source_body_style": {
      "evidence_status": "named_style_with_visible_flow_conflict",
      "visible_flow_override_candidate": {},
      "render_mode": ""
    },
    "header_footer_evidence": {},
    "header_footer_auto_apply": false
  },
  "front_matter": {
    "title": true,
    "authors": true,
    "affiliations": true,
    "corresponding_author": true,
    "author_layout": "tabular",
    "body_column_transition_after_front_matter": false,
    "highlights": false,
    "highlights_guidance": [],
    "graphical_abstract": false,
    "cover_mode": "not_detected",
    "cover_evidence": {},
    "title_style": {},
    "author_style": {},
    "affiliation_style": {},
    "spacing_boundaries": {
      "title_to_author": {"status": "default", "resolved_pt": 8, "rule": "max(previous space-after, following space-before); emit once"},
      "author_to_affiliation": {"status": "default", "resolved_pt": 6, "rule": "max(previous space-after, following space-before); emit once"},
      "affiliation_to_abstract": {"status": "default", "resolved_pt": 12, "rule": "max(previous space-after, following space-before); emit once"},
      "abstract_to_keywords": {"status": "default", "resolved_pt": 6, "rule": "max(previous space-after, following space-before); emit once"}
    }
  },
  "abstracts": {
    "english": true,
    "chinese": false,
    "keywords": true,
    "source_text": null,
    "content_box": null,
    "style": {},
    "label_style": {},
    "keyword_style": {},
    "label": "Abstract:",
    "label_mode": "default",
    "label_paragraph_index": null,
    "content_paragraph_index": null,
    "keyword_label": "Keywords:",
    "layout_mode": "block",
    "layout_evidence": ""
  },
  "body": {
    "section_numbering": "1, 1.1, 1.1.1",
    "section_label_suffix": "",
    "heading_profile": "article-bold",
    "toc": false,
    "toc_evidence": {},
    "line_numbers": true,
    "content_box": null,
    "keyword_content_box": null,
    "heading_styles": {
      "level0": {},
      "level1": {},
      "level2": {}
    },
    "sections": [
      {
        "title": "Introduction",
        "paragraphs": ["Source-backed guidance or placeholder text for this section."]
      }
    ]
  },
  "tables": {
    "caption_position": "above",
    "caption_position_evidence": {},
    "notes": true,
    "booktabs": true,
    "caption_style": {},
    "note_style": {},
    "layout_evidence": {}
  },
  "figures": {
    "caption_position": "below",
    "caption_position_evidence": {},
    "separate_files_required": true,
    "subfigures": true,
    "caption_style": {},
    "layout_evidence": {}
  },
  "references": {
    "style": "author-year",
    "style_evidence": {"source": "", "confidence": "default"},
    "bib_engine": "thebibliography",
    "official_bst": null,
    "entry_style": {}
  },
  "footnotes": {
    "enabled": false,
    "style": {},
    "marker_style": "source-not-extracted",
    "count_in_template": 0
  },
  "appendices": {
    "enabled": true,
    "numbering": "A, B; Eq. (A.1); Table A.1; Fig. A.1",
    "layout_evidence": {
      "boundary_calibration": {
        "status": "pending",
        "mode": "continuous",
        "source": ""
      }
    }
  },
  "statements": {
    "acknowledgements_before_references": true,
    "credit_author_statement": false,
    "declaration_of_competing_interest": false,
    "data_availability": false
  },
  "assets": {
    "word_media": [],
    "header_footer_parts": [],
    "extraction_required": false
  },
  "fallbacks": []
}
```

## Required Decisions

Fill these before generating:

- `journal.language`: `en`, `zh`, or `mixed`.
- `document.class_strategy`: use `cls` by default so the generated template can own title-page, front-matter, page-style, heading, caption, and one-column/two-column behavior. Use `sty` only as a legacy fallback when preserving an existing class is source-backed.
- `document.columns`: `single`, `double`, or `mixed`.
- `document.paper`: use a standard LaTeX paper option only when the Word
  section dimensions match it. For `custom`, preserve the source section size
  in `document.paper_dimensions_mm` as `{ "width_mm": number,
  "height_mm": number, "source": "Word sectPr" }`; do not round a custom
  Word page to A4 or Letter.
- `document.font_size_pt`: source-derived body font size. Use 10 pt as the conservative default for two-column journal templates and 12 pt for single-column templates when official evidence is incomplete.
- `document.render_calibration`: keep `status: not_run` unless a rendered
  Word/PDF comparison measures a persistent body-size metric difference. Set
  a separate candidate to `status: render_probe`, retain source font/baseline,
  measured font and same-column baseline-step deltas, diagnostics path, and
  before metrics. Set `status: render_verified`, `calibrated_font_size_pt`,
  `body_baseline_pt`, and after metrics only when the calibrated class improves
  the same-content comparison without breaking page count, page size, anchors,
  or required structural zones. The original `font_size_pt`, Word line-spacing
  rule, and raw spacing value remain source evidence; never overwrite them.
- A page/body/placement/float-spacing calibration moves from `render_probe` to `render_verified` only
  through a same-target promotion report. The candidate spec must otherwise be
  identical to the source spec. Store accepted ordinary/candidate metrics,
  reference/generated PDF basenames, and evidence file hashes under
  `render_calibration.acceptance`; keep machine-specific absolute paths in the
  separate `promotion_report.json`. A rejected probe never appears in the final
  spec.
- `figures.layout_evidence.placement_calibration` and
  `tables.layout_evidence.placement_calibration` are optional ledgers with
  `{status, mode, source}`. The only current candidate mode is `nonfloating`.
  Word inline/anchor or table-flow evidence can create `status: render_probe`
  but cannot create `render_verified`. The strict promotion report must add an
  `acceptance` ledger before the class may replace its ordinary float wrapper.
  Do not use `placement_mode` or `placement_verified` fields.
- `document.font_family`: preserve the actual Word body-font evidence. Keep
  `font_family_mode` as `evidence_only` unless a PDF comparison validates a
  XeLaTeX font choice; then use `verified` and retain the original Word family.
- `document.cjk_font_family`: preserve the Word East Asian body-font evidence
  separately from the Latin font. Use CJK-safe `ctexart` for `zh` or `mixed`
  documents; enable a source CJK font only after it is available and render
  verified, otherwise retain the ctex default font chain.
- `page.column_sep_mm`: record two-column gutter width when available; use a narrow journal default such as 6 mm only as a fallback.
- `page.header_distance_mm`, `page.footer_distance_mm`, `page.gutter_mm`, and
  `page.mirror_margins`: preserve Word section `pgMar` and settings evidence.
  A positive gutter is a binding offset; mirrored margins use the Word left
  margin as LaTeX inner margin and right margin as outer margin. Header/footer
  distances are evidence for rendered placement, not proof that an XML asset
  has been positioned correctly.
- `page.representative_section_index`: the Word section selected as the
  repeated manuscript-body frame. Prefer a repeated double-column section over
  a single-column title section; derive page frame, column gap, and
  representative table/figure geometry from this section.
- `page.render_calibration`: optional values measured from a same-content PDF
  comparison. Only `status: render_verified` or `verified` may override the
  source-derived `margins_mm` or `column_sep_mm` used by the class. Preserve
  the original Word values beside the calibration, record the compared PDF
  paths/metrics in `source`, and omit this block when comparison is unavailable.
- `page.float_spacing_evidence`: always record `status` (`source` or
  `default`), `resolved_pt`, `eligible_boundary_count`, raw `boundaries`,
  `mapping: candidate_only`, source, and the single-emission rule. Each
  boundary names the object kind/side, outside paragraph role and index, both
  adjacent Word paragraph sides, and its resolved value. Only
  `body_text_candidate` neighbors contribute to the aggregate.
- `page.float_spacing_calibration`: optional candidate with `status`,
  `textfloatsep_pt`, `intextsep_pt`, `dbltextfloatsep_pt`, and `source`. Create
  it only from source-backed float-spacing evidence. `render_probe` remains
  inactive in ordinary output; only strict promotion may write
  `render_verified` plus `acceptance`. Do not use this ledger for caption gaps
  or float-to-float spacing.
- `page.header_footer_profile`: use `fancy-running-head` only when a running head/header rule is source-backed; use `plain` or `empty` when the official Word/PDF evidence lacks a visible running head.
- `page.header_footer_evidence`: preserve every Word header/footer XML part,
  including text samples and embedded-image relationship IDs. Use
  `source-backed-custom` when source material exists but placement still needs
  visual reconstruction; do not substitute a generic running head.
- `page.header_footer_evidence.active_variants`: retain the header/footer
  parts actually referenced by each Word section, keyed by `default`, `first`,
  or `even`. For active text, retain ordered text/tab/PAGE-field tokens and
  direct formatting from every meaningful source paragraph so the class can
  expose editable left, centre, and right slots. A running-text paragraph and
  a page-number paragraph may be separate. Preserve those slots as candidates;
  do not activate custom page furniture until a same-content render comparison
  selects it. Retain a distinct first-page style.
  A literal numeric token becomes `\thepage` only when multiple equivalent
  active variants demonstrate changing page-number samples, including
  alternating left/right placements for facing pages.
- `page.header_footer_evidence.safe_text_parts`: when inspection proves that
  an active part contains only deterministic paragraph tokens/page fields and
  no drawings, relationships, or text boxes, record its part name here. This
  is an evidence ledger for the per-part text mapping; it does not authorize
  image placement or first-page furniture.
- `page.header_footer_auto_apply`: keep false until rendered Word/PDF evidence
  confirms source text, asset, and rule positions. A false value preserves
  extracted slots in the class but makes the default page style empty; XML
  relationship and table order alone may still mirror, suppress, or reposition
  furniture, or use a different first-page variant at render time.
- `page.first_page_furniture_auto_apply`: keep false until a same-content
  render confirms the Word `first` header/footer variant. When verified, set
  it true to use the class's distinct `tempTwoFirstPage` style; this prevents
  a first-page logo, rule, or notice from leaking onto later pages.
- `page.section_flow`: preserve all Word sections, including page dimensions,
  margins, column counts, `section_break_type`, and different-first-page flags.
  Use the first single-to-double transition automatically only when the
  front-matter evidence supports it; expose later boundaries as editable class
  helpers and record them as pending until the manuscript boundary and rendered
  PDF confirm the mapping.
- `page.column_widths_twips` and `page.columns_equal_width`: preserve the
  representative Word `w:cols/w:col` widths. Unequal widths are a distinct
  layout mode, not an ordinary equal-width `twocolumn` article; expose the
  source widths and a render-confirmed candidate such as `paracol` while
  keeping automatic activation pending.
- `front_matter`: include all mandatory title-page elements from the official source.
- `front_matter.column_break_evidence`: preserve paragraph-level Word
  `w:br type="column"` elements with paragraph index, style, and text. These
  breaks can determine where a title, abstract, or metadata block enters the
  next column even when every section reports the same column count.
- `front_matter.body_column_transition_after_front_matter`: set true only when
  Word section evidence shows a single-column first section followed by a
  representative double-column body. A missing first-section `w:cols` is the
  Word one-column default when a later body section explicitly records two
  columns; in that pattern it is positive transition evidence. The class must start in one column and
  `main.tex` must wrap the front matter in a `\twocolumn[...]` title region
  so the body starts in two columns without a forced page break.
- `front_matter.author_layout`: use `inline` only when a visible Word author
  exemplar is a single paragraph; the class then renders `\and` as editable
  punctuation rather than a tabular author separator. Keep `tabular` for
  missing, multi-cell, or multi-paragraph evidence.
- `front_matter.cover_mode`: treat `candidate_first_page_variant` as evidence
  that needs rendering, not proof of a standalone cover. Expose an editable
  cover environment but insert it automatically only when Word/PDF evidence
  explicitly establishes a separate cover page.
- `front_matter.title_style`, `author_style`, and `affiliation_style`: retain
  direct formatting from used Word styles. The class should apply source font
  size/weight/shape and recorded after-spacing before falling back to generic
  title or author profiles. Use the class `\affiliation{...}` interface for
  editable affiliation content. When a source role has no explicit Word `jc`,
  treat the Word paragraph default as left alignment; reserve centred fallback
  for a role with no usable Word evidence. If no visible exemplar or matching
  semantic style exists, store an explicit role object with
  `evidence_status: "default"` and a source note; do not leave the role
  indistinguishable from an uninspected field.
- `abstracts.layout_mode`: use `inline_label` only when the source layout and
  render support a run-in label. Record `layout_evidence` as `inferred` until a
  Word/PDF comparison confirms it; the generated gap log must retain that
  pending check. Use `block` when the evidence is incomplete.
- `abstracts.label_mode`: `inline` when label and content share a defensible
  Word paragraph, `separate` for a standalone label followed by adjacent
  content, `none` when visible content has no visible label, and `default` only
  when structure is unavailable. Record `label_paragraph_index`,
  `content_paragraph_index`, `label_style`, and the distinct content `style`.
  Indentation alone and prose that merely begins with "Abstract" do not prove
  an inline label. The class owns all modes; do not inherit the base class
  abstract environment.
- `front_matter.spacing_boundaries`: evidence ledger for `title_to_author`,
  `author_to_affiliation`, `affiliation_to_abstract`,
  `abstract_to_keywords`, and `abstract_label_to_content` when applicable.
  Each entry records both paragraph indexes, raw before/after twips,
  `resolved_pt`, `status`, and the rule `max(previous after, following before);
  emit once`.
- `abstracts.style` and `abstracts.keyword_style`: keep the two semantic roles
  separate even when Word assigns both `Normal`. A uniform visible run format
  can supply paragraph-wide role typography; mixed runs are local label/value
  evidence and must not turn the entire role bold, italic, or coloured.
- `abstracts.keyword_label`: retain a visible source label such as `Keywords:`,
  `Key words:`, `Index Terms:`, or `关键词：`. Do not normalize a source
  `Index Terms` label into `Keywords` merely because both map to the same
  semantic role.
- `references`: record whether the style is official, inferred, or a placeholder
  in `style_evidence`. Prefer a visible numbered Word entry over generic prose;
  do not treat `et al.` alone as author-year citation evidence.
  Apply a source-backed bibliography font and list left indent when the
  generated backend can express them; keep hanging-indent calibration pending
  when it depends on label width or an official `.bst`.
- `footnotes`: set `enabled` only when Word `footnotes.xml` provides a visible
  note paragraph with usable style evidence. Preserve raw note-node count
  separately; Word separator/continuation nodes are not footnote formatting
  evidence. Retain `marker_style: source-not-extracted` until a visible sample
  or rendered reference proves the marker sequence and separator rule.
- `appendices.numbering`: use an explicit class appendices interface. When the
  source requires `A.1` forms, reset equation/table/figure counters at the
  appendix boundary and derive their labels from the appendix section.
- `appendices.layout_evidence.boundary_calibration`: keep appendix flow
  continuous in ordinary output. A separate `status: render_probe`,
  `mode: new_page` candidate may be promoted to `render_verified` only when
  appendix is the ordinary output's sole shifted anchor and the strict
  same-content page-count-repair gate accepts it. Rendered page appearance by
  itself is not source evidence for `\clearpage`.
- `body.section_label_suffix`: use `"."` when headings are source-backed as `1. Introduction` or `1.` style; otherwise leave empty.
- `body.toc`: enable only when an official Word TOC field is present or an
  author instruction explicitly requires it. A paragraph labelled Contents or
  目录 without a Word TOC field is a rendered-verification candidate, not proof
  that generated LaTeX must include a TOC.
- `body.heading_profile`: use `article-bold` for default article-style headings and `journal-compact` for smaller journal headings when source evidence or regression variant search supports it.
- `body.content_box`, `abstracts.content_box`, and
  `body.keyword_content_box`: record a role-specific left/right paragraph box
  only when an actual Word style directly declares it. These are not page
  margins. A source-backed record contains converted dimensions, source style
  ID/name, source wording, and confidence.
- `body.heading_styles`: retain each used Word heading style's direct font and
  paragraph evidence, including outline level, left indent, and before/after
  spacing. The class may consume these only for the matching heading level.
  When that effective style has no explicit font size, a role-specific official
  template sentence such as `Subheads are 9 pt` may supply only the missing
  size for the matching level. Record it under
  `instructional_format_evidence` with `font_size_pt`, `sample_text`,
  `paragraph_index`, and `source`. Do not use an unrelated point value,
  override an explicit style size, or infer heading spacing from the sentence.
- `tables.caption_style`, `figures.caption_style`, and
  `references.entry_style`: preserve both style-level and actual sample
  paragraph formatting. The generator can apply source font, line spacing,
  alignment, label weight, and ordinary caption spacing. One-sided caption
  boxes and bibliography hanging indents remain backend/layout-specific and
  must be listed in `format_gap_log.md` until a rendered check confirms them.
- `tables.caption_position_evidence` and
  `figures.caption_position_evidence`: keep caption typography separate from
  object attachment. A source-backed entry records object and caption paragraph
  indexes, `above`/`below`, paragraph distance, classification source, and
  `adjacent` or `nearby` confidence. Ignore caption-like text inside table
  cells and distant candidates. When no relation is safe, retain `status:
  default`, the reason, and the observed relation; do not label the default as
  an official requirement.
- `tables.caption_spacing_evidence` and
  `figures.caption_spacing_evidence`: record position, caption/object paragraph
  indexes, the named facing sides, both raw twips values, `resolved_pt`,
  source/default status, and the max-and-emit-once rule. An above caption uses
  caption-after/object-before; a below caption uses object-after/caption-before.
  Also record `caption_outer_side`, `caption_outer_twips`, `outer_status`, and
  `outer_pt` for the opposite side of the caption; it is a separate class skip,
  not an input to the internal maximum.
  A source status requires at least one measured facing-side value. When order
  or both facing sides are unavailable, retain an explicit default rather than
  borrowing the caption's outside spacing.
- `tables.layout_evidence`: retain a representative Word table's width type,
  grid widths, alignment, fixed/autofit mode, active printable borders, and
  merged-cell markers, and the selected table style id. An empty
  `active_borders` list is interpreted together with `style_id`: `TableGrid`
  can provide printable grid rules even when direct `tblBorders` are absent,
  while an empty list with no grid style is treated as no direct printed
  border. The
  optional `geometry_mode` value (`precise` or `full`) is a render-probe
  candidate, not an ordinary default. Do not
  treat one example table as a global manuscript-width rule without a render.
- `tables.layout_evidence.span_evidence` and
  `figures.layout_evidence.span_evidence`: record `status`, `mode`,
  `source_section_index`, `source_section_columns`, `object_width_pt`,
  `usable_width_pt`, `local_column_width_pt`,
  `object_to_local_column_ratio`, and `object_to_usable_width_ratio`. Valid
  modes are `single_column`, `double_column`, and `uncertain`. A mode may drive
  `journal{table,figure}wide` only when `status: source`; a one-column local
  section inside an otherwise two-column document stays `uncertain` until a
  render establishes its manuscript role. Missing section/object geometry must
  not be replaced with a guessed span.
- `figures.layout_evidence`: retain Word body drawing type, dimensions, and
  alignment candidates. Also retain anchor/wrap geometry when available.
  Inline/anchor metadata is evidence for a candidate, not sufficient proof of
  universal float placement.
- `statements`: record required declaration files or sections, especially highlights and CRediT/author contribution statements that may be separate submission files.
- `assets`: retain embedded Word media and the header/footer parts that may use
  it, including non-flow text boxes and their source parts. Run the asset
  extractor or generation with `--word-source` so the final package contains
  original assets plus `assets/word_asset_manifest.json`. Text boxes are
  candidates until rendered coordinates are confirmed; they must not become
  body flow solely because their text was extracted. When Word exposes an
  anchored shape, preserve `assets.text_boxes[].geometry` with its native
  `width_emu`, `height_emu`, horizontal/vertical relative coordinate systems,
  offsets, wrap type, shape name, and text insets. These are source evidence,
  not permission to apply absolute positioning automatically.
- `fallbacks`: one entry per missing official rule. Role objects marked
  `evidence_status: "default"` must also be listed in the generated gap log.

## Fallback Entry

```json
{
  "area": "body.line_spacing",
  "missing_requirement": "Official template did not specify line spacing.",
  "fallback_used": "English default 1.15",
  "source_checked": "Guide for authors and DOCX template",
  "latex_location": "journal-template.cls"
}
```

## Area Checklist

The spec should cover:

- page size and margins
- one-column or two-column mode
- header/footer/page numbers
- cover/title block
- article type, title, authors, affiliations, corresponding author
- abstracts, keywords, highlights, graphical abstract
- table of contents if required
- heading levels and numbering
- body font, indentation, line spacing
- lists, quotes, acknowledgements, declarations
- tables, table notes, long/wide tables
- figures, subfigures, artwork requirements
- equations and equation numbering
- footnotes and endnotes
- citations and bibliography
- appendices and supplementary material
