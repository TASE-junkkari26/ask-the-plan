# Gemini Hydrogen for IFC questions and spatial reasoning

Implementation follow-up: independent IFC planner selection, text-only Hydrogen
planning, bounded source discovery/inspection, an exterior-door resolver and a
24-question/six-model offline comparison harness are now implemented. See
[IFC usage](IFC_QUESTIONS.md) and [evaluation commands](../experiments/ifc_planners/README.md).
Broad live model-quality comparison remains outstanding. The investigation
below records the earlier implementation state and the reasoning behind this work.

Investigated 14 November 2026 against checkout `9db07ec`, current official model
documentation, and three supplied IFC files. This is a recommendation and an
offline source-data investigation. No new model requests were made, credentials
were not inspected, and provider settings and application behavior were not changed.

## Recommendation

Evaluate `gemini-4-hydrogen` as an alternative IFC **query planner**, with optional
visual inspection in a later experiment. Keep IfcOpenShell as the IFC reader and
the existing validated executor as the source of computed answers. Current
evidence does not establish that Hydrogen is more accurate than the supplied
Nemotron deployment on IFC questions or exterior-door reasoning.

For “How many doors lead outside?”, the first improvement should be an explicit
exterior-door selection rule, source coverage reporting, and access to the
relevant property values and relationships. A stronger planner may choose those
rules more reliably, but cannot establish missing source information from the
same incomplete input.

## Current implementation

The implemented IFC path is described in [IFC questions](IFC_QUESTIONS.md):

1. The original IFC is uploaded to the local backend when a question is asked.
   IfcOpenShell extracts entities, scalar properties/quantities, relationships,
   units and source anchors.
2. [Catalog construction](../ifc_api/service.py#L187) sends bounded source
   vocabulary and selected metadata to the language model. It does not send the
   raw IFC, meshes, object placements, screenshots or a complete room-door graph.
3. [Planning](../ifc_api/service.py#L225) asks Nemotron for a validated
   `PlanProposal`. The CPU engine executes the plan; the final explanation is
   assembled from executed source values.

Hydrogen is already implemented for image candidates, but
[`IMAGE_API_PROVIDER=gemini` does not change IFC planning](../image_api/app.py#L145).
The [Gemini client](../gemini/client.py#L174) currently requires a prepared PNG;
it has no text-only IFC planner method. Its [configuration](../gemini/config.py#L23)
accepts only low thinking. An IFC comparison needs a separate planner adapter and
configuration rather than changing the image selector.

Source discovery is a shared limitation. Ordinary door/type labels and property
values can be absent from the bounded catalog; searches rely on narrow literal
matches. The [object-discovery investigation](IFC_OBJECT_DISCOVERY.md) reproduces
these gaps and proposes bounded search/inspection. A model's larger context window
does not automatically remove the application's current catalog restrictions.

## What public model evidence supports

| Question | Finding | Consequence |
| --- | --- | --- |
| Is Hydrogen a usable candidate? | Google's specification documents text/image/PDF input, native function calling, structured output, and a unified 1,048,576-token context. | It can support a structured planner and a separate visual inspection experiment. |
| Does it natively execute IFC geometry? | The documented input modalities do not describe an IFC semantic or geometry engine. STEP records can be represented as text, but that does not establish exact object membership or geometric computation. | Keep native parsing, topology and calculations. |
| Is its reasoning setting fixed? | Hydrogen supports low, medium, high and xhigh; high is the default. | Compare low and higher reasoning settings explicitly; the existing image-only low setting is not an IFC quality result. |
| Is long context unique to Hydrogen? | NVIDIA also advertises up to 1M context for Nemotron 3.5 Super VL, subject to deployment configuration, and configurable thinking. | Context length alone does not justify a replacement. The supplied Verda deployment's actual limit has not been measured here. |
| Is there a direct spatial-quality comparison? | I found no Hydrogen-versus-Nemotron IFC/exterior-door comparison in their published evaluations. | General agent, graph or image benchmark scores cannot establish superiority on this task. |

Sources: [Hydrogen specification](https://aistudio.google.com/docs/models/gemini-4-hydrogen),
[Hydrogen reasoning guidance](https://aistudio.google.com/docs/whats-new-gemini-4-hydrogen#understanding-thinking-levels),
[Hydrogen model card](https://deepmind.google/models/model-cards/gemini-4-hydrogen/),
and [NVIDIA's model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-BF16).
These are provider descriptions and evaluations, not a project-specific result.

My inference is that Hydrogen could improve question interpretation, multilingual
source-vocabulary matching, and composition of supported relationship queries.
Its visual capabilities could also help review a supplied plan or a localized
door view. Neither benefit has been measured for this project's IFC questions.
The current text-only IFC prompt would not exercise visual spatial reasoning.

## What “doors lead outside” needs

Define the requested grain as distinct fitted door occurrences/openings, including
a double-leaf door as one doorway. Keep the selected view/model scope explicit.
Clarify whether outdoor balconies, terraces and courtyards are included when that
choice changes the answer. An external door is not automatically a certified fire
exit or a verified accessible escape route.

There are two useful native evidence paths:

- **Recorded exterior classification:** inspect `Pset_DoorCommon.IsExternal`,
  including inherited type values and occurrence overrides. Its official meaning
  is exterior use/facing outside, rather than an independent proof of traversable
  outdoor access. Missing values remain unknown. See
  [buildingSMART's property definition](https://raw.githubusercontent.com/buildingSMART/IFC4.3.x-development/master/docs/properties/i/IsExternal.md).
- **Recorded outdoor connection:** follow a PHYSICAL, EXTERNAL space boundary to
  an `IfcDoor`, or to an opening explicitly filled by a door. Preserve the room,
  door and relationship identities and count distinct doors. Space boundaries can
  be logical without attached geometry; EXTERNAL can include a terrace. See
  [buildingSMART's boundary definition](https://raw.githubusercontent.com/buildingSMART/IFC4.3.x-development/master/docs/schemas/core/IfcProductExtension/Entities/IfcRelSpaceBoundary.md).

The engine already extracts the relevant relationships. However,
[`outdoor_access`](../ifc_engine/spatial.py#L108) currently returns distinct
**rooms**. Its result cannot be counted as doors: a room can have several outdoor
doors, and multiple rooms or boundary records can refer to one door. Property
filters and explicit supported traversals can answer suitable source-specific
cases. A dedicated exterior-door resolver would make the mixed door/opening
paths, deduplication, evidence and incomplete coverage consistent across models.

There is also a source-proof gap in generic relation filtering:
[`related_to`](../ifc_engine/engine.py#L479) checks graph membership without
retaining the relationship's edge anchors. A local FZK direct-boundary door query
returned two doors but only object anchors, with no boundary-relation anchors.
The reusable rule should retain the actual boundary/fill proof, as the existing
room-topology executor does. Changing the language model does not fix this.

Where metadata/topology is absent, geometric reasoning would need additional
source access: door openings, room/exterior boundaries and building-envelope
geometry in a common coordinate frame. A model could help choose or review those
operations. Guessing from an orbit-camera screenshot would miss occluded doors
and does not provide a complete inventory. Keep inferred geometric classifications
separate from recorded properties and expose ambiguous cases.

## Offline checks on actual supplied files

Used Python 3.14.10 and IfcOpenShell 0.9.0.post1. Counted `IfcDoor` occurrences,
read `Pset_DoorCommon.IsExternal` with occurrence/type inheritance, and followed
exact PHYSICAL + EXTERNAL door/filled-opening boundary paths. Deduplicated paths
by door STEP ID. No geometry, QA reference answers or model inference were used.

| Supplied model | All door occurrences | IsExternal true / false / missing | Distinct doors with external-boundary evidence |
| --- | ---: | --- | ---: |
| FZK-Haus (`kit-fzk-haus_ac20-fzk-haus.ifc`) | 5 | 0 / 0 / 5 | 2 |
| Esplanades (`bsc-esplanades_1807-ep-ar-v18.ifc`) | 211 | 5 / 170 / 36 | No boundary records available |
| Dental clinic architecture (`dental_clinic_arc.ifc`) | 254 | 18 / 236 / 0 | 12 |

Interpretation:

- FZK-Haus supports two distinct doors through boundary evidence despite every
  door lacking the common exterior-classification property.
- Esplanades supports five doors explicitly labeled external, while 36 doors
  lack that classification. Five is not established as the complete outdoor-door
  total. Missing boundary records cannot establish zero outdoor doors.
- The dental architectural model has 18 exterior-classified doors. All 12 doors
  supported by the external-boundary path are among those 18; six flagged doors
  have no such path. The boundary paths involve 14 distinct rooms. Therefore 18
  flagged doors, 12 boundary-supported doors, 14 rooms and raw boundary counts
  answer different questions. The unequal sets alone do not prove contradictory
  source facts or establish a physical total.

The dental file checked here is the architectural model, not the previously
problematic `dental_clinic_mep.ifc`. These three selected examples are not a corpus
accuracy estimate or independent verification of physical exterior doors.

Source identities, all relative to `dataset/junction-dataset/data/`:

| Path | SHA-256 |
| --- | --- |
| `ifc_models/kit-fzk-haus_ac20-fzk-haus.ifc` | `70cc8ff245fc0894201d96496c031005a5cbd7a96b22d8a1b87c5a883fb77994` |
| `ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc` | `b97db10a2cb679a6543ccf4e34cfa8e77753f14e67f51b403e6cd9a819e3748f` |
| `ifc_bench/dental_clinic_arc.ifc` | `b90fe57b8aa9329d762a564770e697d4f7357677484e3a78ede4ab6d2163c0c0` |

The local investigation helper and identity/path report are retained under the
ignored `build/gemini-ifc-assessment/` directory. With that helper present and an
IFC-enabled interpreter, reproduce from the repository root:

```sh
python build/gemini-ifc-assessment/probe_native_exterior.py --output build/gemini-ifc-assessment/native-exterior.json
```

## Comparison worth implementing

1. **Define and verify the exterior-door resolver first.** Return included doors,
   excluded doors, unknown classifications, supporting native paths, and source
   disagreements without silently treating missing data as false. Keep distinct
   door and room grains and exact captured scope. Include the three examples
   above, duplicate boundaries, double leaves and missing/contradictory fixtures.
2. **Add an independent IFC planner provider interface.** Keep image selection
   separate. Add a text-only Hydrogen request to the existing transport, retain
   the same `PlanProposal`, validators, executor and evidence mapping, and record
   the actual planner/model/configuration. Gemini's JSON Schema subset needs a
   compatible representation of the nested plan; preserve full local validation.
3. **Separate model quality from source-access quality.** First compare identical
   question/catalog/scope inputs. Then give both providers the same bounded source
   discovery/inspection actions. Attribute improvements from retrieval separately
   from improvements from changing providers.
4. **Use a small paired evaluation.** A proposed starter is 24 questions across six
   source/fixture models, covering class/property counts, exterior-door versus
   outdoor-room grain, adjacency/connectivity, and missing/ambiguous information.
   Include English/Finnish paraphrases and exact-view versus explicit model scope.
   Keep repeated/translated project cases in one split; references stay evaluator-only.
5. **Compare reasoning settings and executed outcomes.** Start with the current
   Nemotron baseline, a bounded thinking-enabled Nemotron variant where the
   deployment supports it, and Hydrogen low/high; add medium if that tradeoff is
   useful. Preserve supported provider semantics and record actual settings rather
   than assuming equal sampling parameters. Score exact included door identities,
   scope, source support, omissions/duplicates, proper missing-data outcomes,
   invalid plans, total time and usage including thinking. A matching total with
   the wrong objects is a failure. Additional visual inputs are a separate experiment.

Promote Hydrogen for a task when paired checks improve source-backed answers or
reliability at acceptable latency/cost. Keep simple deterministic class/property
questions on the strongest measured economical path. No automatic second-provider
call or wholesale migration is justified by the currently available evidence.

Current paid Hydrogen pricing is $1.50 per million input tokens and $7.50 per
million output tokens; thinking is included in output charges. Account quotas,
free access and this project's effective cost still require separate accounting.
See [Google pricing](https://aistudio.google.com/docs/pricing#gemini-4-hydrogen).
The existing Nemotron and Hydrogen smoke records used different tasks/settings
and do not establish a latency or accuracy ranking between providers.

Verification for this investigation consists of the offline source probe, code
inspection, official documentation review and Markdown/whitespace checks. There
was no head-to-head model evaluation and no change to runtime configuration.
