# Agent Control Loop

## Purpose

Use this file to keep a model on the actual Temp2TeX task. The job is not to
transcribe a Word document, run a converter, or maximize a PDF score. The job
is to create an editable LaTeX template whose formatting decisions can be
traced to the official Word template and supporting official evidence.

Keep this invariant visible in working notes:

> Every observable source formatting decision has one of five outcomes:
> mapped to an editable LaTeX owner, recorded as a justified default, retained
> as an unresolved gap, marked not observable, or classified as non-format
> guidance with a reason.

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
| Status | `mapped`, `needs_mapping`, `default`, `guidance`, `unresolved`, or `not_observable`; guidance also has a declared semantic kind |
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

For a large, legacy, or unfamiliar Word source, run
`audit_word_capture_coverage.py` before starting atomic mapping. A
`capture_complete` result is a source-extraction gate only, not a mapping or
fidelity claim. `captured_sparse_or_empty` means the official template has no
visible body exemplar; use stronger official material or a documented default.
`capture_incomplete` blocks the strict mapping audit and visual calibration
until the named capture limitation is resolved.

For each visible body/table paragraph and each visible header/footer, note, or
text-box paragraph, retain its paragraph formatting and every contiguous
run-format span. Create an independent audit unit for every observable table
grid/header/width/merge structure and drawing placement; do not assume the
nearby caption or cell text owns that geometry. For objects, retain the local section, dimensions,
caption relation, and immediate surrounding paragraph spacing. For tables,
retain column widths, borders, fills, merges, cell alignment, and cell-local
text formatting. For lists, retain every list item plus its independent
numbering-system unit, including label family, start/restart, levels, and
left/hanging indentation. Do not treat a table as an image or a list as an
ordinary body paragraph.

Treat layout-only runs separately from ordinary whitespace. Tabs, line breaks,
non-breaking spaces, and whitespace with direct run formatting receive a
`run_layout` decision because they can carry table, header, field, or inline
spacing semantics. Plain inherited spaces remain under the parent paragraph.
Do not drop a formatted separator merely because it has no letters.

For every OMML formula, retain a formula-instance unit with its convertible or
manual-translation structure, local paragraph alignment, display/inline state,
and adjacent visible number. Retain a separate equation-system unit for the
counter, tag form, number placement, spacing, and appendix interaction. Do not
call the equation matched merely because an `amsmath` fixture compiles.

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

**Exit gate:** `word_format_ledger.json.coverage.all_visible_text_units_captured`
and `all_observable_object_units_captured` are true, every applicable zone has
evidence IDs or `not_observable`.
For each applicable zone, every selected paragraph/run, table cell, drawing,
note, or furniture item has passed the atomic loop or remains explicitly in
the unresolved queue.

If `front_matter_sequence_review.requires_semantic_confirmation` is true,
run `prepare_front_matter_confirmation.py word_format_ledger.json --output
front_matter_semantic_confirmation.json`. Confirm every ordered title, author,
affiliation, and metadata record from its visible Word context. The completed
file must match the ledger fingerprint and retain the proposed role. An
evidence disagreement stays open instead of being relabelled silently. Rerun
`assess_conversion_readiness.py` before an ordinary mapping batch.

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

For a large ledger, do not force a one-turn completion or silently abandon
the queue. First select one coherent source-backed concern with `--roles`
(for example `page.frame,page.columns` or `table.structure,table.caption`),
then create a stable 20-group review batch inside that selection. Complete
only its final dispositions, merge it through the fingerprint-bound batch
tool, then rerun the atomic audit and readiness report. The role filter is
only a work-order mechanism: it never hides other pending groups or weakens
the audit gate. A package with a
complete ledger, preserved decisions, a bounded next batch, and
`checkpoint_handoff.status=ready_for_next_mapping_batch` is a valid
continuation checkpoint. It is not an ordinary completed handoff, it does not
authorize calibration, and it must state the exact next batch rather than
asking a later model to rediscover the source.

System aggregates are a separate queue that must be created before ordinary
mapping, not a requirement to finalize every child before a title, body, or
table mapping batch can start. Text-grid, tab-stop, paragraph-break,
character-effect, character-style, script/language, theme, and unmodeled OOXML
evidence must be split into child records in `system_format_triage.json`.
Follow the readiness report's next ordinary `recommended_mapping_slice`, then
reopen the system queue to review children whose linked role now has final
ordinary context. Review those children in a stable pending-only priority
batch, preserving their locator, observed value, and displayed review-order
reason. The priority only orders work: it never supplies a disposition, hides
a child, or lowers the strict-audit gate. Use `--review-order source-order`
when a forensic source-order recheck is needed. Do not include a system
aggregate in a normal `--roles` mapping batch or close it with a generic class
token; strict audit accepts it only through its child dispositions. Every
strict audit is bound to the exact serialized triage queue. After any child
edit, rerun the audit before coverage refresh, package validation, visual
calibration, or a fidelity claim. A stale child-triage audit cannot be used to
select a visual repair evidence scope, even when its Word ledger fingerprint
still matches.

Run `assess_conversion_readiness.py` after each merge and carry forward its
`recommended_mapping_slice` when it exists. The suggested `--roles` list is
derived from pending source-backed audit units in dependency order. Generate a
batch inside that slice before returning to the full queue. It is a work-order
hint only: do not remove, down-rank, or declare complete the unselected units.

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
   Confirm the audit used a v3 ledger and `atomic_mapping_audit.json.audit_complete` is true, then rerun
   `source_feature_coverage.json` with that atomic-audit artifact. A coverage
   report that lacks complete source capture or completed atomic dispositions
   cannot authorize visual calibration.
2. **Ownership audit:** every mapped requirement has one editable LaTeX owner;
   no formatting logic is hidden in a flattened converted manuscript.
3. **Compile audit:** final `main.tex` and class compile without fatal errors.
4. **Structure audit:** title, metadata, abstract, headings, body, table,
   figure/caption, notes, references, and appendix are present where required.
5. **Visual audit:** compare same-content source and generated PDFs when
   available. Repair source-backed differences one at a time, then repeat the
   affected checks. Combine two probes only when the same Word evidence shows
   that the two roles are coupled in one manuscript-flow decision, both
   isolated probes have been measured on the identical fixture, and the
   combined candidate is retained as a bounded `render_probe` pending strict
   promotion. Never create a cross-product search from visual scores.

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

Use `HANDOFF_STATUS.md` as an executable boundary, not a summary. A package
with unfinished evidence or atomic mapping remains `Ordinary handoff: blocked`.
After the final package validation, use `ready` only with `Package validation:
valid`, the current package fingerprint, and `Verification environment:
available`. When source mapping is complete but required local validation,
TeX, or rendering tools are unavailable, use only
`ready_with_pending_local_verification` with both validation and fingerprint
marked pending, environment `unavailable`, and exact rerun commands. This is
an editable delivery with an explicit local-check boundary, never a way to
skip source or mapping work.

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

When artifacts are available, run `assess_conversion_readiness.py` before a
new phase. Follow its `phase`, `next_actions`, and `blocked_actions`: a pending
Word atomic audit blocks calibration and strict-pass claims, but an unavailable
TeX/PDF tool may leave an editable package ready with a documented local
verification step. Do not override this state from an attractive visual score.

When a comparable PDF pair still fails visually, use
`visual_repair_plan` from the readiness report before selecting a probe. Its
order is binding for the next action: repair same-content fixture validity,
then structural page flow, then a failed local furniture contract, front
matter, object/caption flow, page frame, body density, or running furniture.
It names the actions that remain blocked at that point. Do not skip directly
to margins or font size because they are easy to vary; a visual repair plan is
an evidence-bound work-order, not an invitation to search parameters.

For every concern other than a broken same-content fixture, read
`visual_repair_plan.evidence_review_scope` before editing the class. It names
the exact ledger-matched audit units and their Word roles to revisit. For a
structural-flow failure, its roles are narrowed to the page frame/column
evidence plus the actual shifted anchor role; also inspect only the immediately
adjacent Word paragraphs at that boundary. A missing or fingerprint-mismatched
audit blocks source-rule selection. The scope is a readback list, not
permission to change every listed unit.

For repeated tables or figures, bind each rendered anchor to its exact current
Word evidence IDs in the task anchor map. When readiness exposes
`requested_evidence_ids`, use its `--evidence-ids` command path and inspect
only those source objects plus their immediate caption/flow context. If an ID
is not present in the ledger-matched audit, repair the anchor contract or audit
first; do not fall back to all objects sharing the same role.

Before an object/caption result enters a class rule, a float probe, or an
anchor contract, read its caption-relation `evidence_disposition`. Only
`confirmed_source_relation` can propose order, object-facing spacing, or a
per-object anchor. `remote_caption_candidate`, `label_mismatch`,
`ambiguous_source_relation`, and `no_observed_caption_relation` have explicit
prohibitions; follow them even when their Word paragraphs look visually close.
The first three states require a rendered or otherwise stronger source check;
the last may provide local geometry only. Never turn an audit warning into a
generic publisher-wide caption rule.

Treat `checkpoint_handoff` independently from `ordinary_handoff`. The former
answers whether another model can safely continue from current evidence; the
latter answers whether the conversion is complete enough to hand off as a
finished Word-derived template. Never turn a continuation checkpoint into a
fidelity claim merely because its LaTeX files compile.

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
