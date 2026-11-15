# Raster hardening: fresh 50-question baseline and failure review

15 November 2026. Development evaluation of Detailed scan, source review and paired
prompt trials. This measures **candidate-list count agreement**, not final-answer
accuracy, verified membership or complete localization. References remain unchanged.

## Sample and baseline

Seed `2026111501` selected 50 fresh questions on distinct drawings: 37 CubiCasa images
and 13 Swiss plans, across 16 question families, using the answer-blind random sampler.
Input PNGs and code were frozen before inference; references were accessed after all
outputs were saved. The count-only sample does not evaluate measurements or IFC.

Detailed scan used automatic routing and normal tile/call budgets. All 50 selected
Hydrogen: 50 Decisions calls and 75 Hydrogen calls, all with complete usage and no
transport retries. Peaks were 24 concurrent questions and 26 provider calls. The
isolated evaluation server was separate from the user's workbench.

| Measure | Baseline |
|---|---:|
| Exact reference-count matches | 39/50 |
| Matches with status `ok` | 37/50 |
| CubiCasa / Swiss matches | 28/37 / 11/13 |
| HTTP 200 responses | 50/50 |
| Result status | 47 ok, 3 partial |
| Wall time; median / p95 question | 34.01 s; 9.22 / 16.68 s |
| Nominal standard-rate cost | $0.804803 |

Costs use recorded token tariffs, include thinking, and precede credits, discounts
and taxes; they are estimates, not invoices. All five window cases mismatched.
Ten of eleven mismatches returned `ok`; this did not establish correct inventories.

## All eleven baseline mismatches

Boxes are approximate `[xmin,ymin,xmax,ymax]` pixels in the frozen input PNG.
These are agent reviews, not human labels or replacement references. Local CubiCasa
has no instance SVG annotations; some counting-grain disagreements remain unresolved.

| Case | Family | Reference | Detected | Source review |
|---|---|---:|---:|---|
| Q007 | Showers/baths | 3 | 2 | Confirmed omitted wall shower in upstairs KH; bathtub and downstairs tray detected. |
| Q008 | Windows | 17 | 15 | Multi-section glazing has incomplete bounds; reference division into instances remains uncertain. |
| Q010 | Doors | 5 | 8 | Visible sliding/context doors create a scope or annotation-grain conflict. |
| Q016 | Showers/baths | 1 | 0 | Toilet false positive correctly rejected; probable actual shower remains obscured and unproposed. |
| Q018 | Windows | 24 | 13 | Eight thin glazing frames omitted; source also contains three duplicate window records. |
| Q020 | Showers/baths | 1 | 0 | Confirmed omitted wall-mounted shower without a tray. |
| Q022 | Balconies | 0 | 1 | Visible labelled balcony contradicts supplied zero. |
| Q032 | Doors | 66 | 50 | Dense-symbol omissions plus eleven excess duplicate source door records. |
| Q034 | Windows | 4 | 3 | Three clear right-side windows; possible fourth feature on left remains unresolved. |
| Q041 | Windows | 24 | 20 | Two floor depictions contain small openings and glazing/door/module ambiguity. |
| Q042 | Windows | 13 | 8 | Eight broad assemblies detected; independently framed subunit grain is unresolved. |

**Q007 — `high_quality_architectural-5642.png`.** The upstairs KH includes a small
wall-mounted shower below its basin and left of the WC, near `[607,250,634,270]`.
It is separate from the detected bathtub and downstairs shower tray. Requiring a
tray/enclosure misses this visible shower. A wet-room wall sweep is a bounded
hypothesis; room labels alone must not create fixtures.

**Q008 — `high_quality_architectural-14881.png`.** Several boxes cover only parts
of long glazing. East MH glazing extends approximately `[995,550,1013,735]`, while
the returned box ends at y614. North OH also has multi-section glazing. This is
a localization problem regardless of count, but the lack of instance annotations
prevents certifying how the reference17 divides connected frames. A narrow west
PUK/KHH opening around `[123,550,142,605]` has a swing arc; adding it as a window
to reach17 would introduce a likely wrong category.

**Q010 — `high_quality_architectural-4912.png`.** Rotating for review reveals A22's
five swing doors, its VH sliding door labelled `LIO7`, an adjacent-unit entrance and
a clipped common double door. Reference 5 may exclude sliding/context doors, but the
question has no A22 restriction. Do not silently narrow the view or suppress sliding
doors to match. The clipped door retains a partial warning; its membership check
supported the visible doorway.

**Q016 — `high_quality_architectural-11299.png`.** The initial shower hypothesis
at `[64,308,124,344]` is a toilet, and membership verification correctly rejects
it. A probable wall-mounted shower elsewhere in PH4.1, near `[65,245,100,280]`,
is obscured by dense plumbing overprint. Its identity needs qualification. The
failed inventory should not be repaired by restoring the rejected toilet or by
treating pipe-size labels such as KV/V as fixture evidence.

**Q018 — `site11860_bldg18507_floor50412.pdf`.** Thirteen detections cover ordinary
windows. Source registration identifies eight omitted thin glazing frames on
balcony/living-room and loggia boundaries, only 3–4 source pixels thick. Paired DXF
has 24 window outlines but **21 distinct coordinate outlines**: three occur twice
at identical coordinates. Improving real omissions must not require inventing 24
physical windows. The proposer also sent the legend; its detector returned zero,
consuming an extra call.

**Q020 — `high_quality_architectural-8796.png`.** KPH302 has an observable
wall-mounted fitting and nearby square floor drain around `[70,365,122,401]`.
There is no tray or enclosure. This is a clear missed shower; a drain alone
would not establish one.

**Q022 — `high_quality_architectural-8371.png`.** The drawing visibly labels a
`PARV` balcony with a railing/boundary and access. The detected one is supported
by that source; the supplied zero is a suspected annotation/reference conflict.
Retain the mismatch in the benchmark instead of removing the balcony to match.

**Q032 — `site417_bldg1060_floor4636.pdf`.** The dense plan was inspected in one
native crop. Paired DXF review finds 66 door outline records but **55 distinct
coordinate outlines**: seven openings occur twice and two occur three times.
Baseline50 therefore has a net deficit of five relative to distinct source
geometry, not sixteen established missing physical doors. Examples without
baseline overlap include `[893,598,921,620]` and `[902,1277,928,1313]`.
Other placements also need review; matching55 would not prove localization.

**Q034 — `high_quality_architectural-233.png`.** Three right-side garage windows are
clear. A narrow hatched left-side feature might explain the fourth, but its class
is unresolved. Do not manufacture a candidate from the reference value.

**Q041 — `high_quality_architectural-1967.png`.** Two floor depictions mix small
windows, glazed doors and adjacent frame modules. The four-count deficit needs
instance-level adjudication; omissions/grouping are not yet established causes.

**Q042 — `high_quality_architectural-1485.png`.** Eight broad wall assemblies versus
reference 13 suggests grouping framed subunits too broadly. Counting every mullion
or pane is also unsafe; no definitive replacement instance inventory was made.

Offline audit `experiments/runs/raster-hardening-20261115/swiss-source-audit.json`
records source hashes, duplicate handles and registration landmarks. Neither DXF
geometry nor QA answers entered runtime; original assets/references remain unchanged.

## Rejected prompt trials

Both trials reused exact baseline questions/PNGs and retained correct controls in
the denominator. These development trials are not an independent held-out accuracy
estimate; stochastic variation remains possible.

| Trial | Matches | Repaired | Regressed | Nominal cost |
|---|---:|---:|---:|---:|
| Baseline | 39/50 | — | — | $0.804803 |
| Broad prompt revision | 38/50 | 2 | 3 | $0.901448 |
| Refined prompt revision | 38/50 | 1 | 2 | $0.801306 |

Neither prompt revision passed the no-regression comparison, so neither is
credited as an accuracy improvement. The cheaper refined trial still lost a net
match. Detailed scan becoming the UI default is a product preference, not proof
that every extra crop or model call improves correctness.

## Additional double-door control

`D001`, the user-shown `colorful-6451.png`, has supplied count12 and detected
count11; this remains a count mismatch. Independently, the lounge/ET double-leaf
door occupies roughly `[610,365,658,444]`, while the screenshot's candidate9
encloses only its lower leaf. One doorway still needs one box covering both
leaves and swing evidence. Count agreement alone would not detect that defect.

## Final retained changes and results

The drawing question panel now always uses Detailed scan; its checkbox is removed.
The explicit full-image API remains available. Gemini configuration is required
for the workbench's detail tools.

The retained detection policy uses `ultra_high` image-reading resolution only
for fitted-door detail requests. Declared layout target `door` selects it; the
small-source path has a conservative, anchored multilingual door-count lead-in
hint. Other target kinds and unrelated/quoted door labels preserve the default
payload. Layout, routing, membership and IFC transports keep their prior visual
settings. The detector prompt itself is restored to baseline. The layout prompt
now avoids selecting an isolated symbol legend as an object-inventory region.

| Same50 measure | Before | Retained policy |
|---|---:|---:|
| Exact reference count matches |39/50|40/50|
| Strict `ok` count matches |37/50|39/50|
| Repaired / regressed |—|1 / 0|
| Actual provider attempts, including routing |125|118|
| Nominal cost |$0.804803|$0.764502|
| Median response |9.22s|10.14s|
| Total inference wall time |34.01s|41.17s|

All 50 HTTP requests succeeded in both runs. Candidate-count agreement is not final
answer or localization accuracy. Q016 supplied the additional match, but its
fixture request did not receive increased resolution; stochastic variation can
explain that change. No fixture-accuracy improvement is attributed to the door
policy. Reduced legend work is recorded in actual call ledgers.

D001's double-leaf box changed from `[609.28,382.32,654.08,425.52]` to
`[613.12,367.92,656.64,443.52]`, covering both leaves. Its total remains 11 against
reference 12. No artificial extra leaf/door was inserted to match the reference.

A rejected global-resolution trial had 40/50 matches (two repaired, one
regressed), cost $0.824895 and 120 provider attempts. Three repeated comparisons
confirmed its shower regression: Q009 returned the reference 1 in 3/3 original
attempts, but 2 in 3/3 global-resolution attempts. Q016 and Q020 matched in all
three repeats under both settings. This motivated the door-only restriction;
repeats are diagnostics, not retries or best-answer selection.

## Additional 40 drawings

A further 40 distinct sources were selected with seed `2026111540`, excluding
all initial 50 source paths: 33 CubiCasa and seven Swiss drawings. Both original
and final pipelines ran on identical frozen PNGs and questions. No policy,
threshold or prompt changed after these validation results were inspected.

| New 40 measure | Original | Retained policy |
|---|---:|---:|
| Exact reference count matches |25/40|25/40|
| Strict `ok` matches |25/40|25/40|
| Repaired / regressed |—|1 / 1|
| Provider attempts |89|94|
| Nominal cost |$0.515014|$0.551540|
| Inference wall time |22.51s|34.20s|

Q039 recovered a real missed entrance door (11 to reference 12). Q040 lost two
real balcony glazing panels (8 to 6). Its recorded question, system instruction,
schema, image hash, model settings and omitted default resolution were identical
before and after: retain this observed loss, while distinguishing stochastic
variation from a causal effect of the door-only setting. All 80 HTTP requests
succeeded. There are 15 remaining mismatches; the union of before/after failures
contains 16 cases, reviewed below.

Across both sets, exact agreement was 64/90 before and 65/90 after. Total nominal
cost was $1.319817 before and $1.316042 after, effectively flat. These small,
variable development results do not establish a broad accuracy improvement.
The retained benefit is the demonstrated door localization correction and fewer
unnecessary legend calls, with fixture resolution preserved after repeat tests.

### First-half validation mismatch source review

The following eight baseline mismatches have the same predicted counts before
and after the retained policy. Reviews happened after both inference runs were
complete and did not change runtime prompts, thresholds or reference values.
IDs below belong to the new 40-case set, independently of the earlier 50 IDs.

| Case | Family | Reference → before/after | Observed mechanism and qualification |
|---|---|---|---|
| Q002 | Kitchens | 1 → 2/2 | Two visible `KK` kitchenettes are detected. One belongs to the pink-outlined main apartment; the other is adjacent-unit context outside that outline. The reference likely scopes to the outlined unit, although the question does not explicitly say so. This is a scope/annotation conflict, not a duplicate kitchen hypothesis. |
| Q007 | Bedrooms | 0 → 1/1 | The model calls an enclosed room a bedroom from its door, window and built-in closets. No `MH` label or bed was identified in the returned cue. Membership is inferred rather than visibly labelled; the source alone does not resolve whether an unlabeled bedroom annotation is missing. |
| Q008 | Swiss doors | 19 → 15/15 | Paired DXF has 19 five-vertex doorway outlines but only 15 unique coordinate sequences, alongside 19 leaf lines and 19 arcs. Four excess source outlines are duplicates. Detected 15 agrees with distinct-source geometry count; forcing 19 would duplicate physical hypotheses. This count agreement does not certify every box. |
| Q009 | Sinks | 2 → 3/3 | Detections are a double kitchen sink, a small main-floor WC basin, and a basement washroom basin in the second floor depiction. All are plausible visible fixtures; the reference's exclusion of one is unresolved. This is not double-bowl splitting. |
| Q016 | Sinks | 2 → 3/3 | The main apartment has a kitchen double sink and a KH basin. The third detected basin is in a partially shown adjacent apartment's KH. Primary-unit scope likely explains the reference, but that restriction is not stated in the question. |
| Q017 | Windows | 7 → 5/5 | Five exterior glazing assemblies are detected on a cropped, annotated plan. Some are long multi-section frames. Missing apertures versus splitting independently framed units remains unresolved without instance annotations; annotation strokes must not become windows. |
| Q019 | Sinks | 2 → 4/4 | The central apartment's kitchen sink and bathroom basin are detected together with the neighboring cropped apartment's corresponding sink and basin. Four real visible fixture hypotheses survive; reference 2 appears to restrict the primary apartment. No double-bowl sink was counted twice. |
| Q022 | Windows | 6 → 3/3 | Three broad framed glazing assemblies are detected: MH exterior, OH exterior and kitchen exterior. The reference may divide their framed subunits differently. No independent instance labels establish six distinct apertures, so do not create panes simply to match 6. |

Q008's paired source is `data/swiss_dwellings/site151_bldg318_floor1293.dxf`.
Its geometry was inspected only for this offline review; raster inference still
received only the frozen PNG and question. The repeated primary-apartment/context
disagreements need an explicit scope convention before interpreting every raw
count mismatch as a missed or falsely detected object.


### Second-half validation source review

| Case | Reference | Before → after | Source finding |
|---|---:|---:|---|
| Q023 | 2 | 3 → 3 | Reference/depiction-grain discrepancy; no obvious false third fixture. All three boxes contain the same old WC glyph (rectangular tank/bowl plus directional arrow), each inside a distinctly positioned WC room. Middle and right upstairs-looking plans are mirrored/rotated depictions; source alone does not establish whether they refer to distinct logical units. Supplied reference 2 cannot be treated as proof only two WC glyphs are drawn. |
| Q029 | 11 | 13 → 12 | Combined omitted windows and confident solid-wall false positives, with stochastic detection/placement changes. After result adds two window boxes at the ground-floor KT/WC right boundary that enclose an uninterrupted thick solid black wall. It omits real left-side openings found before, including lower OH and SH. Thus a smaller count error (13 → 12) does not prove better localization. Original CubiCasa vector labels are not supplied locally; no independently certified total asserted. |
| Q031 | 12 | 13 → 17 | Window assembly/pane grouping instability plus at least one door/window confusion. After response changes 13 → 17 from extra proposals on paired top/bottom glazing. The bottom Ulkoet porch opening at approximately [374,504,423,516] has a hinged door leaf extending below its threshold; labeling that opening a window is a clear candidate-type problem. Several paired frame units can be interpreted as one assembly or adjacent windows; no source SVG labels are available locally to establish the supplied 12-assembly convention. Do not optimize to 12 by dropping visible panes arbitrarily. |
| Q032 | 0 | 1 → 1 | Unlabelled external glazed area classified confidently as balcony. The left appendage has glazing/railing-like linework and a fitted door, making a balcony hypothesis visually plausible. The cropped page gives no legible Parveke label or storey/elevation context establishing that it is raised rather than a porch/terrace. Candidate certainty is too strong; supplied 0 does not prove physical absence from this crop alone. |
| Q034 | 3 | 4 → 4 | Counts detached garage/storage plan as an extra storey. Four plan panels are visible: main house ground floor, upper floor, basement, and separate garage/storage. The reference 3 aligns with the main house storeys; detector interprets every complete plan depiction as another floor and adds the garage. Existing one-candidate-per-floor-plan-depiction guidance conflates depiction grain with building-storey grain. |
| Q038 | 0 | 3 → 3 | Inferred room function versus explicit label/annotation scope. There are three bedroom-like enclosed rooms with doors/windows/closets, but no printed MH labels. After result explicitly marks all three uncertain and all three membership checks remain ambiguous. The source supports possible rooms, not a confirmed bedroom inventory or a physical zero. Reference 0 likely reflects missing labels/annotations; original labels are unavailable, so that is an inference rather than established ground truth. |
| Q039 | 12 | 11 → 12 | Recovered missed fitted exterior door. After result adds a real hinged exterior door at the TK entrance, approximately [281,552,324,592], which before omitted. It is one fitted opening. Count changes 11 → 12, matching the reference. |
| Q040 | 8 | 8 → 6 | Omitted thin/long fixed glazing adjoining a balcony door. After result loses two genuine vertical glazing panels along OH/Parveke boundary, above and below the balcony door. Before returned both. This resembles thin balcony/loggia glazing misses in Swiss Q018. Model-visible request fields and pixels were confirmed identical between these two runs; the observed loss is recorded as stochastic variation, not demonstrated policy-induced regression. Before kitchen-window box also covered only part of the real span, so baseline exact count does not certify all boxes. |

The paired audits are `agent_reviewed`, not new human reference labels. They do
not modify the supplied answers. Exact-source duplicates are distinct from
unresolved counting conventions; genuine missed symbols and false positives
remain explicit even when a count happens to move closer to its reference.

## Next bounded accuracy work

Prioritize omission detection for thin balcony glazing and independent window
frames, with original/changed boxes reviewed as well as totals. A closer count
can hide simultaneous misses and false positives (validation Q029).
Scope interpretation must make primary-apartment versus visible-neighbor
ambiguity explicit; do not suppress neighboring source objects merely to fit a
reference. Separate storey depictions from detached accessory-building panels
(validation Q034). Repeated ambiguous membership calls (Q038) do not establish
room function or completeness and should not be treated as successful evidence.

## Verification and artifacts

Windows, Python 3.14.10 and Node 24.22.3: 162 focused Python tests and 126 frontend
tests passed; frontend production build passed with existing Three/WebGPU export
and chunk-size warnings. No Linux runtime or browser interaction test is claimed.
Frontend/backend health and frontend API proxy were checked; the workbench was
left running with the retained patch. Contracts and IFC behavior were unchanged.

Local ignored artifacts are under `experiments/runs/raster-hardening-20261115/`:
`baseline-50`, `final-50`, `validation-before-40`, `validation-after-40`, rejected
prompt/resolution trials, all diagnostic repeats, door controls and source audit
JSONs. Each evaluation retains an answer-free manifest, frozen code, exact model
inputs/hash metadata, raw replies, token usage, timing, audits and per-case scores.
The 40 validation sources do not overlap the initial 50. No provider errors,
reference-answer inputs, best-answer selection or runtime dataset lookup were used.
