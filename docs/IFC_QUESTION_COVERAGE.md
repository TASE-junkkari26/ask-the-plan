# IFC question coverage and acceptance inventory

Audit of the supplied full dataset on 14 November 2026. This is a task inventory,
not a claim of completed engine coverage or measured answer accuracy.

Question-file SHA-256: `0e6322c74561a63f42bac35f5c1be8a2c6a37516b14a81e66ab88b74950a6d1f`.

Regenerate with `python scripts/audit_ifc_questions.py`. Add
`--inventory-json build/ifc-question-inventory.json` for every original
line, question, reviewed family, scope and paired source path. The generator
does not read reference answer values or call a model.

## Exact denominators

| Cohort | Rows | Referenced paths | Distinct question texts |
| --- | ---: | ---: | ---: |
| IFC-Bench, direct IFC | 820 | 25 | 701 |
| Quantitative IFC models, direct IFC | 368 | 15 | 368 |
| IFC-derived floor PDFs | 2,694 | 69 | 2,486 |
| All direct IFC | 1,188 | 40 | 1,069 |
| All IFC-source cohorts | 3,882 | 109 | 3,554 |

The direct IFC target contains **198 reviewed families**.
Including paired PDFs gives **202 families and 54 source-model paths**.
All referenced assets and all 69 PDF-to-IFC pairs exist in this checkout.
The dataset README documents `<model>_plan-<level>.pdf` as a rendering of
`<model>.ifc`; this pairing establishes provenance, not identical view scope.

Direct quantitative IFC rows contain **64 whole-model and 304 floor/room rows**.
Their PDFs add **194 whole-model and 2,500 floor/room rows**. A model-wide
question remains model-wide even when its referenced asset is one floor PDF.
The 820 Bench rows have question-specific restrictions rather than a dataset
scope field; retain their exact model/floor/room/object wording. Do not infer
that all Bench questions authorize broadening an interactive current-view request.

## Starting implementation and required work

The initial audited runtime is commit `80a8ded`. It has source selection,
scalar property projection, exact counts, grouping, ranking, sum/mean/min/max,
native topology, bounded room/boundary geometry, related-object projection,
metadata discovery and source-backed result explanations. Its planner has a
shared cap of three requests, six inspection actions and a deadline. Those
primitives establish an implementation basis; they do not prove every family.

| Code | Required reusable work | Starting coverage / acceptance condition |
| --- | --- | --- |
| C | Select/filter/count at stated grain | Existing primitives; source class/type semantics, assemblies, multilingual literals and exact scope need real-case checks. |
| Q | Project scalar quantities/properties; aggregate or rank | Existing primitives; resolve original property keys, units, net/gross basis, missing inputs and all requested outputs. |
| J | Object→storey/type/material/system/room relationships and joined inventories | Native relations and related-object projection exist; joined per-occurrence grouping and incomplete relationships need verification. |
| A | Arithmetic, percentages, ratios, cost products, consecutive-elevation differences | Executor gap at audit start; preserve dimensions and input evidence, reject zero denominators and unsupported assumptions. |
| X | Material layers, layer thicknesses and nested source properties | Material membership exists; composition/ordered layer facts and derived layer quantities need extraction and evidence. |
| G | Geometry, topology, nearest distances and routes | Bounded topology/room containment exists; general quantities, town positions, route distances and widths remain gaps or require explicit missing-source outcomes. |
| N | Distribution-port graph, connectivity and integration metrics | Native port connectivity graph and derived metric definitions need implementation; system membership is insufficient. |
| M | Source metadata and bounded descriptive summaries | Native metadata exists; verify all requested components without inventing history, location or structural performance. |
| E | External factors, rule basis or estimation assumptions | Require explicit sourced inputs, qualified estimates or precise missing-information outcomes; reference defaults are not model facts. |

Codes describe the family as a whole and are not per-row success labels.
A missing executor for a known family remains unfinished work. Conversely,
a source-supported finding that the requested fact is absent can be correct;
absence must be established from extraction/source coverage, not guessed by a model.

Concrete initial gaps include consecutive storey heights (line 85521),
load-bearing volume percentage (85527), clinical/nonclinical ratio (85616),
net/gross ratio (85643), plumbing and ventilation port metrics (86261, 86292),
nearest town gate (85838), enclosed town area (85839), route lengths (85618,
85770) and source-qualified accessibility rules (85756).

## Every source model referenced directly or by a paired floor

Rows count question records, including translations and repeated references.
Distinct IFC paths are not independent projects: the prior full-data audit
found eight byte-identical cross-folder model pairs. Keep equivalent models
and their floors together in evaluation partitions.

| Source IFC path | Direct IFC rows | Paired PDF rows | PDF paths | First JSONL line |
| --- | ---: | ---: | ---: | ---: |
| `data/ifc_bench/4351_arc.ifc` | 43 | 0 | 0 | 85515 |
| `data/ifc_bench/ac20_arc.ifc` | 48 | 0 | 0 | 85558 |
| `data/ifc_bench/dental_clinic_arc.ifc` | 33 | 0 | 0 | 85606 |
| `data/ifc_bench/dental_clinic_str.ifc` | 10 | 0 | 0 | 85639 |
| `data/ifc_bench/digital_hub_arc.ifc` | 64 | 0 | 0 | 85649 |
| `data/ifc_bench/digital_hub_heating.ifc` | 12 | 0 | 0 | 85713 |
| `data/ifc_bench/digital_hub_plumbing.ifc` | 13 | 0 | 0 | 85725 |
| `data/ifc_bench/digital_hub_ventilation.ifc` | 13 | 0 | 0 | 85738 |
| `data/ifc_bench/duplex_arc.ifc` | 51 | 0 | 0 | 85751 |
| `data/ifc_bench/duplex_mep.ifc` | 18 | 0 | 0 | 85802 |
| `data/ifc_bench/ettenheim_gis_city.ifc` | 21 | 0 | 0 | 85820 |
| `data/ifc_bench/fantasy_hotel_1_arc.ifc` | 41 | 0 | 0 | 85841 |
| `data/ifc_bench/fantasy_office_building_1_arc.ifc` | 35 | 0 | 0 | 85882 |
| `data/ifc_bench/fantasy_office_building_2_arc.ifc` | 31 | 0 | 0 | 85917 |
| `data/ifc_bench/fantasy_office_building_3_arc.ifc` | 35 | 0 | 0 | 85948 |
| `data/ifc_bench/fantasy_residential_building_1_arc.ifc` | 37 | 0 | 0 | 85983 |
| `data/ifc_bench/fzk_house_arc.ifc` | 49 | 0 | 0 | 86020 |
| `data/ifc_bench/hitos_arc.ifc` | 51 | 0 | 0 | 86069 |
| `data/ifc_bench/molio_arc.ifc` | 58 | 0 | 0 | 86120 |
| `data/ifc_bench/sixty5_arc.ifc` | 50 | 0 | 0 | 86178 |
| `data/ifc_bench/sixty5_electrical.ifc` | 16 | 0 | 0 | 86228 |
| `data/ifc_bench/sixty5_plumbing.ifc` | 18 | 0 | 0 | 86244 |
| `data/ifc_bench/sixty5_str.ifc` | 11 | 0 | 0 | 86262 |
| `data/ifc_bench/sixty5_ventilation.ifc` | 20 | 0 | 0 | 86273 |
| `data/ifc_bench/smiley_west_arc.ifc` | 42 | 0 | 0 | 86293 |
| `data/ifc_models/bimspeed-barlad_ro-arc-m3-e-pth-0000.ifc` | 0 | 28 | 6 | 89293 |
| `data/ifc_models/bimspeed-frigento_modello-palazzo-testa-cipriano.ifc` | 0 | 8 | 2 | 88459 |
| `data/ifc_models/bimspeed-gdynia_ruchu-oporu-18.ifc` | 0 | 76 | 4 | 89321 |
| `data/ifc_models/bimspeed-vitoria_ald26-before.ifc` | 0 | 196 | 6 | 88467 |
| `data/ifc_models/bimspeed-vitoria_ald26-project.ifc` | 0 | 196 | 6 | 88663 |
| `data/ifc_models/bimspeed-warmond_ar.ifc` | 0 | 434 | 8 | 88859 |
| `data/ifc_models/bsc-chesapeake-bay-bridge-tunnel_chesapeake-bay-bridge-tunnel-4x3.ifc` | 4 | 0 | 0 | 87819 |
| `data/ifc_models/bsc-clinic_clinic-architectural.ifc` | 280 | 0 | 0 | 86379 |
| `data/ifc_models/bsc-clinic_clinic-electrical.ifc` | 2 | 0 | 0 | 86665 |
| `data/ifc_models/bsc-clinic_clinic-hvac.ifc` | 1 | 0 | 0 | 86663 |
| `data/ifc_models/bsc-clinic_clinic-plumbing.ifc` | 1 | 0 | 0 | 86664 |
| `data/ifc_models/bsc-clinic_clinic-structural.ifc` | 4 | 0 | 0 | 86659 |
| `data/ifc_models/bsc-duplex_duplex-a-20110907.ifc` | 36 | 0 | 0 | 86335 |
| `data/ifc_models/bsc-duplex_duplex-electrical-20121207.ifc` | 2 | 0 | 0 | 86375 |
| `data/ifc_models/bsc-duplex_duplex-m-20111024-rooms-and-spaces.ifc` | 1 | 0 | 0 | 86371 |
| `data/ifc_models/bsc-duplex_duplex-mep-20110907.ifc` | 3 | 0 | 0 | 86372 |
| `data/ifc_models/bsc-duplex_duplex-plumbing-20121113.ifc` | 2 | 0 | 0 | 86377 |
| `data/ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc` | 0 | 630 | 5 | 86667 |
| `data/ifc_models/bsc-gymzaal-amersfoort_example-project-location.ifc` | 0 | 128 | 2 | 87691 |
| `data/ifc_models/bsc-molio_molio-with-uris.ifc` | 0 | 394 | 9 | 87297 |
| `data/ifc_models/kit-fzk-haus_ac20-fzk-haus.ifc` | 0 | 44 | 2 | 87823 |
| `data/ifc_models/kit-institute_ac20-institute-var-2.ifc` | 0 | 98 | 5 | 87867 |
| `data/ifc_models/kit-smiley-west_ac-20-smiley-west-10-bldg.ifc` | 0 | 70 | 4 | 87965 |
| `data/ifc_models/rwth-digitalhub_digitalhub-fm-arc-v2.ifc` | 0 | 194 | 3 | 88035 |
| `data/ifc_models/rwth-digitalhub_digitalhub-fm-san-v2.ifc` | 2 | 0 | 0 | 88229 |
| `data/ifc_models/rwth-digitalhub_fm-arc-digitalhub-v1.ifc` | 14 | 0 | 0 | 88231 |
| `data/ifc_models/rwth-digitalhub_fm-arc-digitalhub-with-sb-v1.ifc` | 14 | 0 | 0 | 88245 |
| `data/ifc_models/rwth-digitalhub_fm-san-digitalhub-v1.ifc` | 2 | 0 | 0 | 88259 |
| `data/ifc_models/tuwien-escape-route_real-world-escape-route-test-model-zdb.ifc` | 0 | 198 | 7 | 88261 |

## Every reviewed family

The existing [exhaustive wording catalog](QUESTION_CLASSIFICATION.md#exhaustive-wording-and-template-catalog)
retains verbatim examples. The optional JSON inventory retains every original
row and exact path; this table preserves direct IFC versus PDF denominators.

| Family | IFC rows | PDF rows | Required work | First JSONL line |
| --- | ---: | ---: | --- | ---: |
| Area / Building footprint | 4 | 0 | G, Q | 85904 |
| Area / Duct cross-sections and distribution | 1 | 0 | A, Q | 85749 |
| Area / Exterior facade surface | 3 | 0 | G, Q | 85547 |
| Area / Floor finishes, tiles or specialty flooring | 5 | 0 | Q | 85625 |
| Area / Glazed windows | 1 | 0 | A, Q | 85758 |
| Area / Gross floor area, optionally by level | 12 | 0 | Q | 85520 |
| Area / Interior wall painting | 2 | 0 | A, Q | 85538 |
| Area / Net floor area of all spaces on one level | 5 | 70 | Q | 86355 |
| Area / Net or usable floor area, optionally by level | 6 | 0 | Q | 85585 |
| Area / Net side area of walls | 0 | 64 | Q | 87389 |
| Area / One room or space | 288 | 1792 | Q | 85635 |
| Area / Selected room or function totals | 3 | 0 | Q | 85613 |
| Area / Town enclosed by inner wall | 1 | 0 | G, Q | 85839 |
| Compliance / Internal-door accessibility requirements | 1 | 0 | E | 85756 |
| Compound / Door and window counts together | 1 | 0 | C, J, Q | 85833 |
| Compound / Room counts and areas | 4 | 0 | C, J, Q | 85908 |
| Compound / Room counts and locations | 1 | 0 | C, J, Q | 85907 |
| Compound / Staircase counts and widths | 1 | 0 | C, J, Q | 85878 |
| Compound / Wall counts and total length | 1 | 0 | C, J, Q | 85903 |
| Connectivity / Plumbing network ports and integration | 1 | 0 | A, N | 86261 |
| Connectivity / Ventilation network ports and integration | 1 | 0 | A, N | 86292 |
| Count / Apartments and residential units | 1 | 0 | C | 85990 |
| Count / Bathrooms and washrooms | 2 | 0 | C | 85798 |
| Count / Beams | 7 | 22 | C | 86339 |
| Count / Bedrooms | 1 | 0 | C | 85794 |
| Count / Buildings | 2 | 0 | C | 85821 |
| Count / Columns | 6 | 64 | C | 86660 |
| Count / Door hardware | 1 | 0 | C | 85799 |
| Count / Doors | 11 | 114 | C | 85637 |
| Count / Guest rooms by floor | 1 | 0 | C | 85847 |
| Count / Light fixtures | 4 | 2 | C | 86374 |
| Count / Light switches | 1 | 0 | C | 85552 |
| Count / Radiators | 1 | 0 | C | 85804 |
| Count / Roof vapor barriers | 1 | 0 | A, C | 85775 |
| Count / Rooms and spaces | 18 | 120 | C | 85612 |
| Count / Rooms with outdoor access | 1 | 0 | C | 85759 |
| Count / Sanitary fixtures (combined) | 8 | 4 | C | 86373 |
| Count / Separate toilet rooms | 1 | 0 | C | 85630 |
| Count / Stair steps | 1 | 0 | A, C | 85795 |
| Count / Stairs | 9 | 86 | C | 86340 |
| Count / Toilets (fixture-versus-room unspecified) | 5 | 0 | C | 85590 |
| Count / Walls | 8 | 90 | C | 86338 |
| Count / Wells and fountains | 1 | 0 | C | 85828 |
| Count / Windows | 11 | 64 | C | 85636 |
| Count / X-ray rooms | 1 | 0 | C | 85608 |
| Derived / Clinical-to-nonclinical space ratio | 1 | 0 | A, Q | 85616 |
| Derived / Door cost by type or total | 1 | 0 | A, E, Q | 85525 |
| Derived / Load-bearing wall volume proportion | 1 | 0 | A, Q | 85527 |
| Derived / Net-to-gross floor area ratio | 2 | 0 | A, Q | 85643 |
| Derived / Space use by function, areas or percentages | 4 | 0 | A, Q | 85682 |
| Derived / Structural embodied carbon | 1 | 0 | A, E, Q | 85789 |
| Derived / Window total cost | 1 | 0 | A, E, Q | 85526 |
| Inventory / Air terminals | 3 | 0 | C, J, Q | 85742 |
| Inventory / Apartments by level and elevation | 1 | 0 | C, J, Q | 86180 |
| Inventory / Beam types and quantities or properties | 9 | 0 | C, J, Q | 85598 |
| Inventory / Boilers, specifications and locations | 1 | 0 | C, J, Q | 85805 |
| Inventory / Cable routing and cable trays | 2 | 0 | C, J, Q | 86233 |
| Inventory / Coils | 2 | 0 | C, J, Q | 85745 |
| Inventory / Column types, dimensions and quantities | 15 | 0 | C, J, Q | 85599 |
| Inventory / Controllers | 1 | 0 | C, J, Q | 86277 |
| Inventory / Cooling systems and quantities | 5 | 0 | C, J, Q | 85876 |
| Inventory / Coverings and finishes | 7 | 0 | C, J, Q | 85586 |
| Inventory / Curtain-wall types and quantities | 5 | 0 | C, J, Q | 85852 |
| Inventory / Dampers | 2 | 0 | C, J, Q | 85743 |
| Inventory / Data and communication devices | 1 | 0 | C, J, Q | 86240 |
| Inventory / Door types with quantities, optionally dimensions or percentages | 13 | 0 | C, J, Q | 85522 |
| Inventory / Duct fittings and accessories | 3 | 0 | C, J, Q | 85741 |
| Inventory / Duct types and specifications | 3 | 0 | C, J, Q | 85740 |
| Inventory / Electrical receptacles and switches by type | 2 | 0 | C, J, Q | 86230 |
| Inventory / Electrical systems and components | 9 | 0 | C, J, Q | 85551 |
| Inventory / Fans | 2 | 0 | C, J, Q | 85744 |
| Inventory / Filters | 2 | 0 | C, J, Q | 85733 |
| Inventory / Foundation types and quantities | 4 | 0 | C, J, Q | 85690 |
| Inventory / Furniture by type, room or level | 20 | 0 | C, J, Q | 85548 |
| Inventory / Heat recovery units | 2 | 0 | C, J, Q | 85747 |
| Inventory / Heating sensors | 1 | 0 | C, J, Q | 85718 |
| Inventory / Heating systems and component categories | 10 | 0 | C, J, Q | 85605 |
| Inventory / Junction components and junction boxes | 2 | 0 | C, J, Q | 86236 |
| Inventory / Lighting systems, fixtures and devices | 6 | 0 | C, J, Q | 85709 |
| Inventory / MEP systems and components by category, space or level | 19 | 0 | C, J, Q | 85553 |
| Inventory / Measuring equipment | 2 | 0 | C, J, Q | 86258 |
| Inventory / Mechanical and unitary equipment | 2 | 0 | C, J, Q | 85722 |
| Inventory / Parking equipment and areas | 2 | 0 | C, J, Q | 85658 |
| Inventory / Pipe fittings and accessories | 5 | 0 | C, J, Q | 85716 |
| Inventory / Pipes by type, application, material or floor | 9 | 0 | C, J, Q, X | 85604 |
| Inventory / Plumbing systems and component categories | 5 | 0 | C, J, Q | 85725 |
| Inventory / Pumps | 3 | 0 | C, J, Q | 85720 |
| Inventory / Radiator types and quantities | 1 | 0 | C, J, Q | 85719 |
| Inventory / Railings, types, quantities or materials | 8 | 0 | C, J, Q, X | 85593 |
| Inventory / Roof types, components, materials or areas | 10 | 0 | C, J, Q, X | 85549 |
| Inventory / Rooms and spaces by name or function | 9 | 0 | C, J, Q | 85610 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | 76 | 0 | C, J, Q | 85516 |
| Inventory / Sanitary fixtures and equipment by type or location | 13 | 0 | C, J, Q | 85556 |
| Inventory / Slab types, quantities and thicknesses | 18 | 0 | C, J, Q, X | 85601 |
| Inventory / Stair types, quantities or specifications | 8 | 0 | C, J, Q | 85541 |
| Inventory / Structural components and quantities | 9 | 0 | C, J, Q | 85597 |
| Inventory / Tanks | 1 | 0 | C, J, Q | 85721 |
| Inventory / Town buildings and categories | 3 | 0 | C, J, Q | 85824 |
| Inventory / Town gates and fortifications | 3 | 0 | C, J, Q | 85822 |
| Inventory / Town roads and paths | 1 | 0 | C, J, Q | 85829 |
| Inventory / Town water features | 1 | 0 | C, J, Q | 85830 |
| Inventory / Valves | 3 | 0 | C, J, Q | 85717 |
| Inventory / Ventilation systems and component categories | 4 | 0 | C, J, Q | 85738 |
| Inventory / Vertical circulation types, counts and subcomponents | 2 | 0 | C, J, Q | 85924 |
| Inventory / Wall thickness distribution | 1 | 0 | C, J, Q, X | 86268 |
| Inventory / Wall types with quantities, optionally materials or properties | 40 | 0 | C, J, Q, X | 85528 |
| Inventory / Walls by load-bearing status, counts or proportions | 11 | 0 | C, J, Q | 85582 |
| Inventory / Waste terminals | 2 | 0 | C, J, Q | 85732 |
| Inventory / Water heaters and water-heating systems | 2 | 0 | C, J, Q | 85731 |
| Inventory / Window types and sizes with quantities or percentages | 14 | 0 | C, J, Q | 85523 |
| Length / All walls on one level | 0 | 64 | Q | 87387 |
| Length / Electrical conduits, optionally with segment statistics | 1 | 0 | Q | 86234 |
| Length / Exterior and interior walls together or compared | 3 | 0 | Q | 85672 |
| Length / Exterior walls | 7 | 0 | Q | 85534 |
| Length / Flexible cable pipes, quantities and proportions | 1 | 0 | Q | 86238 |
| Length / Heating pipe network, optionally with segment statistics | 2 | 0 | Q | 85714 |
| Length / Interior walls | 3 | 0 | Q | 85533 |
| Length / Pipes (system unspecified) | 2 | 0 | Q | 86114 |
| Length / Pipes and ducts together | 1 | 0 | Q | 85712 |
| Length / Plumbing pipe network, optionally with segment statistics | 4 | 0 | Q | 85555 |
| Length / Skirting boards | 1 | 0 | G, Q | 85784 |
| Length / Steel beams by type | 1 | 0 | Q | 86271 |
| Length / Ventilation ductwork, optionally with segment statistics | 2 | 0 | Q | 85739 |
| Overview / Building metrics combining counts, areas or elevations | 5 | 0 | M | 85560 |
| Overview / Project, location, building function or historical identity | 13 | 0 | M | 85558 |
| Overview / Residential or level layout and organization | 5 | 0 | M | 85835 |
| Overview / Structural system, concept or efficiency | 8 | 0 | M | 85550 |
| Overview / Town defensive layout and strategy | 1 | 0 | M | 85834 |
| Property / Beam spans and sizes | 1 | 0 | Q | 85689 |
| Property / Building envelope airtightness | 1 | 0 | Q | 85778 |
| Property / Building level heights and elevations | 14 | 0 | A, Q | 85521 |
| Property / Building thermal bridges | 1 | 0 | Q | 85777 |
| Property / Ceiling GUID | 1 | 0 | G, Q | 85797 |
| Property / Ceiling materials or systems | 12 | 0 | Q, X | 85587 |
| Property / Column dimensions | 3 | 0 | Q | 85600 |
| Property / Conduit materials and applications | 1 | 0 | Q, X | 86235 |
| Property / Construction phasing and renovation status | 3 | 0 | Q | 85557 |
| Property / Defensive wall heights | 1 | 0 | Q | 85836 |
| Property / Door fire ratings or rating availability | 13 | 0 | Q | 85535 |
| Property / Door width or dimensions | 2 | 0 | Q | 85611 |
| Property / Electrical distribution capacity availability | 1 | 0 | Q | 85706 |
| Property / Electrical loads, optionally equipment or floor breakdowns | 5 | 0 | Q | 85705 |
| Property / Electrical voltage levels | 1 | 0 | Q | 85708 |
| Property / Energy consumption or efficiency | 2 | 0 | Q | 85710 |
| Property / External-wall insulation type or thickness | 4 | 0 | Q, X | 85606 |
| Property / Fire protection or suppression system | 2 | 0 | Q | 85810 |
| Property / Floor live-load capacity | 1 | 0 | Q | 85767 |
| Property / Foundation depth | 1 | 0 | Q | 85761 |
| Property / Foundation materials | 1 | 0 | Q, X | 85647 |
| Property / Heating capacity or equipment specifications | 2 | 0 | Q | 85723 |
| Property / Light-fixture presence | 1 | 0 | Q | 85916 |
| Property / Maintenance requirements or schedules | 3 | 0 | E, Q | 85711 |
| Property / Model software and IFC standards | 14 | 0 | M, Q | 85515 |
| Property / Parking dimensions and capacity | 1 | 0 | Q | 85657 |
| Property / Pipe materials and quantities | 1 | 0 | Q, X | 86260 |
| Property / Renewable-energy systems presence | 1 | 0 | Q | 85817 |
| Property / Residential-building construction materials | 1 | 0 | Q, X | 85837 |
| Property / Roof material lifespan | 2 | 0 | E, Q, X | 85639 |
| Property / Room and ceiling heights | 4 | 0 | Q | 85609 |
| Property / Room wall or floor finishes | 2 | 0 | Q | 85622 |
| Property / Slab materials | 1 | 0 | Q, X | 86318 |
| Property / Steel beams spanning a specified room | 1 | 0 | G, Q | 85763 |
| Property / Structural materials | 1 | 0 | Q, X | 85688 |
| Property / Structural reinforcement for medical equipment | 1 | 0 | Q | 85621 |
| Property / Toilet water efficiency | 1 | 0 | Q | 85818 |
| Property / Ventilation insulation and coverage | 1 | 0 | Q, X | 86289 |
| Property / Ventilation requirements | 1 | 0 | E, Q | 86334 |
| Property / Waiting-area capacities | 1 | 0 | E, Q | 85614 |
| Property / Wall acoustic rating | 1 | 0 | E, Q | 85626 |
| Property / Wall fire ratings or rating availability | 2 | 0 | Q | 85644 |
| Property / Wall load-bearing status | 3 | 0 | Q | 85627 |
| Property / Wall materials and construction layers | 27 | 0 | Q, X | 85530 |
| Property / Wall thicknesses or layer dimensions | 13 | 0 | Q, X | 85532 |
| Property / Window fire ratings or rating availability | 11 | 0 | Q | 85596 |
| Property / Window glazing type | 3 | 0 | Q | 85524 |
| Property / Window height or dimensions | 2 | 0 | Q | 85632 |
| Property / Window solar heat gain coefficient | 1 | 0 | Q | 85779 |
| Property / Window warranty | 1 | 0 | Q | 85781 |
| Ranking / Door widths, extrema, top-k or statistics | 13 | 0 | Q | 85536 |
| Ranking / Largest room or rooms by area | 8 | 0 | Q | 85568 |
| Ranking / Rooms with highest or lowest ceilings | 6 | 0 | Q | 85594 |
| Ranking / Window widths, extrema or top-k | 8 | 0 | Q | 85573 |
| Spatial / Emergency escape-route width | 1 | 0 | G, J | 85772 |
| Spatial / Emergency-exit route distance | 3 | 0 | G, J | 85618 |
| Spatial / Equipment locations | 4 | 0 | G, J | 85638 |
| Spatial / Fire exits and their locations | 2 | 0 | G, J | 85539 |
| Spatial / Fire-extinguisher presence and locations | 1 | 0 | G, J | 85811 |
| Spatial / Highest-ground buildings and location | 1 | 0 | G, J | 85825 |
| Spatial / Nearest town gate | 1 | 0 | G, J | 85838 |
| Spatial / Room adjacency or connectivity | 2 | 0 | G, J | 85633 |
| Spatial / Rooms served by thermostats or air systems | 2 | 0 | G, J | 85554 |
| Spatial / Rooms with direct outdoor access | 1 | 0 | G, J | 85540 |
| Spatial / Server-room location and identifier | 1 | 0 | G, J | 85620 |
| Sustainability / Material recyclability | 1 | 0 | E, X | 85790 |
| Sustainability / Recycled material content | 1 | 0 | E, X | 85819 |
| Volume / Concrete across structural components | 4 | 0 | J, Q | 85543 |
| Volume / Foundation concrete | 3 | 0 | J, Q | 85546 |
| Volume / Insulation | 2 | 0 | A, J, Q, X | 85531 |
| Volume / Net slab volume | 0 | 72 | J, Q | 87349 |
| Volume / Net wall volume | 0 | 66 | J, Q | 87391 |
| Volume / Slabs, optionally grouped by type or level | 11 | 0 | J, Q | 85542 |
| Volume / Wall concrete | 1 | 0 | J, Q | 85544 |

## Completion and evaluation gates

1. Preserve the 1,188 direct-IFC-row denominator and all 198 families. Track
   the 2,694 paired-PDF rows separately; using their source IFC must retain
   the named floor/view and cannot silently expand a user's upload scope.
2. Run production upload/question planning and execution on all 40 directly
   referenced IFC paths. Cover every family and named quantity, including
   rare geometry, network and derived tasks. Unknown unsupported families
   remain in the denominator rather than disappearing from a success report.
3. Save predictions, plans, source hashes, source element/fact/anchor sets,
   calculation inputs, scope, status, units, usage and timing before loading
   evaluation references. No QA lookup belongs in planning or execution.
4. Counts require exact agreement at the stated occurrence/assembly grain.
   Quantities require compatible units/bases and the supplied dataset's 2%
   tolerance. A missing total is not zero; lower bounds cannot pass as exact.
5. Bench `text` includes numerical and multipart tasks. Check every requested
   component against source facts/calculations or an independently supported
   missing-information finding. Structural/evidence checks alone leave text
   accuracy ungraded; keyword matching cannot establish correctness.
6. Check current-view, explicit-empty-view, hidden-floor, whole-model and
   source-revision variants. Add paraphrases/translations within these known
   families and preserve literal identifiers. A result cannot use outside-view
   prerequisite objects without reporting incomplete coverage.
7. Use deterministic cached extraction and bounded tools for computation.
   Start with one planning call; discovery/repair shares a finite budget.
   Resume persisted runs to avoid repeated paid calls and report actual usage,
   latency, errors and non-answers alongside successful results.

Known reference disputes need source adjudication. For example, line 85820
reports a legacy schema differing from the distributed IFC file header.
See [dataset findings](../dataset/FULL_DATASET_FINDINGS.md) and
[scope and acceptance](PROJECT_SCOPE.md). This inventory does not validate
all reference answers, classify all missing-input references, or establish
dataset-wide end-to-end accuracy.

Implemented behavior, source-backed development probes and their limitations
are recorded separately in [implementation verification](IFC_IMPLEMENTATION_VERIFICATION.md).
