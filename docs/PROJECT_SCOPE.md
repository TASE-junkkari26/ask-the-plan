# Hackathon project scope and acceptance

Scope clarified on 14 November 2026. This is the project acceptance boundary and
applies to the architecture, capability backlog, frontend, and evaluation plans.

## The supplied dataset defines the target

**A system that works for the supplied dataset's question families, returns
source-supported answers, and makes them easy to verify satisfies the technical
scope.** The hackathon evaluation is treated as covering those demonstrated
families. Unknown question classes do not need to be anticipated as surprise
requirements.

Use the full supplied questions and source materials to define the required
object/property categories, operations, languages, formats, and counting or
measurement conventions. Prioritize implementation within that bounded set.
This includes the known harder IFC-Bench questions; they are not optional merely
because they are less frequent. See the [full dataset findings](../dataset/FULL_DATASET_FINDINGS.md)
for the observed domains and reference-data limitations.

Different wording or translations of a supported question remain the same task
family. Development/test splits and paraphrase checks measure reliability within
the supplied families; they do not imply that new classes, trades, regulations,
or document domains must be supported.

## Separate requirements from extensions

- Each required capability should identify supplied questions it enables. A
  missing executor for a known family is an implementation gap to track.
- Broader schema variants, general CAD/BIM support, automatic revision comparison,
  photo-to-model registration, and additional specialist models are extensions
  unless a supplied question needs them. Schema flexibility is not a requirement
  to implement every representable operation.
- Assets without question examples do not by themselves introduce new question
  classes. Archival handwriting and unasked object categories can be optional
  demonstrations; they do not justify an open-ended training or renderer backlog.
- Use the simplest computation and evidence presentation that answers the known
  task. A custom 3D engine is not an acceptance requirement when source properties,
  2D marks, schedules, or an existing viewer provide sufficient verification.

## Keep question scope and evidence honest

The finite task catalog is separate from the scope of an individual answer.
Image/PDF/DXF questions use the drawing/page/layout shown. IFC questions always
use the entire imported model, independently of storey filters, hidden objects
and section cuts in the viewer. Preserve explicit room/floor filters in the
question; a single floor is not evidence for a whole-model total.

An unasked per-image category is an unknown annotation, not a zero label or a new
evaluation class. Missing source properties, incomplete extraction, estimates,
and conflicting references still need explicit handling within the known tasks.
Record source-backed reference discrepancies instead of inventing facts to match
an erroneous answer.

Completion means checking the supplied families for answer correctness, scope,
units, inspectable evidence, multilingual consistency, and practical latency/cost.
Mock responses, schema validation, and selected happy-path examples alone do not
establish that coverage. Derive reusable facts from the source materials rather
than looking up supplied reference answers at runtime.
