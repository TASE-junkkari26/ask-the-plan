# IFC object discovery investigation

Initial investigation on 14 November 2026. Follow-up implementation now provides
per-session source metadata indexing, automatic retrieval/facets and bounded
search/property/fact/relationship inspection shared by Nemotron and Hydrogen.
See [current behavior](IFC_QUESTIONS.md). Exhaustive-selection handles, broader
semantic retrieval and the remaining design below are **proposed**. The historical
probes used local source models and no credentials; they did not measure live
planner interpretation accuracy or the deployment's context-window limit.

Current discovery normalizes Unicode and case for matching while retaining
literal source values, fact/anchor references and explicit truncation. Entity
discovery and inspection stay within the captured inventory, and the initial
catalog reports spatial prerequisites. Large catalogs reduce general labels and
property definitions with explicit truncation instead of rejecting every question
at the former property-count cap. One invalid schema/reference/shape proposal can
be repaired against the same source and scope within the shared request/deadline
caps. Search samples remain candidates, not proof of complete selection. The
older limitations and catalog sizes below record the original probes.

The recommended change is a searchable source-metadata index with a bounded
discovery loop before final query execution. Keep the complete IFC and answer
computation on the backend. Give Nemotron ways to discover the model's actual
vocabulary and inspect candidate facts without knowing full source names first.

The integration at the time of those probes followed this path:

1. The [question panel](../frontend/src/components/IfcQuestionPanel.tsx#L139)
   captures the selected scope and uploads the original IFC when first asked.
   The backend verifies its SHA-256 and creates a temporary extracted session.
2. The [extractor](../ifc_engine/ingest.py#L229) builds a `KnowledgeBundle` of
   entities, scalar facts, units, relationships and source anchors. Geometry is
   not placed in the planning prompt. `Name`, `LongName`, `Description`, `Tag`,
   `ObjectType` and `PredefinedType` are retained where available. Occurrence
   properties override inherited type properties, including explicit nulls.
3. [Catalog construction](../ifc_api/service.py#L187) sends class counts,
   concepts, property definitions, selected entity labels, literal name/ID
   matches, relations, units and bounded project/site/building metadata.
4. [One Nemotron request](../ifc_api/service.py#L225) proposes `PlanProposal`
   JSON. The server builds a source-bound `QueryPlan`, enforces exact view
   membership, validates it and executes supported operations locally.
5. The response contains computed values, included/excluded source entities,
   facts, anchors and calculation inputs. Its narrative is assembled
   deterministically; there is no second inference call for the final prose.

This sequence records the earlier implementation. The README, repository
instructions and IFC question guide describe the current provider-independent
planning and discovery loop.

The original discovery gaps were narrower than an inability to query IFC without names:
class-based queries already work without object names. They become relevant
when a question requires a function, named subset, type or property value.

| Behavior at investigation | Consequence |
| --- | --- |
| Ordinary element/type labels are absent from the general entity list. It includes project, site, building, storey, space, system, zone and material labels, capped at the first 1,000 entries. | Door types and equipment labels can be unavailable even when the source contains them. The truncation flag reports omission but provides no pagination. |
| `matching_elements` requires a complete source label in the question, a matching token containing a digit, or an explicit STEP/GUID locator. Only the first 100 matches are sent. | A natural partial phrase without digits, such as “single-flush doors”, can miss every relevant object. There is no ranked search over description, type or property values. |
| Property definitions are sent, but ordinary element property values are not. | The model knows a field exists without seeing how functions, types or categories are actually encoded in that field. |
| More than 2,000 properties or 250,000 serialized catalog characters rejects planning. | Larger vocabularies cannot be explored in bounded pages. The character bound is not a measured token budget for the complete prompt and schema. |
| [`resolve_entity`](../ifc_engine/engine.py#L125) uses exact case-folded labels/IDs. Executable text `eq` and `contains` are literal and case-sensitive. The `label` field reads only the first label, usually `Name`. | A semantically plausible filter can select nothing because its spelling, case or field differs from the source. `LongName` is a separate property, even though both names appear in catalog labels. |
| Planning is one request followed by execution. | Nemotron cannot inspect candidates or property values, refine its search, or repair a source-resolution failure during that question. |

These behaviors were reproduced with the supplied preview files. Counts below
describe source records or diagnostic selections, not reference-answer lookups.

| Local probe | Observed result |
| --- | --- |
| Duplex: source names containing `M_Single-Flush` | 12 `IfcDoor` occurrences; example STEP `#125`, `M_Single-Flush:0762 x 2032mm:0762 x 2032mm:204034`. |
| Duplex: `_catalog(..., "Show the single-flush doors.")` | Zero `matching_elements`; the general entity list also contains no single-flush label. Even “Show the M_Single-Flush doors.” returns zero matches. |
| Duplex: `_catalog(..., "Show #125.")` | One matching element. |
| Duplex: door `label contains "single-flush"` versus `"M_Single-Flush"` | The executor returns 0 versus 12 for these different literal predicates. This demonstrates why resolution must preserve the actual source spelling. |
| Duplex: recorded-function probes over spaces | `label contains "Bathroom"` returns 0; `LongName contains "bathroom"` returns 0; `LongName contains "Bathroom"` returns 4. All probes explicitly restrict to present fields. The four bathroom labels are already visible in the small model's general catalog. |
| AC20: “Which rooms are meeting rooms?” | Zero `matching_elements`, although two spaces have `LongName` values `Besprechungsraum I` and `Besprechungsraum II`. Both are present in the general catalog, so a multilingual model could still resolve them. This is not proof of a live model failure. |
| Temporary SQLite FTS5 prototype over extracted `Name`, `LongName`, `Description`, `ObjectType` | `single AND flush`, restricted to `IfcDoor`, retrieves all 12 source occurrences; `bathroom`, restricted to `IfcSpace`, retrieves all four bathroom records. No model call or production change was involved. |

The duplex bundle contains 351 entities and 351 property definitions; AC20 has
1,217 entities and 982 property definitions. The duplex catalog for the
single-flush question is 69,219 JSON characters, before system instructions and
the proposal schema. These observations establish specific discovery gaps, not
a frequency estimate for incorrect answers.

The proposed implementation has five parts:

1. **Index extracted metadata once per model session.** Build an index alongside
   `_Model`, using existing entities/facts/relations. Search source names,
   `LongName`, description, tag, object/predefined type, relevant scalar property
   values, type labels and source-backed container/system/material labels. Keep
   each hit's entity ID, field/property key, literal value, status, fact/anchor
   references and relationship basis. Classification associations are not
   currently extracted; do not advertise them as searchable source facts.

   Start with exact identifier maps, Unicode case-folded text search, token and
   prefix matching, and a small multilingual concept/alias vocabulary for the
   supplied families. SQLite FTS5 is an available local option; an in-memory
   inverted index is also sufficient. FTS tokenization alone does not translate
   German/Finnish labels or establish semantic equivalence. Keep literal IDs
   such as `121.A`, `7.16`, GUIDs and STEP locators in a separate exact channel;
   punctuation-sensitive identifiers must not depend on full-text tokenization.

   Use aliases to retrieve suggestions while preserving original source text.
   “Meeting room” may suggest `Besprechungsraum`; “server room” must not silently
   treat every generic technical room as equivalent. Keep toilet fixtures and
   toilet rooms distinct. Add multilingual embeddings only if evaluation exposes
   remaining recall gaps. If used, embed compact metadata records or distinct
   type/function values and use similarity only to propose candidates.

2. **Replace the fixed catalog dump with bounded discovery actions.** Supply a
   small initial summary of relevant classes/concepts and capabilities. Search
   property paths and expose source-value facets on demand, including present,
   null and not-extracted status counts. Return literal values, matching fields,
   representative source identities, totals and explicit truncation/cursors.
   Give repeated type/function values one vocabulary entry with occurrence
   membership on the backend, rather than repeating thousands of names.

   Three typed actions are enough initially: `discover` searches entities,
   property paths and value facets; `inspect` reads bounded candidate facts and
   native relationships; `resolve_selection` validates a proposed source rule
   over the full authorized inventory. The latter returns a preview and a
   server-held selection handle only when the full rule can be evaluated. A
   ranked or semantic search result is always a candidate list, even if every
   returned hit was inspected.

3. **Allow a short discovery/refinement loop.** Run cheap retrieval before the
   first planning call, so straightforward class counts can retain one model
   request. Let unresolved questions request discovery/inspection and then
   produce their final proposal. Start with at most three model requests and
   six action executions under one end-to-end planning deadline; cap samples
   and total prompt/tool tokens, including schemas and message history. These
   are proposed bounds to tune, not measured latency or cost claims.

   The existing [Nemotron transport](../nemotron/client.py) accepts tool-call
   parameters but never executes tools. Its current IFC integration does not
   use them. Implement orchestration in `ifc_api`, with allowlisted, validated
   arguments. Native provider tool support has not been verified here; a typed
   JSON action envelope over the existing JSON request path can implement the
   same loop without depending on that support. No arbitrary code or SQL is
   needed in model output.

4. **Resolve discovery into exhaustive engine selection.** For a count or sum,
   the backend must evaluate the confirmed source predicate over every eligible
   object. A top-20 retrieval list is never the universe to aggregate. Prefer
   existing concept/property predicates using original literal values. Where a
   complete resolved set is necessary, keep it behind a server-held handle and
   compile it into the existing typed `entity_id in [...]` predicate; the model
   need not copy every ID into its context. The final exported `QueryPlan`
   remains concrete and replayable. Handle support is proposed internal planner
   work, not an existing contract or executor operation.

   Return `needs_clarification` when candidates have materially different
   meanings. Report missing fields or unextracted data using the existing
   non-answer/coverage outcomes. An empty search result does not establish zero.
   A supported class with a fully evaluated empty source inventory can still
   legitimately count as zero. Preserve count grain, hierarchy policy, units,
   quantity basis, included/excluded sets and calculation inputs.

5. **Bind discovery to the captured source and scope.** Filter candidate answer
   membership by the exact submitted view inventory, and bind selections to
   model session, source hash, scope fingerprint and index/alias versions.
   Purge handles and indexes with their sessions. Supporting type metadata must
   remain identified as metadata; it must not introduce hidden type objects or
   their occurrences into an executable view-scoped traversal. Use already
   extracted occurrence facts where possible, and preserve the executor's
   existing scope checks for any required related objects. A discovery action
   cannot broaden the UI scope. Source labels and retrieved text remain data.

For example, an English bathroom question would retrieve the source function
field `LongName` and its literal `Bathroom 1` / `Bathroom 2` values, resolve the
intended room category, and execute a selection over all in-scope spaces using
that source rule. Its final count still comes from the IFC engine and includes
the four relevant source identities only if all four belong to the captured
scope. A named door-type question similarly discovers `M_Single-Flush` before
building a source-correct predicate.

Implement the metadata index and automatic retrieval first, then add refinement
actions and exhaustive-selection handles. Keep the independent IFC CLI and
existing deterministic query semantics. The main changes belong in a new
discovery module and `ifc_api/service.py`; shared contracts and generated outputs
need updating only if new public wire types are introduced. Record resolution
rules, source facts, searches, truncation and clarification choices alongside
execution evidence so retrieval mistakes can be investigated.

Acceptance should use the supplied families in the
[question catalog](QUESTION_CLASSIFICATION.md#exhaustive-wording-and-template-catalog):
room/function inventories and bathroom counts, named-room quantities, door/type
inventories and fire-rating availability, material/property questions and
equipment locations. Check paraphrases and translations within those families;
do not build a runtime lookup from their reference answers. In particular,
verify partial type names, `Name` versus `LongName`, German/Finnish wording,
duplicate room labels on different floors, IFC2X3 type-derived concepts,
catalogs beyond the current sample limits, unknown versus zero, and unchanged
revision/view/evidence handling. Evaluate selection precision/recall separately
from final answer accuracy, evidence correctness, calls/tokens and latency.

The local probes used Linux Python 3.12.3, IfcOpenShell 0.9.0.post1, Pydantic
2.14.3 and SQLite 3.45.1 with FTS5. They exercised the actual `_catalog` and
`execute` methods on the supplied preview IFCs. The temporary full-text prototype
used parameterized queries against an in-memory index; it is not a shipped
retrieval component. No credentials or live inference were required.

The existing engine and exact-scope checks passed: 29 tests, including the real
Esplanades model/floor counts, with:

```sh
.venv/bin/python -m unittest tests.test_ifc_engine tests.test_ifc_api.ExactScopeEngineTests -q
```

The standard combined asynchronous API test run stalled in this execution
environment and was interrupted. A bounded single-test diagnostic also timed
out; a diagnostic event-loop timer allowed it to progress through thread waits.
Running `tests.test_ifc_api` and `tests.test_ifc_spatial_api` with a temporary
in-process event-loop policy scheduling a no-op timer every 20 ms passed all
32 checks in 3.779 seconds. This changed only the temporary test runner, with no
repository or application changes. Those checks use mocked provider responses;
they verify HTTP/planning/execution/evidence integration under that runner,
not live Nemotron interpretation. The normal asynchronous runner did not pass
as invoked, and the timing is not a production latency measurement.

The documentation link checker passed with zero errors, and `git diff --check`
passed. Frontend/browser checks were not run for this documentation-only change.

Implementation options were checked against the primary
[IfcOpenShell selector documentation](https://docs.ifcopenshell.org/ifcopenshell-python/selector_syntax.html)
and [element utilities](https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/element/index.html),
which describe attribute/property/type access, and
[SQLite FTS5 documentation](https://www.sqlite.org/fts5.html), which describes
Unicode tokenization, prefix/substring indexes and ranking. They support the
proposed building blocks; neither establishes semantic selection completeness
or replaces this project's scope and evidence validation.
