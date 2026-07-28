# LLM Skill Evaluation

## Purpose

Use this protocol when measuring whether Temp2TeX improves an agent's actual
behavior. `run_regression.py` is not sufficient for this purpose: it is a
deterministic tooling baseline and does not execute a model.

## Paired Runs

For each evaluation, prepare the same official input folder and task prompt:

1. A **loaded-skill** run receives the Temp2TeX skill path and follows it.
2. A **baseline** run receives the same task and files without Temp2TeX, or a
   snapshot of the preceding skill version when evaluating a revision.

Save each run separately. Record model identifier, token count, duration, tool
availability, source files, and output paths. Do not compare an agent run with
a local script-only package and call the difference a skill improvement.

### Isolation and Prompt Control

The paired prompt must describe the user task, not the grading rubric. For
example: "Convert this official Word author template into an editable LaTeX
template package. Preserve requirements supported by the source and document
unresolved requirements." Do not add the required filenames, atomic-evidence
steps, audit order, rendering policy, or corpus restrictions to the shared
prompt; those are the behavior being measured.

Run the baseline in an isolated workspace containing only the fixed input
files and an empty output directory. It must not be able to read the Temp2TeX
skill directory, a checked-out Temp2TeX repository, prior generated packages,
or hidden evaluation rubrics. Give both runs the same model, tool inventory,
time limit, input hashes, and output path shape, except for the deliberate
skill injection. If the host cannot enforce this isolation, record the run as
`invalid_for_comparison`; it may still be a smoke test, but it is not evidence
that the skill improved agent behavior.

Before grading, record the exact shared prompt and a contamination check:
whether either run could access Temp2TeX scripts, references, prior outputs,
or the other run's directory. A baseline that discovers the installed skill or
repository is contaminated even if its final answer does not name Temp2TeX.

## Minimum Task Set

Use at least these three task shapes before claiming a behavior improvement:

| Task | Inputs | What it tests |
| --- | --- | --- |
| Word-only template | Official DOCX/DOTX plus author instructions | Granular Word evidence, defaults, class-based package, and no unrequested corpus run. |
| Incomplete source | Word/PDF/web guidance with missing rules | Source/default/gap separation and honest fallback. |
| Comparable source pair | Official Word and LaTeX template or renderable Word reference | Same-content comparison scope, image-interior masking limits, and audit before calibration. |

Include a Chinese or mixed-language case whenever the revision changes engine,
font, abstract, keyword, or CJK guidance.

## Required Grading

Grade outputs against observable evidence, not polish alone:

1. The delivered package contains editable `journal-template.cls`, `main.tex`,
   `references.bib`, assets, spec, gap log, and README.
2. The agent keeps paragraph/run/table/object evidence separate and records a
   source reference, default, or unresolved gap for every applicable zone.
3. The agent does not fabricate publisher rules, flatten an example article
   into the default template, or use a generic body setting to erase local
   formatting.
4. The agent uses `.cls` for reusable behavior and `main.tex` for editable
   metadata and fixtures.
5. An ordinary task does not start the corpus runner. A comparison task does
   not calibrate from unmatched fixtures, incomplete atomic audit, or masked
   table/caption/text regions.
6. Compile and visual claims match the tools that actually ran; unavailable
   checks remain explicit in the README and gap log.

For each criterion record `passed`, `failed`, or `not_applicable`, with a path
or source excerpt. Grade the baseline and loaded-skill runs independently
before comparing pass rate, quality observations, time, and tokens.

Save a compact evaluation record alongside the task fixtures. It must include
`evaluation_id`, task shape, input hashes, shared prompt, model and tool
environment, skill path/version, output paths, per-criterion grades,
contamination check, and one of `valid`, `invalid_for_comparison`, or
`incomplete`. Never aggregate an invalid run into a skill-quality score.

## Relationship To Corpus Regression

After a loaded-skill run changes Temp2TeX scripts or generation behavior, run
the affected deterministic corpus cases. Treat their result as a separate
engineering signal. A model run can establish that the skill steers reasoning;
a tooling baseline can establish that a code path compiles or a comparable PDF
fixture is stable. Neither result substitutes for the other.
