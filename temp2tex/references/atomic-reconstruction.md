# Atomic Reconstruction Protocol

## Purpose

This protocol keeps a model focused on reconstructing a journal template,
rather than transcribing a Word sample, trusting an initial converter, or
optimizing a PDF score. The template is rebuilt from small, traceable source
decisions.

## The Evidence Unit

Use the smallest visible source unit that has formatting meaning:

- an ordinary paragraph and each contiguous run-format span;
- a table-cell paragraph together with its cell grid, border, fill, merge, and
  alignment context;
- a drawing plus its anchor, dimensions, wrap state, and caption relation;
- a footnote/endnote paragraph and its marker;
- a header/footer paragraph, field, or page-furniture object;
- a floating text-box paragraph with its anchor and geometry context.

A Word list also has two independent units: each visible list paragraph is a
`body.list_item`, while each numbering definition is a `body.list_system`.
The system records the label family, start/restart behaviour, level text, and
left/hanging indentation. Do not pass list fidelity merely because a generic
LaTeX list environment renders bullets or numbers.

Each observed Word OMML formula also produces an `equation.instance` unit, and
the aggregate display/numbering policy produces an `equation.system` unit.
Audit formula structure separately from its counter, tag position, paragraph
alignment, and display/inline context. A successful OMML-to-LaTeX candidate is
not evidence that the source equation layout or number placement was matched.

Any Word paragraph with border, shading, or frame evidence also produces a
`block.decoration` unit. Its typography belongs to the paragraph role, while
its visible box, fill, padding, and anchor behaviour require a separate
editable LaTeX owner. Never substitute a generic coloured or framed box just
because it compiles.

For a table, the cell paragraphs do not replace its structural unit: audit the
grid, widths, borders, fills, merges, header row, indentation, default and
cell-local margins, row height/`cantSplit`, cell `noWrap`, and placement
separately. Preserve these as the matching table's local evidence. Word cell
padding does not prove a journal-wide `\tabcolsep`; a row pagination or no-wrap
flag does not justify boxing every LaTeX table or disabling wrapping globally.
When a table uses `tblStyle`, retain the resolved style definition, `basedOn`
chain, and every used conditional `tblStylePr` rule such as `firstRow` or
`band1Horz`. A style name is not a rendering decision: verify a matching visible
table region before promoting any condition to a LaTeX header, banding, border,
or cell-format helper.
For an image, do not audit manuscript-specific pixels as template rules; audit
its box dimensions, anchor/wrap state, caption relation, and surrounding flow.
For a text box, audit its geometry separately from its paragraph/run typography.
For header/footer drawings or VML shapes, audit the visual object's part,
geometry, and placement as `running_furniture`; do not reclassify it as a body
figure just because it contains an image relationship.
An official Word TOC field is a distinct `toc.structure` unit and may justify
`\tableofcontents`; a paragraph merely labelled Contents/目录 is not enough.
Word TOC entry tab stops are a separate `toc.layout` unit. Preserve each
level's indentation, right-tab position, leader, and page-number alignment;
the existence of a TOC field does not prove that LaTeX's default dotted leader
matches the source.
Visible non-TOC Word `w:tab` characters are a separate `paragraph.tab_stops`
system when their effective paragraph format defines tab stops. Retain each
paragraph's semantic context, tab type, position, and leader. Do not promote
an unused style tab stop, apply one global tab setting, or borrow the TOC's
leader layout for metadata or body text.
Word `framePr` with a `dropCap` value is a distinct `paragraph.drop_cap` unit.
Preserve drop versus margin mode, line count, anchor/wrap state, the first
visible letter, and the adjacent body text. A frame without `dropCap` remains
ordinary block/frame evidence; do not turn it into a decorative initial.
Small/all caps, highlight, text shading, text border, kerning threshold, hidden state,
character spacing, scaling, baseline position, outline, shadow, emboss, and
imprint on a visible Word run form a
separate `run.character_effects` unit. Preserve the exact span and role; do
not promote a local style effect into a document-wide LaTeX setting.
The same properties on a named Word style are also source rules, especially in
sparse templates. Preserve them as `named_style_rule` evidence with the style
identity, but do not call them rendered confirmation until a role-matched
visible use is available.
Each visible `w:rStyle` reference is also a separate `run.character_styles`
unit. Resolve the referenced character style before interpreting the run's
effective font, colour, underline, or effect formatting, then retain both the
style identity and the local span boundary. Do not flatten a character-style
reference into its paragraph style or a document-wide font rule.
When a visible run or named style uses Word theme color/font aliases, retain
the `word/theme/theme1.xml` palette/font scheme, alias, tint/shade, and local
use as a `document.theme` unit. The source inventory is the authoritative
per-span record. In the model-facing spec and `word-theme.tex`, group only
identical evidence kind, source scope/part/style/container, and theme aliases;
retain the occurrence count and bounded representative locations. This prevents
one inherited Word alias from masquerading as hundreds of distinct formatting
rules while preserving an audit path back to every use site. A theme alias is
not a license to use an arbitrary Office color or font in LaTeX; map the actual
source role and verify the rendered choice.
Character effects include OpenType `w14:ligatures`, `w:fitText`, and Word 2010
`w14:textFill` in addition to ordinary colour/shading/border effects. Retain
their local run and scope, including table cells and page furniture. A text-fill
scheme or `fitText` width is not equivalent to a generic font colour or size,
and a ligature setting is not authority to enable an OpenType feature globally.
Keep an evidence candidate and validate the affected role in rendering.
Word run language (`w:lang`), complex-script bold/italic (`w:bCs`/`w:iCs`),
complex-script flag (`w:cs`), and right-to-left direction (`w:rtl`) are a
separate `run.script_language` system aggregate. Keep the direct/effective values and local
source role/container distinct from ordinary Latin bold or paragraph alignment.
The source inventory retains every raw span and named style; the model-facing
review may group only identical kind, scope/part/style/table container, and
direct/effective script policy, while retaining cell positions as examples. Do not infer a document-wide language package,
font family, bidi direction, or hyphenation policy merely because Word records
an inherited language alias. Send every grouped sample to child-level system
triage, not to one ordinary atomic mapping decision.
The extractor also writes `word.unmodeled_format` evidence when it encounters
run or paragraph property nodes outside its current direct-format model. This
is a guard against silent loss, not a claim that every OOXML node is visible
typography. Before a full-fidelity claim, classify every recorded property as
one of: a visible role effect requiring local reconstruction; a documented
Word default; non-format metadata that has no layout consequence; or an
explicit unresolved gap. Keep its source part, occurrence count, and XML
attribute sample in `unmodeled-word-properties.json`. Do not suppress a
frequent property merely because the generated package compiles.
A first-page header/footer variant is a `cover.structure` candidate, not proof
that a standalone cover page should be enabled without render confirmation.
Each Word section also produces separate `page.frame` and `page.columns`
evidence. Map its page size, margins, header/footer distances, column count,
column gap, unequal widths, and break type to editable geometry/column helpers
before tuning any PDF score. Do not collapse a source `nextPage` transition
into a continuous full-width title block.
Word `docGrid` and direct paragraph/style/run `snapToGrid`, East Asian
auto-spacing, kinsoku, punctuation, or text-alignment properties form a
separate `page.text_grid` system aggregate. Preserve the section grid and each local
override as source evidence. A run-level `snapToGrid=0` is a local grid opt-out,
not missing data or ordinary font formatting. The raw span boundaries remain in
the source inventory; the grid evidence file may group identical scope, style,
container, and direct/effective run policy with a count and representative locations.
Do not approximate it by changing global LaTeX line spacing or enabling a
baseline grid without a Chinese or same-content render. Send each grouped
section/style/run item to child-level system triage, not to one ordinary atomic
mapping decision.
Word paragraph `w:bidi` and `w:textDirection` form a separate
`paragraph.direction` unit. They control paragraph flow, alignment semantics,
and start/end indentation; do not merge them with run-level `w:rtl` or a font
choice. Preserve direct/effective values and scope/style/table container. Raw
paragraph records remain in the source inventory; identical policy may be
grouped only with bounded representative locations. An enabled local policy is
not authority to make the entire manuscript RTL or vertical.
Word `w:suppressAutoHyphens` and `w:wordWrap` form a separate
`paragraph.break_policy` system aggregate. They can alter source line breaks and downstream
pagination. Preserve direct/effective values and source role/container. An
explicit no-hyphenation or no-wrap override needs role-specific LaTeX mapping
and a same-content page-flow check; ordinary permissive/default values remain
observed provenance rather than a reason to change the entire document's
hyphenation or wrapping settings. Send every grouped policy child through
system triage; do not map its aggregate as one global TeX setting.
An explicit Word `w:pgNumType` override is a separate `page.numbering` system:
retain its section boundary, number format, start/restart value, and any
chapter-number component. A `PAGE` field shows where a number renders; it does
not by itself establish the format or restart policy.
An explicit Word `w:lnNumType` override is a separate `line.numbering` system:
retain its section boundary, `countBy`, start value, distance from text, and
restart policy. A generic `\linenumbers` call only enables visible numbers; it
does not establish that Word's interval, reset behavior, or side distance was
matched. Keep the source-labeled `line-numbering.tex` candidates until the
rendered boundary confirms the policy. If Word omits any of these values, log
the missing parameters and keep the system as a mapping gap; do not silently
substitute LaTeX or assumed Word defaults. A documented OOXML default may be
recorded separately from the raw omission, but an automatic Word distance is
not a fixed point value and still needs rendered confirmation.
Treat note content and note system as separate evidence: visible footnote or
endnote paragraphs establish content typography, while Word numbering settings,
reference markers, restart behavior, and note count establish
`footnote.system` or `endnote.system`. Do not claim that standard LaTeX note
numbering matches a journal when Word supplies different marker evidence.
Likewise distinguish reference and appendix text from their systems. A visible
reference heading/entry establishes paragraph formatting, while the Word
reference boundary establishes `references.system` ownership of the
bibliography environment and numbering. A visible appendix heading establishes
heading typography, while its boundary establishes `appendix.system` ownership
of counter scope and page-boundary behavior.
Do not use whole-document defaults as a substitute for these units. A named
Word style is supporting evidence, not a mapping, until a role-matched visible
unit or an explicit sparse-template style rule supports it.

## Required Loop

For every unit considered for template behavior, record the following before
editing the class:

| Question | Required record |
| --- | --- |
| What is it? | Source ID, text/object identity, and role candidate. |
| What is visible? | Paragraph geometry plus every local run, cell, or object format. |
| Why does it represent that role? | Role-matched exemplar, explicit named style, or official instruction; otherwise reject it as guidance/example/noise. |
| Who owns it in LaTeX? | Exact macro, environment, class setting, or fixture location. |
| What remains uncertain? | `default`, `unresolved`, `not_observable`, or render-confirmation action. |

Use one owner per requirement. Split mixed paragraphs at formatting or
semantic boundaries. For example, a bold `Abstract` label and regular abstract
text are two units; an author line followed by red typesetting guidance is an
author-format unit plus a guidance unit, not a red author rule.

## Tool-Independent Evidence Record

When a model cannot run Word inspection, JSON helpers, TeX, or PDF tools, it
must still maintain a compact `manual_evidence_ledger.md`. Create it before
editing `journal-template.cls`; do not rely on remembered page appearance or a
free-form narrative. Use one row or fenced record per indivisible source unit:

| Field | Required content |
| --- | --- |
| `source_ref` | Official file/page/screenshot plus paragraph, table-cell, drawing, or visible run location. |
| `excerpt_or_object` | Short visible text, label, or object identity; never invent hidden Word values. |
| `observed_format` | Only observable geometry, typography, border/fill, caption relation, or surrounding-flow facts. |
| `role` | One semantic role or an explicit `ambiguous` candidate list. |
| `status` | `mapped`, `default`, `guidance`, `not_observable`, or `unresolved`; no implicit status. |
| `latex_owner` | Exact editable file and macro/environment/setting, or `none` for a real unresolved gap. |
| `reason_and_next_check` | Why the decision follows the source and the remaining compile/render/source action. |

Keep a companion `manual_mapping_audit.md` with the required zones: page
frame/furniture, title and front matter, abstract/keywords, headings/body,
tables, figures/captions, notes, references, appendices, cover/text boxes when
present, and language/engine. For each zone state `covered`, `default-backed`,
`unresolved`, or `not present in source`, and link its ledger records. A zone
may not be marked covered by an attractive PDF, a generic class default, or a
statement that the agent intends to inspect it later.

Manual records are deliberately conservative. If a format is not visible in
the supplied Word/PDF/web evidence, record a language-matched default or an
unresolved gap. Do not manufacture point sizes, margins, bibliography styles,
or table rules. When tools later become available, import or reconcile these
records into the structured ledger rather than discarding their source refs.

Use this compact shape for each ledger record:

```markdown
## manual-001
- source_ref: official-template.docx, page 1, title paragraph
- excerpt_or_object: "Article title"
- observed_format: centered; bold; visibly larger than author line
- role: front_matter.title
- status: mapped
- latex_owner: journal-template.cls :: \journaltitleformat
- reason_and_next_check: visible title exemplar; compile and compare first-page title box
```

Use this compact audit table at the end of `manual_mapping_audit.md`:

```markdown
| Zone | Status | Ledger records | Pending action |
| --- | --- | --- | --- |
| Title and front matter | covered | manual-001 to manual-008 | compile first page |
| Tables | default-backed | manual-021 | obtain a populated official table example |
| References | unresolved | manual-034 | confirm official reference guide |
```

Do not silently discard a run because it contains no visible letters. A tab,
line break, non-breaking space, or directly formatted whitespace may carry
header, table-cell, field, or inline-layout evidence. The atomic audit emits
these as `run_layout` units and requires a mapped/default/gap disposition.
Plain inherited spaces without their own direct format remain covered by the
parent paragraph and are reported separately, so the queue does not fabricate
meaning from ordinary spacing.

Likewise, an empty Word paragraph with explicit spacing, indentation, border,
shading, break, tab, section, or anchored-object evidence is a
`paragraph.layout` unit. Reproduce it through a local editable helper such as
`\journalblankparagraph` or leave an explicit gap. Inspect the preceding and
following source blocks before mapping it; it is not evidence for a global
body baseline or a generic `\vspace` rule.

Never combine `paragraph.layout` or `run_layout` evidence from different Word
parent paragraphs merely because their direct formats happen to match. Their
semantics depend on the adjacent title, metadata, body, table, figure, or
furniture blocks. Keep each local boundary in a separate atomic decision until
the same-content render confirms a reusable interface.

When the ledger assigns a run a more specific semantic candidate than its parent
paragraph, the run candidate controls the audit queue. Preserve the parent role
as context, but do not group that run with the surrounding title, author, or
keyword evidence. This matters for templates that append author-order, casing,
punctuation, or keyword-count instructions after an otherwise valid exemplar,
and for an `Abstract` or `Index Terms` label followed by template-filling prose.

## Classification Guards

- **Authors:** require a plausible name sequence and first-page context.
  Exclude affiliations, addresses, dates, correspondence, funding, abstracts,
  keywords, and typography instructions. For Chinese names, a sequence of
  two-to-four CJK-character names with author separators and optional
  affiliation marks is strong evidence; commas alone are not.
- **Headings:** require semantic style, outline structure, role-matched wording,
  or repeated rendered evidence. Lists and instructions do not become headings.
- **Captions:** require an adjacent/nearby labelled figure or table relation.
  A sentence explaining caption rules is guidance, not a caption exemplar.
- **Tables:** inspect cells as text and geometry. Preserve row/column,
  border/fill, merge, alignment, table indentation, default/cell-local margins,
  row pagination constraints, and cell-local runs. Never pass a table by
  masking or rasterising it.
- **Images:** image pixels may differ in a render comparison, but frame size,
  position, caption, wrapping, whitespace, and later page flow remain required
  audit targets.

## Mapping Rules

Put reusable journal behavior in `journal-template.cls`; put editable example
content in `main.tex`. Keep source-specific art under `assets/` or `figures/`.
Do not encode role formatting in a flattened converted manuscript.

For each change, identify the ledger IDs it implements. If no ID or explicit
default/gap justifies the change, do not make it. If one evidence unit conflicts
with a global rule, preserve it as a local override or leave a gap; do not
silently erase it.

Before selecting the units, confirm the ledger is v3 and both
`coverage.all_visible_text_units_captured` and
`coverage.all_observable_object_units_captured` are true. The ledger must
include body/table-cell evidence, table structure and drawing placement, as
well as list-system evidence, header/footer, footnote/endnote, and text-box text. A reported capture limitation is an
upstream audit gap: rebuild the ledger or record why the source cannot be
observed before proceeding.

For a corpus or unfamiliar publisher template, run
`audit_word_capture_coverage.py` before creating the atomic-decision starter.
Its `capture_complete` state confirms only that the observable source units
were extracted. Every paragraph and contiguous run still needs an atomic
disposition. `captured_sparse_or_empty` is not a defect in a blank official
template: use a guide/sample PDF or a documented default, without inventing a
body exemplar. `capture_incomplete` blocks strict mapping completion and any
visual-calibration claim until its limitations are resolved.

After selecting the units, create `atomic_mapping_decisions.json` from the
starter written by `scripts/audit_atomic_mapping.py`. The starter may group
units only when their source scope, container, kind, role proposal, and direct/effective format evidence
are identical. Review the text samples and split a group whenever it mixes
manuscript content with instructions, guidance, or another semantic role. Give
every paragraph and every contiguous visible run one of five dispositions: `mapped`, `default`,
`guidance`, `not_observable`, or `unresolved`. A `mapped` or `default` decision
must name a role from that exact unit's source-backed role candidates, the exact editable LaTeX owner, a package-relative `.cls` or `.tex`
file, and a token that appears outside comments in that exact file. A token
somewhere else in the package is not owner evidence. A `guidance` decision
must also choose exactly one semantic kind: `author_instruction`,
`editorial_note`, `placeholder_example`, `template_scaffold`, or
`non_manuscript_furniture`, with a concise explanation. Guidance is never a
catch-all for a source format the agent did not map. `not_observable` and
`unresolved` decisions need a concise explanation. Run the audit in strict mode before PDF calibration.

For a `mapped` or `default` paragraph/run with direct Word formatting, the
decision must also include one `format_bindings` record for every scalar path
under `direct_format`. Each record repeats the exact Word `source_value`, names
the package-local `latex_file` and executable `latex_token`, and gives a short
`mapping_reason` (for example, half-points converted to a class font-size
declaration). This is a traceability record, not an automatic proof that the
rendered result matches; use the role-level PDF check for that. A generic
`\maketitle`, `\RequirePackage`, or other broad owner token without per-property
bindings is insufficient for strict mapping.

The token must identify active template behavior, not merely an unused class
definition. When a binding or role token is a bare macro declared in a `.cls`
file, the strict audit requires a non-declaration use elsewhere in the package
(normally from `main.tex` or the active title/body/furniture path). Map the
invocation that exercises the mapped role, or record the role unresolved until
the class interface is actually used. Direct class-load declarations such as
`\setlength{...}` or `\geometry{...}` remain valid token targets, but still
need the normal role-level render check.

`prepare_atomic_mapping_review.py` exposes those paths and exact values in the
readable review sheet and prepopulates them in each bounded batch draft. Each
review card must also show its parent Word paragraph, up to two preceding and
following paragraphs from the same container, named style, table-cell state,
and paragraph-level direct formatting when the ledger provides them. Stop at a
table-cell or container boundary instead of jumping across it for a later
paragraph. This local context is read-only: it
helps distinguish an affiliation, instruction, caption, or body paragraph, but
it never changes the authoritative evidence IDs or Word values. The agent fills
only the target LaTeX file/token and transformation reason. Do not replace a
prefilled source value or omit a binding simply because it resembles the role's
usual formatting.

The same rule applies to observable object layout. A mapped/default table,
drawing, text box, page frame, or running-furniture unit needs
`object_format_bindings` for every retained `format_signature` geometry or
structure field. This covers image width/height, anchor and wrap state,
spacing around an object, table grid/width/borders/cell margins, and page or
furniture coordinates. Ignore only source identity bookkeeping and inherited
paragraph values already audited in their own role; do not discard a visible
object field because a generic `figure`, `table`, `geometry`, or `fancyhdr`
token exists.

The object review sheet also gives the next PDF comparison model. Body tables
and drawings are normally `flow_relative`: bind a unique confirmed caption or
nearby manuscript phrase after rendering, keep the object and context on the
same page, and verify caption order and surrounding flow. Header/footer
objects are `page_fixed`: bind text or artwork-frame evidence to the correct
page rectangle. Page frame/column evidence needs a full same-content document
comparison. Mask only raster image interiors; retain image frame geometry,
caption, wrapping, whitespace, table cells, and rules in the visual check.

Before editing a large starter, generate `atomic_mapping_review.md` with
`scripts/prepare_atomic_mapping_review.py`. Work first through its
source-single-role groups, then follow its fixed reconstruction order:
front matter, furniture, headings, body, local notes, objects, references,
appendix, and guidance. Its package token hints only identify candidate
editable locations; they never authorize a mapping. Write the actual decision
and reason in `atomic_mapping_decisions.json`, split mixed evidence IDs where
necessary, and let the strict audit decide whether the claimed owner/token is
real. A final mapped/default/guidance/unresolved group is not a fresh semantic
task merely because the review queue is regenerated: audit its local context,
bindings, and active package path, and reopen it only on a concrete conflict.

Keep front-matter metadata as its own work item. Dates, DOI labels, received or
accepted notices, classification codes, ORCID, correspondence notices, and
author biographies are not title text and must not be silently absorbed into an
author block. Split explicit labels into `front_matter.metadata.publication_id`,
`.doi`, `.dates`, `.funding`, `.contributor_note`, or `.editorial_note`; retain
the source line plus label-run and value-run bindings for each. Do not merge
adjacent metadata types because they share a title page. When the generated
package lacks an editable typed interface, add
`\journalmetadata[kind]{\journalmetadatalabel[kind]{Label:} value}` in
`journal-template.cls` and expose its editable content in `main.tex`; then map
the unit to that interface or leave an explicit gap. An untyped metadata line
is a documented default, never evidence that one observed type owns another.

For a large ledger, begin with one coherent reconstruction concern instead of
an arbitrary page of evidence. Use `--roles` to select source-backed roles,
then split only that semantic selection into stable batches. For example,
`--roles page.frame,page.columns --batch-size 20 --batch-index 1
--batch-template-output atomic_mapping_page_geometry_batch_001_draft.json`
creates a page-geometry work slice. Other useful slices are
`table.structure,table.caption`, `figure.placement,figure.caption`,
`running_furniture,floating_text`, `body.list_system,body.list_item`, and
`equation.system,equation.instance`, and `references.system,appendix.system`.
The filter is a review aid only: every nonselected ledger group remains pending
and continues to block a full-fidelity claim.

The draft binds only pending `group_key` values to the ledger fingerprint and
intentionally uses the non-final status `pending`; it cannot be merged until
the model has replaced entries with final dispositions and removed fields that
do not apply. It is a bounded task contract, not a source-evidence editor.
For an active continuation batch, add `--pending-only` so the review card and
draft exclude already final groups. If the requested role slice has no pending
groups, the command stops with a final-audit instruction instead of producing
an empty batch; rerun without `--pending-only` only when checking an existing
owner, binding, or token for a concrete conflict.
Write only the completed decisions for that slice in a separate batch JSON:

```json
{
  "schema_version": "temp2tex.atomic-mapping-batch.v1",
  "ledger_fingerprint": "<from-word_format_ledger.json>",
  "updates": [
    {
      "group_key": "<from-review-queue>",
      "status": "guidance",
      "role": "guidance.instruction",
      "guidance_kind": "author_instruction",
      "reason": "Visible template instruction, not manuscript-format evidence."
    }
  ]
}
```

Apply it with `scripts/apply_atomic_mapping_batch.py` to a new decisions file
and pass `--package latex-package`. The merge rejects unknown groups, duplicate
updates, non-final statuses, source fingerprint mismatch, attempts to edit
immutable evidence fields, incomplete final dispositions, and nonexistent or
comment-only or declaration-only mapped/default tokens. It refuses to overwrite a final group
unless the agent deliberately passes `--allow-revise`; corrections must remain
explicit and auditable. Repeat the review/merge cycle until no pending group remains, then run the strict
atomic audit. After every batch, refresh `conversion_readiness.json`; it
records `ready_for_next_mapping_batch` when the next model can safely continue
but the source mapping remains incomplete. A merged batch is still not a
fidelity result.

When the Word ledger is regenerated, use
`reconcile_atomic_mapping_decisions.py` instead of copying an earlier queue.
It carries a final disposition only when its source identity remains exact or
uniquely stable. It also performs a binding migration check: an old
`mapped`/`default` decision that lacks a currently required direct-format or
object-layout binding is reset to `pending`, even when its role and evidence
IDs still match. The reconciliation report lists these keys in
`binding_migration_required_keys`. Their fresh records retain the current
source paths and exact Word values; complete the missing LaTeX file, token,
and transformation reasons through the normal bounded review. Do not turn a
binding-migration warning into an `invalid_decision` by copying the old final
status back into the new queue.

## Audit Gate

Before visual comparison, verify that each applicable role has:

1. at least one classified evidence unit or an explicit absence record;
2. a source/default/gap status;
3. one editable LaTeX owner;
4. a compiled fixture that exercises the owner; and
5. a named audit action.

The atomic audit must report `source_capture_complete: true` and no
`needs_decision` or `invalid_decision` unit.
Known `unresolved` units remain visible gaps: they do not block an editable
handoff, but they do block any claim of full source fidelity.

Only then use same-content PDF comparison to refine already mapped geometry.
PDF results can reject or promote a candidate mapping; they cannot manufacture
missing role evidence. A failed comparison returns the agent to the specific
ledger item, not to generic margin or pixel-threshold tuning.
