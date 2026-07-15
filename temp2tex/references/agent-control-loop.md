# Agent Control Loop

## Purpose

Use this file to keep a model on the actual Temp2TeX task. The job is not to
transcribe a Word document, run a converter, or maximize a PDF score. The job
is to create an editable LaTeX template whose formatting decisions can be
traced to the official Word template and supporting official evidence.

Keep this invariant visible in working notes:

> Every observable source formatting decision has one of four outcomes:
> mapped to an editable LaTeX owner, recorded as a justified default, retained
> as an unresolved gap, or marked not observable.

## Mandatory Working Ledger

Maintain a compact live ledger while working. `word_format_ledger.json` is the
machine-readable form when possible; a human-readable table is acceptable when
the source cannot be parsed.

| Field | Required content |
| --- | --- |
| Evidence ID | Word paragraph/run/table/drawing/comment/PDF location |
| Zone and role | For example `front_matter.title`, `body.heading_2`, `figure.caption` |
| Observed format | Text, font, size, emphasis, spacing, alignment, geometry, numbering, or object relationship |
| Authority | official Word, official instruction, official PDF, inferred, or default |
| LaTeX owner | exact class macro/environment/file that will own the behavior |
| Status | `mapped`, `needs_mapping`, `default`, `unresolved`, or `not_observable` |
| Audit | compilation check, visual check, or explicit reason it is pending |

Do not replace the ledger with prose summaries. Do not claim a role is mapped
because a similar Word style exists; point to a used role-matched exemplar.

## Atomic Reconstruction Loop

Use `references/atomic-reconstruction.md` as the working procedure. The
smallest evidence unit is a visible Word paragraph plus its contiguous run
spans, or one table-cell paragraph, drawing, footnote, header/footer part, or
field where that is the actual source container. Process each unit through this
loop before moving to visual tuning:

1. **Observe:** retain source location, visible text or object identity,
   effective and direct formatting, and its local relationship to neighbours.
2. **Classify:** assign one semantic role, mark it as instruction/example/
   manuscript evidence, or explicitly leave it unclassified. A heading-looking
   string, comma-separated line, or generic Word style is never sufficient by
   itself.
3. **Map or gap:** give the evidence one editable LaTeX owner at the narrowest
   correct scope, or record why it is a default, unresolved, or not observable.
   Preserve a local run override locally; never promote it to a class rule from
   a single mixed-format paragraph.
4. **Exercise and audit:** put a neutral fixture for the role in `main.tex`,
   compile it, and retain the evidence-to-owner link for the structure and
   render audit.

No page-level, global-style, or pixel-level adjustment may be made to conceal
an unfinished atomic unit. An initial generated package is a queue of proposed
mappings, not evidence that those mappings are correct.

## Phase Gates

### 1. Evidence

Inspect the source by zone rather than extracting a single global `Normal`
style. Resolve title, authors, affiliations, abstract, keywords, each heading
level, body, lists, equations, tables, figures, notes, references, appendix,
and page furniture independently where applicable.

For each visible paragraph, retain its paragraph formatting and every
contiguous run-format span. For objects, retain the local section, dimensions,
caption relation, and immediate surrounding paragraph spacing. For tables,
retain column widths, borders, fills, merges, cell alignment, and cell-local
text formatting. Do not treat a table as an image.

Word comments never become manuscript content. Adopt a comment as formatting
evidence only when all of the following hold:

1. It is anchored to an identifiable source location.
2. It names a semantic target such as body text, table note, or footnote.
3. It supplies an unambiguous value such as a font size, font family, or exact
   line spacing.
4. It does not conflict with stronger visible Word or official publisher
   evidence.

Record the comment ID, anchor, wording, and conflict result in the ledger and
spec. Otherwise retain it as non-binding guidance.

**Exit gate:** every applicable zone has evidence IDs or `not_observable`.
For each applicable zone, every selected paragraph/run, table cell, drawing,
note, or furniture item has passed the atomic loop or remains explicitly in
the unresolved queue.

### 2. Mapping

Turn each ledger row into one named editable LaTeX owner. Class-wide rules
belong in `journal-template.cls`; sample content and metadata belong in
`main.tex`; copied artwork belongs in `assets/`; a source fact or assumption
belongs in `template_spec.json` and `format_gap_log.md`.

Never use a global body font, margin tweak, or a generic package default to
erase a role-specific difference. Preserve local run formatting locally. Keep
unresolved roles visible rather than guessing a rule.

**Exit gate:** each role is `mapped`, `default`, `unresolved`, or
`not_observable`, with a named owner or an explicit gap.

### 3. Build

Create a class-based package. Exercise every applicable role with editable
fixture content so the class interface is actually compiled. A copied filled
article is evidence, not the default template body. Keep sample body images as
assets unless they are reusable journal furniture; use a neutral editable
figure fixture by default.

**Exit gate:** the package contains `journal-template.cls`, `main.tex`,
`template_spec.json`, `format_gap_log.md`, `references.bib`, `assets/`,
`figures/`, and the source/coverage records available for the case.

### 4. Audit And Repair

Audit in this order:

1. **Ledger audit:** no required zone was skipped; no role was inferred from
   unrelated instructional text or a generic Word style.
   Confirm that selected author lines are name sequences rather than affiliations,
   dates, correspondence, or typography guidance; that captions are actual
   caption exemplars rather than instructions; and that table-cell evidence is
   audited as text plus grid geometry, not flattened into an image.
2. **Ownership audit:** every mapped requirement has one editable LaTeX owner;
   no formatting logic is hidden in a flattened converted manuscript.
3. **Compile audit:** final `main.tex` and class compile without fatal errors.
4. **Structure audit:** title, metadata, abstract, headings, body, table,
   figure/caption, notes, references, and appendix are present where required.
5. **Visual audit:** compare same-content source and generated PDFs when
   available. Repair source-backed differences one at a time, then repeat the
   affected checks.

For visual audit, image *content* may differ. Mask only raster image interiors
when calculating an image-insensitive metric. Continue checking image box
position, dimensions, frame/border, caption, wrapping, whitespace, and later
page flow. Do not mask tables, captions, text, rules, or vector drawing
geometry. A separate raw-pixel metric remains useful diagnostic evidence.

If no renderer is available, record the exact pending compile/render/compare
commands and do not downgrade the package to a failed conversion solely for
that reason.

**Exit gate:** critical failures are repaired or explicitly listed with their
evidence, consequence, and next verification action.

### 5. Handoff

Hand off an editable package with a clear boundary between official rules,
inferences, and defaults. The README must state what was checked and what
remains pending. Never call an unrendered or unresolved role visually matched.

## Anti-Drift Checks

Ask these questions before any new action:

1. Which ledger item does this action resolve or audit?
2. Is this the smallest action that advances the current phase?
3. Does it create evidence, an editable mapping, or a reproducible audit
   record?

If the answer to all three is no, do not perform it. Typical drift includes
running a large corpus for a single journal, tuning generic pixel thresholds
before mapping a missing caption, converting sample article prose into the
template, or treating a missing local tool as a reason to stop.

Also stop and return to the ledger when an action proposes a global class
change from one paragraph, suppresses a role because it is hard to render, or
uses a visual score without first proving that the compared files contain the
same role-level fixture. These are audit failures, not permission to continue.

## Testing Scope

For an ordinary journal task, test the generated package and, when possible,
one same-content source-vs-generated render comparison. Use the broader
corpus only when the user requests skill development or a reusable generator
change. For skill work, run affected cases first, then a representative set,
then the required corpus manifests. A benchmark result informs skill changes;
it never substitutes for the per-journal evidence ledger.
