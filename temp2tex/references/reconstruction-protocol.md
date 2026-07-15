# Reconstruction Protocol

Use this protocol for every Word-to-LaTeX conversion. A Word template is not a
complete specification merely because its XML can be parsed. Reconstruct the
visible publication system from evidence, then implement that system in an
editable class.

## Evidence Packet

Create one compact evidence record for each applicable zone. Store the result
in `template_spec.json` or `source_inventory.json`; attach screenshots or page
anchors when they are available.

| Zone | Minimum evidence | Record |
| --- | --- | --- |
| Page frame | Section dimensions and a rendered page | paper size, margins, columns, header/footer distances; ordered section transition evidence |
| Body | A real prose paragraph, not a placeholder or reference | effective style chain, direct formatting, indents, spacing, font, language |
| Front matter | Used title/author/abstract paragraphs on a rendered first page | alignment, block order, spacing, labels, affiliation/note model |
| Headings | One used example for each level | level, numbering, font, spacing, run-in state |
| Tables and figures | One representative table/drawing plus its caption | width behavior, caption location/style, notes, float policy |
| Page furniture | Active header/footer parts and a rendered page | text, rules, logos, page-number field, first-page exception |
| References and appendix | Actual entries/appendix content when present | heading, citation/bibliography behavior, indents, counters |

For every record, label the conclusion as one of:

- `source`: directly supported by a used Word paragraph, section property,
  official instruction, or rendered page.
- `inferred`: supported by several sources but not directly explicit.
- `default`: a documented Chinese or English fallback.
- `unverified`: a plausible implementation that has not been rendered against
  a relevant source page.

Never promote an unused built-in Word style, a blank placeholder, a separator
node, or an XML relationship ordering into source evidence for visible layout.

An exception applies to a truly sparse Word *template*: a deliberately named
paragraph style such as `Title`, `Abstract`, `Body Text`, `Heading 1`, or
`Figure Caption`, including a Word outline level where present, is a usable
template-style candidate. Carry its effective format into the editable class,
but label it `template_style_candidate` and verify it after the same-content
fixture is rendered. Do not treat a generic unused style as proof of the final
visible page.

## Semantic Mapping

Assign roles before translating numbers into LaTeX. Map title, authors,
affiliations, abstract, keywords, body, each heading, captions, tables,
figures, notes, references, and appendix separately. Derive a role's effective
format in this order:

1. direct paragraph or run formatting;
2. the used named style and its `basedOn` chain;
3. document defaults and section properties;
4. official instructions or a documented fallback.

Keep role evidence separate even when several roles share a typeface. A
reference paragraph is not body evidence; a caption is not a heading rule.

## Sparse Word Templates

Many publisher templates are empty shells. In that case, a PDF of the original
and a PDF of a populated LaTeX example are not comparable unless both use the
same content.

1. Preserve the original Word artifact unchanged and work on a copy.
2. Fill the copy with a compact, semantically tagged fixture: title/authors,
   abstract/keywords, two body paragraphs, two heading levels, one equation,
   one footnote, one table, one figure, citations/references, and appendix.
3. Use the template's actual named styles and existing semantic placeholders;
   do not add a made-up layout or infer formatting from the fixture itself.
4. Populate `main.tex` with equivalent content and matching zone order.
   Preserve body artwork from a filled Word sample in `assets/` as source
   evidence, but use a neutral editable figure placeholder in the reusable
   template package unless the artwork is confirmed page furniture.
5. Render both documents, compare page frame first, then body density, front
   matter, headings, floats, furniture, and bibliography. Save the fixture
   mapping and comparison report.

If Word cannot be populated reliably, use the original rendered template only
for zones it visibly demonstrates. Deliver the LaTeX package with explicit
unverified gaps. Do not report pixel equivalence.

## Reconstruction Order

Work outside in: page frame and columns; body text box and density; front
matter; headings; tables/figures; notes, furniture, bibliography, and
appendix. On a mismatch, repair the first failing layer rather than compensating
with local `\\vspace` adjustments.

## Run-Level Evidence And Coverage

Inspect visible Word text as contiguous run-format spans, not merely as whole
paragraphs. A span records its character range, text, direct formatting, and
effective formatting after style inheritance. This preserves local distinctions
such as a bold `Abstract` label followed by regular content, mixed title
emphasis, superscript author markers, and styled correspondence text.

Before rendering, create `source_feature_coverage.json`. For each observable
feature, mark it `mapped`, `needs_mapping`, or `not_observable`, and name its
editable LaTeX owner. Treat run typography, page frame, line numbers, page
furniture, title, abstract, headings, tables, figures, notes, references, and
appendix as separate features. Resolve priority source-backed gaps before
adjusting PDF margins, font metrics, or float spacing. A similarly named unused
Word style does not satisfy coverage for a visible source feature.

The normal package is a general class-based reconstruction, not a one-off
conversion of Word's sample text. Keep all policies in `journal-template.cls`
and demonstrate them in `main.tex` through named, editable interfaces.

## Handoff Claims

State only what the evidence supports:

- "Implemented from Word section and used-style evidence" is valid.
- "Visually checked against the populated Word fixture" is valid only after
  the same-content render comparison is saved.
- "Matches the journal template" requires source evidence for each claimed
  zone; otherwise name the default or unverified gap.
