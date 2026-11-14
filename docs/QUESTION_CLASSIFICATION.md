# Exact question classification of the full Junction dataset

Generated 2026-11-14 from the supplied full dataset, excluding the preview.

**127,044 question rows; 6,789 distinct verbatim question texts; 234 semantic question families; every row classified exactly once.**

These are counts of **questions**, not counts of physical windows, doors, or other objects. No reference answers were summed.

## Counting and classification rules

- Each nonblank JSONL record counts once, including translations and repeated wording on different drawings. These are row frequencies, not independent buildings or training examples.
- Semantically equivalent questions in different languages share a family. Literal room IDs, storey names, and model names remain unchanged in examples; parameter variations do not create new families.
- Families combine the requested operation and target. They are an explicit analysis taxonomy, not organizer-supplied semantic labels. The dataset's own `type` field describes the stored answer format and is reported separately. All IFC-Bench rows are stored as `text`, even when they ask for counts, areas, or other numeric results.
- The family table is mutually exclusive. Multipart inventories stay in one descriptive family; questions asking multiple independent counts or a count plus area have explicit compound families. Do not add inventory/compound rows to a simple count without changing the definition.
- "Count windows" includes direct total/filtered/window-schedule assembly counts. Type/size inventories, window dimensions, window area, and multiplying assembly widths into individual units are separate families. Door leaves, mixed door-schedule entries, and gates are also separate from direct door counts.
- Room labels are normalized separately using the explicit Swiss label mapping below. Generic `Zimmer`/`Pièce`/`Stanza` are not assumed to be bedrooms. Stairwell rooms, stairs, and stair steps remain distinct.
- Source counting conventions still apply: CubiCasa includes only doorways fitted with a door, combines showers with bathtubs, and counts a double-bowl sink as one. Its kitchen and bathroom definitions differ from a literal Swiss label filter. The five ambiguous IFC-Bench "toilets" wordings remain explicitly unspecified rather than being guessed as fixtures or rooms.
- The classification describes **what the question requests**, not whether its answer is available, correct, estimated, or implemented. No model or source-geometry accuracy is implied.

## Direct count questions: exact totals

These families ask directly for object counts, including filtered counts and per-floor count breakdowns. Named-type inventories and compound questions appear separately in the exhaustive family table.

| Question asks how many… | Question rows | Share of all rows |
| --- | --- | --- |
| Windows | 11,735 | 9.2370% |
| Toilet bowls and WC fixtures | 11,645 | 9.1661% |
| Sinks and washbasins | 11,531 | 9.0764% |
| Floors and storeys shown | 9,574 | 7.5360% |
| Doors | 9,267 | 7.2943% |
| Showers and bathtubs together | 8,884 | 6.9929% |
| Kitchens | 8,488 | 6.6811% |
| Saunas | 6,630 | 5.2187% |
| Bathrooms and washrooms | 6,556 | 5.1604% |
| Bedrooms | 6,443 | 5.0715% |
| Separate toilet rooms | 4,665 | 3.6720% |
| Balconies | 4,280 | 3.3689% |
| Apartments and residential units | 2,081 | 1.6380% |
| Corridors | 1,860 | 1.4641% |
| Bathtubs | 1,794 | 1.4121% |
| Generic labelled rooms (not necessarily bedrooms) | 1,542 | 1.2138% |
| Stairwell rooms | 1,284 | 1.0107% |
| Living and dining rooms together | 1,064 | 0.8375% |
| Showers | 644 | 0.5069% |
| Storage rooms | 596 | 0.4691% |
| Living rooms | 538 | 0.4235% |
| Loggias | 204 | 0.1606% |
| Rooms and spaces | 139 | 0.1094% |
| Walls | 98 | 0.0771% |
| Stairs | 95 | 0.0748% |
| Columns | 70 | 0.0551% |
| Beams | 29 | 0.0228% |
| Sanitary fixtures (combined) | 12 | 0.0094% |
| Kitchen and dining rooms together | 8 | 0.0063% |
| Cellar rooms | 6 | 0.0047% |
| Light fixtures | 6 | 0.0047% |
| Toilets (fixture-versus-room unspecified) | 5 | 0.0039% |
| Buildings | 2 | 0.0016% |
| Rooms filtered by finish | 2 | 0.0016% |
| Door hardware | 1 | 0.0008% |
| Door leaves | 1 | 0.0008% |
| Door-schedule entries including non-door items | 1 | 0.0008% |
| Gates | 1 | 0.0008% |
| Guest rooms by floor | 1 | 0.0008% |
| Light switches | 1 | 0.0008% |
| Radiators | 1 | 0.0008% |
| Roof vapor barriers | 1 | 0.0008% |
| Rooms with outdoor access | 1 | 0.0008% |
| Stair steps | 1 | 0.0008% |
| Wells and fountains | 1 | 0.0008% |
| X-ray rooms | 1 | 0.0008% |
| **Direct-count subtotal** | 111,789 |  |

## Requested-operation totals

These semantic operation buckets are separate from the original answer-format labels.

| Requested operation | Question rows | Share |
| --- | --- | --- |
| Count | 111,789 | 87.9923% |
| Area | 14,282 | 11.2418% |
| Inventory | 420 | 0.3306% |
| Property | 188 | 0.1480% |
| Volume | 159 | 0.1252% |
| Length | 92 | 0.0724% |
| Ranking | 36 | 0.0283% |
| Overview | 32 | 0.0252% |
| Spatial | 19 | 0.0150% |
| Derived | 12 | 0.0094% |
| Compound | 10 | 0.0079% |
| Sustainability | 2 | 0.0016% |
| Connectivity | 2 | 0.0016% |
| Compliance | 1 | 0.0008% |
| **Total** | 127,044 | 100% |

## Original dataset answer-format totals

| Stored `type` | Question rows | Share |
| --- | --- | --- |
| count | 111,763 | 87.9719% |
| area | 14,243 | 11.2111% |
| text | 836 | 0.6580% |
| volume | 138 | 0.1086% |
| length | 64 | 0.0504% |
| other | 0 | 0.0000% |
| **Total** | 127,044 | 100% |

### Requested operation versus stored answer format

This cross-tab makes numeric tasks stored as `text` visible without altering the supplied type labels.

| Requested operation | count | area | text | volume | length | other | Total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Count | 111,762 | 0 | 27 | 0 | 0 | 0 | 111,789 |
| Area | 0 | 14,243 | 39 | 0 | 0 | 0 | 14,282 |
| Inventory | 0 | 0 | 420 | 0 | 0 | 0 | 420 |
| Property | 0 | 0 | 188 | 0 | 0 | 0 | 188 |
| Volume | 0 | 0 | 21 | 138 | 0 | 0 | 159 |
| Length | 0 | 0 | 28 | 0 | 64 | 0 | 92 |
| Ranking | 0 | 0 | 36 | 0 | 0 | 0 | 36 |
| Overview | 0 | 0 | 32 | 0 | 0 | 0 | 32 |
| Spatial | 0 | 0 | 19 | 0 | 0 | 0 | 19 |
| Derived | 1 | 0 | 11 | 0 | 0 | 0 | 12 |
| Compound | 0 | 0 | 10 | 0 | 0 | 0 | 10 |
| Sustainability | 0 | 0 | 2 | 0 | 0 | 0 | 2 |
| Connectivity | 0 | 0 | 2 | 0 | 0 | 0 | 2 |
| Compliance | 0 | 0 | 1 | 0 | 0 | 0 | 1 |
| **Total** | 111,763 | 14,243 | 836 | 138 | 64 | 0 | 127,044 |

## Source coverage

| Source | Question rows | Distinct question texts | Referenced paths | Families in source |
| --- | --- | --- | --- | --- |
| CubiCasa5K | 85,514 | 24 | 4,787 | 12 |
| Swiss Dwellings | 37,584 | 3,147 | 1,040 | 25 |
| IFC models | 3,062 | 2,853 | 84 | 15 |
| IFC-Bench | 820 | 701 | 25 | 191 |
| Opening Design | 64 | 64 | 3 | 24 |
| europeana | 0 | 0 | 0 | 0 |
| finna | 0 | 0 | 0 | 0 |
| habs | 0 | 0 | 0 | 0 |
| wikimedia | 0 | 0 | 0 | 0 |

## Every semantic family, with counts by source

Each row below is a disjoint family. Column totals and the grand total are checked by the generator. Zero means no supplied questions in that family/source, not zero objects in a drawing.

| Question family | Total | CubiCasa | Swiss | IFC models | IFC-Bench | Opening Design |
| --- | --- | --- | --- | --- | --- | --- |
| Area / One room or space | 6,236 | 0 | 4,152 | 2,079 | 1 | 4 |
| Area / Net apartment floor area excluding outdoor spaces | 3,750 | 0 | 3,750 | 0 | 0 | 0 |
| Area / Net indoor floor area excluding outdoor spaces, shafts and voids | 2,080 | 0 | 2,080 | 0 | 0 | 0 |
| Area / Sum of labelled rooms: generic labelled rooms (not necessarily bedrooms) | 1,512 | 0 | 1,512 | 0 | 0 | 0 |
| Area / Sum of labelled rooms: bedrooms | 522 | 0 | 522 | 0 | 0 | 0 |
| Area / Net floor area of all spaces on one level | 75 | 0 | 0 | 75 | 0 | 0 |
| Area / Net side area of walls | 64 | 0 | 0 | 64 | 0 | 0 |
| Area / Gross floor area, optionally by level | 12 | 0 | 0 | 0 | 12 | 0 |
| Area / Selected room or function totals | 7 | 0 | 0 | 0 | 3 | 4 |
| Area / Net or usable floor area, optionally by level | 6 | 0 | 0 | 0 | 6 | 0 |
| Area / Floor finishes, tiles or specialty flooring | 5 | 0 | 0 | 0 | 5 | 0 |
| Area / Building footprint | 4 | 0 | 0 | 0 | 4 | 0 |
| Area / Exterior facade surface | 3 | 0 | 0 | 0 | 3 | 0 |
| Area / Interior wall painting | 2 | 0 | 0 | 0 | 2 | 0 |
| Area / Duct cross-sections and distribution | 1 | 0 | 0 | 0 | 1 | 0 |
| Area / Glazed windows | 1 | 0 | 0 | 0 | 1 | 0 |
| Area / Room areas filtered by finish | 1 | 0 | 0 | 0 | 0 | 1 |
| Area / Town enclosed by inner wall | 1 | 0 | 0 | 0 | 1 | 0 |
| Compliance / Internal-door accessibility requirements | 1 | 0 | 0 | 0 | 1 | 0 |
| Compound / Room counts and areas | 5 | 0 | 0 | 0 | 4 | 1 |
| Compound / Door and window counts together | 1 | 0 | 0 | 0 | 1 | 0 |
| Compound / Room counts and locations | 1 | 0 | 0 | 0 | 1 | 0 |
| Compound / Staircase counts and widths | 1 | 0 | 0 | 0 | 1 | 0 |
| Compound / Toilet, washbasin and shower counts together | 1 | 0 | 0 | 0 | 0 | 1 |
| Compound / Wall counts and total length | 1 | 0 | 0 | 0 | 1 | 0 |
| Connectivity / Plumbing network ports and integration | 1 | 0 | 0 | 0 | 1 | 0 |
| Connectivity / Ventilation network ports and integration | 1 | 0 | 0 | 0 | 1 | 0 |
| Count / Windows | 11,735 | 9,574 | 2,080 | 73 | 2 | 6 |
| Count / Toilet bowls and WC fixtures | 11,645 | 9,564 | 2,080 | 0 | 0 | 1 |
| Count / Sinks and washbasins | 11,531 | 9,450 | 2,080 | 0 | 0 | 1 |
| Count / Floors and storeys shown | 9,574 | 9,574 | 0 | 0 | 0 | 0 |
| Count / Doors | 9,267 | 7,038 | 2,080 | 123 | 2 | 24 |
| Count / Showers and bathtubs together | 8,884 | 8,884 | 0 | 0 | 0 | 0 |
| Count / Kitchens | 8,488 | 6,524 | 1,964 | 0 | 0 | 0 |
| Count / Saunas | 6,630 | 6,630 | 0 | 0 | 0 | 0 |
| Count / Bathrooms and washrooms | 6,556 | 4,768 | 1,786 | 0 | 2 | 0 |
| Count / Bedrooms | 6,443 | 5,920 | 522 | 0 | 1 | 0 |
| Count / Separate toilet rooms | 4,665 | 4,664 | 0 | 0 | 1 | 0 |
| Count / Balconies | 4,280 | 2,924 | 1,356 | 0 | 0 | 0 |
| Count / Apartments and residential units | 2,081 | 0 | 2,080 | 0 | 1 | 0 |
| Count / Corridors | 1,860 | 0 | 1,860 | 0 | 0 | 0 |
| Count / Bathtubs | 1,794 | 0 | 1,794 | 0 | 0 | 0 |
| Count / Generic labelled rooms (not necessarily bedrooms) | 1,542 | 0 | 1,542 | 0 | 0 | 0 |
| Count / Stairwell rooms | 1,284 | 0 | 1,284 | 0 | 0 | 0 |
| Count / Living and dining rooms together | 1,064 | 0 | 1,064 | 0 | 0 | 0 |
| Count / Showers | 644 | 0 | 644 | 0 | 0 | 0 |
| Count / Storage rooms | 596 | 0 | 596 | 0 | 0 | 0 |
| Count / Living rooms | 538 | 0 | 538 | 0 | 0 | 0 |
| Count / Loggias | 204 | 0 | 204 | 0 | 0 | 0 |
| Count / Rooms and spaces | 139 | 0 | 0 | 136 | 2 | 1 |
| Count / Walls | 98 | 0 | 0 | 98 | 0 | 0 |
| Count / Stairs | 95 | 0 | 0 | 95 | 0 | 0 |
| Count / Columns | 70 | 0 | 0 | 70 | 0 | 0 |
| Count / Beams | 29 | 0 | 0 | 29 | 0 | 0 |
| Count / Sanitary fixtures (combined) | 12 | 0 | 0 | 12 | 0 | 0 |
| Count / Kitchen and dining rooms together | 8 | 0 | 8 | 0 | 0 | 0 |
| Count / Cellar rooms | 6 | 0 | 6 | 0 | 0 | 0 |
| Count / Light fixtures | 6 | 0 | 0 | 6 | 0 | 0 |
| Count / Toilets (fixture-versus-room unspecified) | 5 | 0 | 0 | 0 | 5 | 0 |
| Count / Buildings | 2 | 0 | 0 | 0 | 2 | 0 |
| Count / Rooms filtered by finish | 2 | 0 | 0 | 0 | 0 | 2 |
| Count / Door hardware | 1 | 0 | 0 | 0 | 1 | 0 |
| Count / Door leaves | 1 | 0 | 0 | 0 | 0 | 1 |
| Count / Door-schedule entries including non-door items | 1 | 0 | 0 | 0 | 0 | 1 |
| Count / Gates | 1 | 0 | 0 | 0 | 0 | 1 |
| Count / Guest rooms by floor | 1 | 0 | 0 | 0 | 1 | 0 |
| Count / Light switches | 1 | 0 | 0 | 0 | 1 | 0 |
| Count / Radiators | 1 | 0 | 0 | 0 | 1 | 0 |
| Count / Roof vapor barriers | 1 | 0 | 0 | 0 | 1 | 0 |
| Count / Rooms with outdoor access | 1 | 0 | 0 | 0 | 1 | 0 |
| Count / Stair steps | 1 | 0 | 0 | 0 | 1 | 0 |
| Count / Wells and fountains | 1 | 0 | 0 | 0 | 1 | 0 |
| Count / X-ray rooms | 1 | 0 | 0 | 0 | 1 | 0 |
| Derived / Space use by function, areas or percentages | 4 | 0 | 0 | 0 | 4 | 0 |
| Derived / Net-to-gross floor area ratio | 2 | 0 | 0 | 0 | 2 | 0 |
| Derived / Clinical-to-nonclinical space ratio | 1 | 0 | 0 | 0 | 1 | 0 |
| Derived / Door cost by type or total | 1 | 0 | 0 | 0 | 1 | 0 |
| Derived / Load-bearing wall volume proportion | 1 | 0 | 0 | 0 | 1 | 0 |
| Derived / Structural embodied carbon | 1 | 0 | 0 | 0 | 1 | 0 |
| Derived / Window total cost | 1 | 0 | 0 | 0 | 1 | 0 |
| Derived / Window-unit count from assembly multiplicities | 1 | 0 | 0 | 0 | 0 | 1 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | 76 | 0 | 0 | 0 | 76 | 0 |
| Inventory / Wall types with quantities, optionally materials or properties | 40 | 0 | 0 | 0 | 40 | 0 |
| Inventory / Furniture by type, room or level | 20 | 0 | 0 | 0 | 20 | 0 |
| Inventory / MEP systems and components by category, space or level | 19 | 0 | 0 | 0 | 19 | 0 |
| Inventory / Slab types, quantities and thicknesses | 18 | 0 | 0 | 0 | 18 | 0 |
| Inventory / Column types, dimensions and quantities | 15 | 0 | 0 | 0 | 15 | 0 |
| Inventory / Window types and sizes with quantities or percentages | 14 | 0 | 0 | 0 | 14 | 0 |
| Inventory / Door types with quantities, optionally dimensions or percentages | 13 | 0 | 0 | 0 | 13 | 0 |
| Inventory / Sanitary fixtures and equipment by type or location | 13 | 0 | 0 | 0 | 13 | 0 |
| Inventory / Walls by load-bearing status, counts or proportions | 11 | 0 | 0 | 0 | 11 | 0 |
| Inventory / Heating systems and component categories | 10 | 0 | 0 | 0 | 10 | 0 |
| Inventory / Roof types, components, materials or areas | 10 | 0 | 0 | 0 | 10 | 0 |
| Inventory / Beam types and quantities or properties | 9 | 0 | 0 | 0 | 9 | 0 |
| Inventory / Electrical systems and components | 9 | 0 | 0 | 0 | 9 | 0 |
| Inventory / Pipes by type, application, material or floor | 9 | 0 | 0 | 0 | 9 | 0 |
| Inventory / Rooms and spaces by name or function | 9 | 0 | 0 | 0 | 9 | 0 |
| Inventory / Structural components and quantities | 9 | 0 | 0 | 0 | 9 | 0 |
| Inventory / Railings, types, quantities or materials | 8 | 0 | 0 | 0 | 8 | 0 |
| Inventory / Stair types, quantities or specifications | 8 | 0 | 0 | 0 | 8 | 0 |
| Inventory / Coverings and finishes | 7 | 0 | 0 | 0 | 7 | 0 |
| Inventory / Lighting systems, fixtures and devices | 6 | 0 | 0 | 0 | 6 | 0 |
| Inventory / Cooling systems and quantities | 5 | 0 | 0 | 0 | 5 | 0 |
| Inventory / Curtain-wall types and quantities | 5 | 0 | 0 | 0 | 5 | 0 |
| Inventory / Pipe fittings and accessories | 5 | 0 | 0 | 0 | 5 | 0 |
| Inventory / Plumbing systems and component categories | 5 | 0 | 0 | 0 | 5 | 0 |
| Inventory / Foundation types and quantities | 4 | 0 | 0 | 0 | 4 | 0 |
| Inventory / Ventilation systems and component categories | 4 | 0 | 0 | 0 | 4 | 0 |
| Inventory / Air terminals | 3 | 0 | 0 | 0 | 3 | 0 |
| Inventory / Duct fittings and accessories | 3 | 0 | 0 | 0 | 3 | 0 |
| Inventory / Duct types and specifications | 3 | 0 | 0 | 0 | 3 | 0 |
| Inventory / Pumps | 3 | 0 | 0 | 0 | 3 | 0 |
| Inventory / Town buildings and categories | 3 | 0 | 0 | 0 | 3 | 0 |
| Inventory / Town gates and fortifications | 3 | 0 | 0 | 0 | 3 | 0 |
| Inventory / Valves | 3 | 0 | 0 | 0 | 3 | 0 |
| Inventory / Cable routing and cable trays | 2 | 0 | 0 | 0 | 2 | 0 |
| Inventory / Coils | 2 | 0 | 0 | 0 | 2 | 0 |
| Inventory / Dampers | 2 | 0 | 0 | 0 | 2 | 0 |
| Inventory / Electrical receptacles and switches by type | 2 | 0 | 0 | 0 | 2 | 0 |
| Inventory / Fans | 2 | 0 | 0 | 0 | 2 | 0 |
| Inventory / Filters | 2 | 0 | 0 | 0 | 2 | 0 |
| Inventory / Heat recovery units | 2 | 0 | 0 | 0 | 2 | 0 |
| Inventory / Junction components and junction boxes | 2 | 0 | 0 | 0 | 2 | 0 |
| Inventory / Measuring equipment | 2 | 0 | 0 | 0 | 2 | 0 |
| Inventory / Mechanical and unitary equipment | 2 | 0 | 0 | 0 | 2 | 0 |
| Inventory / Parking equipment and areas | 2 | 0 | 0 | 0 | 2 | 0 |
| Inventory / Vertical circulation types, counts and subcomponents | 2 | 0 | 0 | 0 | 2 | 0 |
| Inventory / Waste terminals | 2 | 0 | 0 | 0 | 2 | 0 |
| Inventory / Water heaters and water-heating systems | 2 | 0 | 0 | 0 | 2 | 0 |
| Inventory / Apartments by level and elevation | 1 | 0 | 0 | 0 | 1 | 0 |
| Inventory / Boilers, specifications and locations | 1 | 0 | 0 | 0 | 1 | 0 |
| Inventory / Controllers | 1 | 0 | 0 | 0 | 1 | 0 |
| Inventory / Data and communication devices | 1 | 0 | 0 | 0 | 1 | 0 |
| Inventory / Heating sensors | 1 | 0 | 0 | 0 | 1 | 0 |
| Inventory / Radiator types and quantities | 1 | 0 | 0 | 0 | 1 | 0 |
| Inventory / Tanks | 1 | 0 | 0 | 0 | 1 | 0 |
| Inventory / Town roads and paths | 1 | 0 | 0 | 0 | 1 | 0 |
| Inventory / Town water features | 1 | 0 | 0 | 0 | 1 | 0 |
| Inventory / Wall thickness distribution | 1 | 0 | 0 | 0 | 1 | 0 |
| Length / All walls on one level | 64 | 0 | 0 | 64 | 0 | 0 |
| Length / Exterior walls | 7 | 0 | 0 | 0 | 7 | 0 |
| Length / Plumbing pipe network, optionally with segment statistics | 4 | 0 | 0 | 0 | 4 | 0 |
| Length / Exterior and interior walls together or compared | 3 | 0 | 0 | 0 | 3 | 0 |
| Length / Interior walls | 3 | 0 | 0 | 0 | 3 | 0 |
| Length / Heating pipe network, optionally with segment statistics | 2 | 0 | 0 | 0 | 2 | 0 |
| Length / Pipes (system unspecified) | 2 | 0 | 0 | 0 | 2 | 0 |
| Length / Ventilation ductwork, optionally with segment statistics | 2 | 0 | 0 | 0 | 2 | 0 |
| Length / Electrical conduits, optionally with segment statistics | 1 | 0 | 0 | 0 | 1 | 0 |
| Length / Flexible cable pipes, quantities and proportions | 1 | 0 | 0 | 0 | 1 | 0 |
| Length / Pipes and ducts together | 1 | 0 | 0 | 0 | 1 | 0 |
| Length / Skirting boards | 1 | 0 | 0 | 0 | 1 | 0 |
| Length / Steel beams by type | 1 | 0 | 0 | 0 | 1 | 0 |
| Overview / Project, location, building function or historical identity | 13 | 0 | 0 | 0 | 13 | 0 |
| Overview / Structural system, concept or efficiency | 8 | 0 | 0 | 0 | 8 | 0 |
| Overview / Building metrics combining counts, areas or elevations | 5 | 0 | 0 | 0 | 5 | 0 |
| Overview / Residential or level layout and organization | 5 | 0 | 0 | 0 | 5 | 0 |
| Overview / Town defensive layout and strategy | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Wall materials and construction layers | 27 | 0 | 0 | 0 | 27 | 0 |
| Property / Building level heights and elevations | 14 | 0 | 0 | 0 | 14 | 0 |
| Property / Door fire ratings or rating availability | 14 | 0 | 0 | 0 | 13 | 1 |
| Property / Model software and IFC standards | 14 | 0 | 0 | 0 | 14 | 0 |
| Property / Ceiling materials or systems | 13 | 0 | 0 | 0 | 12 | 1 |
| Property / Wall thicknesses or layer dimensions | 13 | 0 | 0 | 0 | 13 | 0 |
| Property / Window fire ratings or rating availability | 11 | 0 | 0 | 0 | 11 | 0 |
| Property / Door width or dimensions | 5 | 0 | 0 | 0 | 2 | 3 |
| Property / Electrical loads, optionally equipment or floor breakdowns | 5 | 0 | 0 | 0 | 5 | 0 |
| Property / Room wall or floor finishes | 5 | 0 | 0 | 0 | 2 | 3 |
| Property / External-wall insulation type or thickness | 4 | 0 | 0 | 0 | 4 | 0 |
| Property / Room and ceiling heights | 4 | 0 | 0 | 0 | 4 | 0 |
| Property / Column dimensions | 3 | 0 | 0 | 0 | 3 | 0 |
| Property / Construction phasing and renovation status | 3 | 0 | 0 | 0 | 3 | 0 |
| Property / Maintenance requirements or schedules | 3 | 0 | 0 | 0 | 3 | 0 |
| Property / Wall load-bearing status | 3 | 0 | 0 | 0 | 3 | 0 |
| Property / Window glazing type | 3 | 0 | 0 | 0 | 3 | 0 |
| Property / Window height or dimensions | 3 | 0 | 0 | 0 | 2 | 1 |
| Property / Door or frame material | 2 | 0 | 0 | 0 | 0 | 2 |
| Property / Energy consumption or efficiency | 2 | 0 | 0 | 0 | 2 | 0 |
| Property / Fire protection or suppression system | 2 | 0 | 0 | 0 | 2 | 0 |
| Property / Heating capacity or equipment specifications | 2 | 0 | 0 | 0 | 2 | 0 |
| Property / Roof material lifespan | 2 | 0 | 0 | 0 | 2 | 0 |
| Property / Wall fire ratings or rating availability | 2 | 0 | 0 | 0 | 2 | 0 |
| Property / Beam spans and sizes | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Building envelope airtightness | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Building thermal bridges | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Ceiling GUID | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Conduit materials and applications | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Defensive wall heights | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Door hardware group | 1 | 0 | 0 | 0 | 0 | 1 |
| Property / Door type and description | 1 | 0 | 0 | 0 | 0 | 1 |
| Property / Electrical distribution capacity availability | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Electrical voltage levels | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Floor live-load capacity | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Foundation depth | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Foundation materials | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Light-fixture presence | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Parking dimensions and capacity | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Pipe materials and quantities | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Renewable-energy systems presence | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Residential-building construction materials | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Slab materials | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Steel beams spanning a specified room | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Structural materials | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Structural reinforcement for medical equipment | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Toilet water efficiency | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Ventilation insulation and coverage | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Ventilation requirements | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Waiting-area capacities | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Wall acoustic rating | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Window solar heat gain coefficient | 1 | 0 | 0 | 0 | 1 | 0 |
| Property / Window warranty | 1 | 0 | 0 | 0 | 1 | 0 |
| Ranking / Door widths, extrema, top-k or statistics | 13 | 0 | 0 | 0 | 13 | 0 |
| Ranking / Largest room or rooms by area | 9 | 0 | 0 | 0 | 8 | 1 |
| Ranking / Window widths, extrema or top-k | 8 | 0 | 0 | 0 | 8 | 0 |
| Ranking / Rooms with highest or lowest ceilings | 6 | 0 | 0 | 0 | 6 | 0 |
| Spatial / Equipment locations | 4 | 0 | 0 | 0 | 4 | 0 |
| Spatial / Emergency-exit route distance | 3 | 0 | 0 | 0 | 3 | 0 |
| Spatial / Fire exits and their locations | 2 | 0 | 0 | 0 | 2 | 0 |
| Spatial / Room adjacency or connectivity | 2 | 0 | 0 | 0 | 2 | 0 |
| Spatial / Rooms served by thermostats or air systems | 2 | 0 | 0 | 0 | 2 | 0 |
| Spatial / Emergency escape-route width | 1 | 0 | 0 | 0 | 1 | 0 |
| Spatial / Fire-extinguisher presence and locations | 1 | 0 | 0 | 0 | 1 | 0 |
| Spatial / Highest-ground buildings and location | 1 | 0 | 0 | 0 | 1 | 0 |
| Spatial / Nearest town gate | 1 | 0 | 0 | 0 | 1 | 0 |
| Spatial / Rooms with direct outdoor access | 1 | 0 | 0 | 0 | 1 | 0 |
| Spatial / Server-room location and identifier | 1 | 0 | 0 | 0 | 1 | 0 |
| Sustainability / Material recyclability | 1 | 0 | 0 | 0 | 1 | 0 |
| Sustainability / Recycled material content | 1 | 0 | 0 | 0 | 1 | 0 |
| Volume / Net slab volume | 72 | 0 | 0 | 72 | 0 | 0 |
| Volume / Net wall volume | 66 | 0 | 0 | 66 | 0 | 0 |
| Volume / Slabs, optionally grouped by type or level | 11 | 0 | 0 | 0 | 11 | 0 |
| Volume / Concrete across structural components | 4 | 0 | 0 | 0 | 4 | 0 |
| Volume / Foundation concrete | 3 | 0 | 0 | 0 | 3 | 0 |
| Volume / Insulation | 2 | 0 | 0 | 0 | 2 | 0 |
| Volume / Wall concrete | 1 | 0 | 0 | 0 | 1 | 0 |
| **Total** | 127,044 | 85,514 | 37,584 | 3,062 | 820 | 64 |

## Swiss room-label questions without losing the original labels

Counts below cover Swiss Dwellings only. Count-label and sum-by-label columns are subsets of the corresponding family totals; individual-room area queries belong to "Area / One room or space". English and local-language rows both count. Only surrounding guillemet spacing is trimmed.

| Literal label | Semantic room group | Count questions | One-room area questions | Sum-area questions |
| --- | --- | --- | --- | --- |
| Arkade | Arcades | 0 | 2 | 0 |
| Balcon | Balconies | 318 | 116 | 0 |
| Balcone | Balconies | 118 | 20 | 0 |
| Balkon | Balconies | 920 | 258 | 0 |
| Bad | Bathrooms and washrooms | 1,210 | 446 | 0 |
| Bagno | Bathrooms and washrooms | 160 | 68 | 0 |
| Bain | Bathrooms and washrooms | 416 | 144 | 0 |
| Camera da letto | Bedrooms | 46 | 22 | 46 |
| Chambre à coucher | Bedrooms | 126 | 48 | 126 |
| Schlafzimmer | Bedrooms | 350 | 166 | 350 |
| Compartiment cave | Cellar rooms | 0 | 2 | 0 |
| Kellerabteil | Cellar rooms | 4 | 0 | 0 |
| Vano cantina | Cellar rooms | 2 | 4 | 0 |
| Corridoio | Corridors | 168 | 66 | 0 |
| Couloir | Corridors | 454 | 138 | 0 |
| Korridor | Corridors | 1,238 | 496 | 0 |
| Essen | Dining rooms | 0 | 22 | 0 |
| Repas | Dining rooms | 0 | 4 | 0 |
| Hall | Entrance halls | 0 | 2 | 0 |
| Local | Generic labelled rooms (not necessarily bedrooms) | 0 | 6 | 0 |
| Pièce | Generic labelled rooms (not necessarily bedrooms) | 356 | 236 | 354 |
| Raum | Generic labelled rooms (not necessarily bedrooms) | 0 | 16 | 0 |
| Stanza | Generic labelled rooms (not necessarily bedrooms) | 142 | 74 | 142 |
| Zimmer | Generic labelled rooms (not necessarily bedrooms) | 1,044 | 602 | 1,016 |
| Küche/Essen | Kitchen and dining rooms together | 8 | 2 | 0 |
| Cucina | Kitchens | 180 | 64 | 0 |
| Cuisine | Kitchens | 466 | 118 | 0 |
| Küche | Kitchens | 1,318 | 310 | 0 |
| Buanderie | Laundry rooms | 0 | 2 | 0 |
| Soggiorno/pranzo | Living and dining rooms together | 90 | 16 | 0 |
| Séjour/repas | Living and dining rooms together | 272 | 78 | 0 |
| Wohnen/Essen | Living and dining rooms together | 702 | 162 | 0 |
| Soggiorno | Living rooms | 52 | 12 | 0 |
| Séjour | Living rooms | 124 | 30 | 0 |
| Wohnen | Living rooms | 362 | 100 | 0 |
| Loggia | Loggias | 204 | 42 | 0 |
| Büro | Office rooms and office areas | 0 | 2 | 0 |
| Bürofläche | Office rooms and office areas | 0 | 2 | 0 |
| Sitzplatz | Seating areas | 0 | 2 | 0 |
| Cage d'escalier | Stairwell rooms | 276 | 14 | 0 |
| Treppenhaus | Stairwell rooms | 882 | 76 | 0 |
| Vano scala | Stairwell rooms | 126 | 14 | 0 |
| Reduit | Storage rooms | 422 | 88 | 0 |
| Ripostiglio | Storage rooms | 52 | 14 | 0 |
| Réduit | Storage rooms | 122 | 34 | 0 |
| Terrasse | Terraces | 0 | 6 | 0 |
| Terrazza | Terraces | 0 | 2 | 0 |
| Jardin d'hiver | Winter gardens | 0 | 2 | 0 |
| Wintergarten | Winter gardens | 0 | 2 | 0 |
| **Total** |  | 12,730 | 4,152 | 2,034 |

## Quantitative IFC count scope

Only the structured `ifc_models` source is included here. Explicit whole-model questions and floor/view questions remain separate even when their referenced file is a single floor PDF. IFC-Bench and schedule counts are covered in the family/catalog tables.

| Count target | Floor/view rows | Whole-model rows | Total |
| --- | --- | --- | --- |
| Beams | 0 | 29 | 29 |
| Columns | 43 | 27 | 70 |
| Doors | 86 | 37 | 123 |
| Light fixtures | 0 | 6 | 6 |
| Rooms and spaces | 95 | 41 | 136 |
| Sanitary fixtures (combined) | 0 | 12 | 12 |
| Stairs | 62 | 33 | 95 |
| Walls | 59 | 39 | 98 |
| Windows | 39 | 34 | 73 |

## Exhaustive wording and template catalog

Every supplied row is represented below. For CubiCasa, IFC-Bench, and Opening Design, each entry is one exact question text. Swiss and quantitative IFC entries group only reviewed parameterized templates; each shows a verbatim example, its row count, number of distinct wordings/parameter values, and the first one-based source line. Swiss labels are expanded separately above. The classifier can additionally export every original row and its assigned family.

An example is not a promise that every row has the same room ID or scope. Follow its family and, for quantitative IFC counts, the separately preserved floor/model scope. No answers are included.

### CubiCasa5K

<details>
<summary>85,514 rows in 24 exact texts or parameterized templates</summary>

| Family | Verbatim question or example | Rows | Distinct question texts | First JSONL line |
| --- | --- | --- | --- | --- |
| Count / Balconies | How many balconies (parveke, including glazed balconies) are on this floor plan? | 1,462 | 1 | 21 |
| Count / Balconies | Kuinka monta parveketta (myös lasitetut parvekkeet) pohjapiirustuksessa on? | 1,462 | 1 | 22 |
| Count / Bathrooms and washrooms | How many bathrooms or washrooms (e.g. KH, KPH, PH, PESUH, SH) are on this floor plan, not counting separate WC rooms? | 2,384 | 1 | 51 |
| Count / Bathrooms and washrooms | Kuinka monta kylpy- tai pesuhuonetta (esim. KH, KPH, PH, PESUH, SH) pohjapiirustuksessa on, erillisiä WC-tiloja lukuun ottamatta? | 2,384 | 1 | 52 |
| Count / Bedrooms | How many bedrooms (makuuhuone, usually marked MH) are on this floor plan? | 2,960 | 1 | 5 |
| Count / Bedrooms | Kuinka monta makuuhuonetta (MH) pohjapiirustuksessa on? | 2,960 | 1 | 6 |
| Count / Doors | How many doors are shown on this floor plan? Count doorways fitted with a door; open doorways without a door leaf do not count. | 3,519 | 1 | 1 |
| Count / Doors | Kuinka monta ovea pohjapiirustuksessa on? Laske oviaukot, joissa on ovi; pelkkiä oviaukkoja ilman ovilehteä ei lasketa. | 3,519 | 1 | 2 |
| Count / Floors and storeys shown | How many floors (storeys) does this floor plan show? | 4,787 | 1 | 13 |
| Count / Floors and storeys shown | Kuinka monta kerrosta pohjapiirustuksessa on esitetty? | 4,787 | 1 | 14 |
| Count / Kitchens | How many kitchens (including kitchenettes, open kitchens and utility kitchens) are on this floor plan? | 3,262 | 1 | 49 |
| Count / Kitchens | Kuinka monta keittiötä (myös keittokomerot, avo- ja tupakeittiöt sekä apukeittiöt) pohjapiirustuksessa on? | 3,262 | 1 | 50 |
| Count / Saunas | How many saunas are on this floor plan? | 3,315 | 1 | 7 |
| Count / Saunas | Kuinka monta saunaa pohjapiirustuksessa on? | 3,315 | 1 | 8 |
| Count / Separate toilet rooms | How many separate WC rooms (toilet rooms marked WC) are on this floor plan? | 2,332 | 1 | 53 |
| Count / Separate toilet rooms | Kuinka monta erillistä WC-tilaa pohjapiirustuksessa on? | 2,332 | 1 | 54 |
| Count / Showers and bathtubs together | How many showers and bathtubs are drawn on this floor plan in total? | 4,442 | 1 | 27 |
| Count / Showers and bathtubs together | Kuinka monta suihkua ja kylpyammetta pohjapiirustukseen on piirretty yhteensä? | 4,442 | 1 | 28 |
| Count / Sinks and washbasins | How many sinks and wash basins (kitchen and bathroom combined; a double-bowl sink counts as one) are drawn on this floor plan? | 4,725 | 1 | 11 |
| Count / Sinks and washbasins | Kuinka monta pesu- ja tiskiallasta (keittiö ja kylpytilat yhteensä; kaksoisallas lasketaan yhdeksi) pohjapiirustukseen on piirretty? | 4,725 | 1 | 12 |
| Count / Toilet bowls and WC fixtures | How many toilet bowls (WC seats) are drawn on this floor plan? | 4,782 | 1 | 9 |
| Count / Toilet bowls and WC fixtures | Kuinka monta WC-istuinta pohjapiirustukseen on piirretty? | 4,782 | 1 | 10 |
| Count / Windows | How many windows are shown on this floor plan? | 4,787 | 1 | 3 |
| Count / Windows | Kuinka monta ikkunaa pohjapiirustuksessa on? | 4,787 | 1 | 4 |

</details>

### Swiss Dwellings

<details>
<summary>37,584 rows in 161 exact texts or parameterized templates</summary>

| Family | Verbatim question or example | Rows | Distinct question texts | First JSONL line |
| --- | --- | --- | --- | --- |
| Area / Net apartment floor area excluding outdoor spaces | Qual è la superficie netta dell'appartamento A in m² (somma di tutti i locali, esclusi balconi, logge, terrazze e altri spazi esterni)? | 166 | 7 | 89530 |
| Area / Net apartment floor area excluding outdoor spaces | Quelle est la surface nette de l'appartement C en m² (somme de toutes ses pièces, hors balcons, loggias, terrasses et autres espaces extérieurs) ? | 450 | 13 | 89568 |
| Area / Net apartment floor area excluding outdoor spaces | What is the net floor area of apartment B in m², summing all its rooms except balconies, loggias, terraces and other outdoor spaces? | 1,875 | 14 | 89495 |
| Area / Net apartment floor area excluding outdoor spaces | Wie gross ist die Nettowohnfläche von Wohnung B in m² (Summe aller Räume ohne Balkone, Loggien, Terrassen und andere Aussenräume)? | 1,259 | 10 | 89496 |
| Area / Net indoor floor area excluding outdoor spaces, shafts and voids | Qual è la superficie netta totale in m² di tutti i locali interni numerati di questo piano (esclusi balconi, logge, terrazze e altri spazi esterni, cavedi e vuoti)? | 95 | 1 | 89534 |
| Area / Net indoor floor area excluding outdoor spaces, shafts and voids | Quelle est la surface nette totale en m² de toutes les pièces intérieures numérotées de cet étage (hors balcons, loggias, terrasses et autres espaces extérieurs, gaines et vides) ? | 247 | 1 | 89574 |
| Area / Net indoor floor area excluding outdoor spaces, shafts and voids | What is the total net floor area in m² of all numbered indoor rooms on this floor (excluding balconies, loggias, terraces and other outdoor spaces, shafts and voids)? | 1,040 | 1 | 89501 |
| Area / Net indoor floor area excluding outdoor spaces, shafts and voids | Wie gross ist die gesamte Nettogeschossfläche in m² aller nummerierten Innenräume dieses Geschosses (ohne Balkone, Loggien, Terrassen und andere Aussenräume, Schächte und Lufträume)? | 698 | 1 | 89502 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 0.01 («Arkade») in m²? | 1 | 1 | 117582 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 7.01 («Balkon») in m²? | 129 | 102 | 89492 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 2.06 («Bad») in m²? | 223 | 124 | 89872 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 1.01 («Schlafzimmer») in m²? | 83 | 62 | 90990 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 7.16 («Korridor») in m²? | 248 | 144 | 89494 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 1.20 («Essen») in m²? | 11 | 11 | 91816 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 2.13 («Zimmer») in m²? | 309 | 168 | 89638 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 5.01 («Küche/Essen») in m²? | 1 | 1 | 115660 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 3.02 («Küche») in m²? | 155 | 99 | 89736 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 2.37 («Wohnen/Essen») in m²? | 81 | 63 | 89700 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 5.04 («Wohnen») in m²? | 50 | 43 | 90954 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 4.01 («Loggia») in m²? | 13 | 13 | 89838 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 2.31 («Büro») in m²? | 2 | 2 | 89636 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 0.32 («Sitzplatz») in m²? | 1 | 1 | 118444 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 2.09 («Treppenhaus») in m²? | 38 | 35 | 89874 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 0.16 («Reduit») in m²? | 44 | 40 | 89910 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 3.12 («Terrasse») in m²? | 3 | 3 | 114170 |
| Area / One room or space | Wie gross ist die Nettofläche von Raum 0.01 («Wintergarten») in m²? | 1 | 1 | 93004 |
| Area / One room or space | What is the net floor area of room 0.01 ('Arkade') in m²? | 1 | 1 | 117581 |
| Area / One room or space | What is the net floor area of room 7.01 ('Balkon') in m²? | 197 | 160 | 89491 |
| Area / One room or space | What is the net floor area of room 2.06 ('Bad') in m²? | 329 | 218 | 89871 |
| Area / One room or space | What is the net floor area of room 1.02 ('Camera da letto') in m²? | 118 | 93 | 89525 |
| Area / One room or space | What is the net floor area of room 0.14 ('Vano cantina') in m²? | 3 | 3 | 90275 |
| Area / One room or space | What is the net floor area of room 7.16 ('Korridor') in m²? | 350 | 229 | 89493 |
| Area / One room or space | What is the net floor area of room 1.20 ('Essen') in m²? | 13 | 13 | 91815 |
| Area / One room or space | What is the net floor area of room 1.20 ('Hall') in m²? | 1 | 1 | 93081 |
| Area / One room or space | What is the net floor area of room 2.13 ('Zimmer') in m²? | 467 | 293 | 89637 |
| Area / One room or space | What is the net floor area of room 5.01 ('Küche/Essen') in m²? | 1 | 1 | 115659 |
| Area / One room or space | What is the net floor area of room 3.02 ('Küche') in m²? | 246 | 172 | 89735 |
| Area / One room or space | What is the net floor area of room 2.28 ('Buanderie') in m²? | 1 | 1 | 101915 |
| Area / One room or space | What is the net floor area of room 5.10 ('Séjour/repas') in m²? | 128 | 105 | 89563 |
| Area / One room or space | What is the net floor area of room 0.18 ('Séjour') in m²? | 71 | 64 | 90311 |
| Area / One room or space | What is the net floor area of room 4.01 ('Loggia') in m²? | 21 | 20 | 89837 |
| Area / One room or space | What is the net floor area of room 2.31 ('Büro') in m²? | 2 | 2 | 89635 |
| Area / One room or space | What is the net floor area of room 0.32 ('Sitzplatz') in m²? | 1 | 1 | 118443 |
| Area / One room or space | What is the net floor area of room 1.07 ('Vano scala') in m²? | 52 | 48 | 89527 |
| Area / One room or space | What is the net floor area of room 5.01 ('Réduit') in m²? | 68 | 63 | 89565 |
| Area / One room or space | What is the net floor area of room 3.08 ('Terrazza') in m²? | 4 | 4 | 112853 |
| Area / One room or space | What is the net floor area of room 3.24 ('Jardin d'hiver') in m²? | 2 | 2 | 92925 |
| Area / One room or space | Quelle est la surface nette de la pièce 1.01 (« Balcon ») en m² ? | 58 | 48 | 89602 |
| Area / One room or space | Quelle est la surface nette de la pièce 3.16 (« Bain ») en m² ? | 72 | 63 | 90822 |
| Area / One room or space | Quelle est la surface nette de la pièce 2.01 (« Chambre à coucher ») en m² ? | 24 | 21 | 90196 |
| Area / One room or space | Quelle est la surface nette de la pièce U2.31 (« Compartiment cave ») en m² ? | 1 | 1 | 124670 |
| Area / One room or space | Quelle est la surface nette de la pièce 1.36 (« Couloir ») en m² ? | 69 | 55 | 89604 |
| Area / One room or space | Quelle est la surface nette de la pièce 3.52 (« Repas ») en m² ? | 2 | 2 | 94962 |
| Area / One room or space | Quelle est la surface nette de la pièce 1.20 (« Hall ») en m² ? | 1 | 1 | 93082 |
| Area / One room or space | Quelle est la surface nette de la pièce 6.01 (« Pièce ») en m² ? | 121 | 94 | 90054 |
| Area / One room or space | Quelle est la surface nette de la pièce 6.04 (« Cuisine ») en m² ? | 59 | 44 | 90052 |
| Area / One room or space | Quelle est la surface nette de la pièce 2.28 (« Buanderie ») en m² ? | 1 | 1 | 101916 |
| Area / One room or space | Quelle est la surface nette de la pièce 5.10 (« Séjour/repas ») en m² ? | 39 | 34 | 89564 |
| Area / One room or space | Quelle est la surface nette de la pièce 0.18 (« Séjour ») en m² ? | 15 | 15 | 90312 |
| Area / One room or space | Quelle est la surface nette de la pièce 2.01 (« Loggia ») en m² ? | 6 | 6 | 90926 |
| Area / One room or space | Quelle est la surface nette de la pièce 5.20 (« Cage d'escalier ») en m² ? | 7 | 6 | 90784 |
| Area / One room or space | Quelle est la surface nette de la pièce 5.01 (« Réduit ») en m² ? | 17 | 16 | 89566 |
| Area / One room or space | Quelle est la surface nette de la pièce 3.24 (« Jardin d'hiver ») en m² ? | 1 | 1 | 92926 |
| Area / One room or space | Qual è la superficie netta del locale 4.17 («Balcone») in m²? | 10 | 10 | 94200 |
| Area / One room or space | Qual è la superficie netta del locale 3.05 («Bagno») in m²? | 34 | 31 | 91094 |
| Area / One room or space | Qual è la superficie netta del locale 1.02 («Camera da letto») in m²? | 11 | 10 | 89526 |
| Area / One room or space | Qual è la superficie netta del locale 0.14 («Vano cantina») in m²? | 2 | 2 | 90276 |
| Area / One room or space | Qual è la superficie netta del locale 3.04 («Corridoio») in m²? | 33 | 30 | 91096 |
| Area / One room or space | Qual è la superficie netta del locale 5.11 («Stanza») in m²? | 37 | 31 | 89806 |
| Area / One room or space | Qual è la superficie netta del locale 3.11 («Cucina») in m²? | 32 | 29 | 91674 |
| Area / One room or space | Qual è la superficie netta del locale 2.02 («Soggiorno/pranzo») in m²? | 8 | 8 | 95180 |
| Area / One room or space | Qual è la superficie netta del locale 3.03 («Soggiorno») in m²? | 6 | 6 | 91890 |
| Area / One room or space | Qual è la superficie netta del locale 3.32 («Loggia») in m²? | 2 | 2 | 107436 |
| Area / One room or space | Qual è la superficie netta del locale 1.07 («Vano scala») in m²? | 7 | 7 | 89528 |
| Area / One room or space | Qual è la superficie netta del locale U1.01 («Ripostiglio») in m²? | 7 | 7 | 93732 |
| Area / One room or space | Qual è la superficie netta del locale 3.08 («Terrazza») in m²? | 1 | 1 | 112854 |
| Area / Sum of labelled rooms: bedrooms | Wie gross ist die gesamte Nettofläche in m² aller Räume mit der Bezeichnung «Schlafzimmer» in diesem Geschoss? | 175 | 1 | 89500 |
| Area / Sum of labelled rooms: bedrooms | What is the total net area in m² of all rooms labelled 'Schlafzimmer' on this floor? | 261 | 3 | 89499 |
| Area / Sum of labelled rooms: bedrooms | Quelle est la surface nette totale en m² de toutes les pièces désignées « Chambre à coucher » à cet étage ? | 63 | 1 | 89610 |
| Area / Sum of labelled rooms: bedrooms | Qual è la superficie netta totale in m² di tutti i locali denominati «Camera da letto» in questo piano? | 23 | 1 | 89532 |
| Area / Sum of labelled rooms: generic labelled rooms (not necessarily bedrooms) | Wie gross ist die gesamte Nettofläche in m² aller Räume mit der Bezeichnung «Zimmer» in diesem Geschoss? | 508 | 1 | 89644 |
| Area / Sum of labelled rooms: generic labelled rooms (not necessarily bedrooms) | What is the total net area in m² of all rooms labelled 'Pièce' on this floor? | 756 | 3 | 89571 |
| Area / Sum of labelled rooms: generic labelled rooms (not necessarily bedrooms) | Quelle est la surface nette totale en m² de toutes les pièces désignées « Pièce » à cet étage ? | 177 | 1 | 89572 |
| Area / Sum of labelled rooms: generic labelled rooms (not necessarily bedrooms) | Qual è la superficie netta totale in m² di tutti i locali denominati «Stanza» in questo piano? | 71 | 1 | 89814 |
| Count / Apartments and residential units | Combien d'appartements (logements) figurent sur ce plan d'étage ? | 247 | 1 | 89536 |
| Count / Apartments and residential units | How many apartments (residential units) are shown on this floor plan? | 1,040 | 1 | 89461 |
| Count / Apartments and residential units | Quanti appartamenti (unità abitative) sono rappresentati in questa pianta? | 95 | 1 | 89504 |
| Count / Apartments and residential units | Wie viele Wohnungen sind auf diesem Grundriss dargestellt? | 698 | 1 | 89462 |
| Count / Balconies | Wie viele Räume mit der Bezeichnung «Balkon» gibt es in diesem Geschoss? | 460 | 1 | 89474 |
| Count / Balconies | How many rooms labelled 'Balkon' are there on this floor? | 678 | 3 | 89473 |
| Count / Balconies | Combien de pièces portant la désignation « Balcon » y a-t-il à cet étage ? | 159 | 1 | 89586 |
| Count / Balconies | Quanti locali con la denominazione «Balcone» ci sono in questo piano? | 59 | 1 | 89792 |
| Count / Bathrooms and washrooms | Wie viele Räume mit der Bezeichnung «Bad» gibt es in diesem Geschoss? | 605 | 1 | 89470 |
| Count / Bathrooms and washrooms | How many rooms labelled 'Bad' are there on this floor? | 893 | 3 | 89469 |
| Count / Bathrooms and washrooms | Combien de pièces portant la désignation « Bain » y a-t-il à cet étage ? | 208 | 1 | 89546 |
| Count / Bathrooms and washrooms | Quanti locali con la denominazione «Bagno» ci sono in questo piano? | 80 | 1 | 89510 |
| Count / Bathtubs | Combien de baignoires sont dessinées sur ce plan ? | 224 | 1 | 89560 |
| Count / Bathtubs | How many bathtubs are drawn on this floor plan? | 897 | 1 | 89487 |
| Count / Bathtubs | Quante vasche da bagno sono disegnate in questa pianta? | 83 | 1 | 89524 |
| Count / Bathtubs | Wie viele Badewannen sind auf diesem Grundriss eingezeichnet? | 590 | 1 | 89488 |
| Count / Bedrooms | Wie viele Räume mit der Bezeichnung «Schlafzimmer» gibt es in diesem Geschoss? | 175 | 1 | 89464 |
| Count / Bedrooms | How many rooms labelled 'Schlafzimmer' are there on this floor? | 261 | 3 | 89463 |
| Count / Bedrooms | Combien de pièces portant la désignation « Chambre à coucher » y a-t-il à cet étage ? | 63 | 1 | 89578 |
| Count / Bedrooms | Quanti locali con la denominazione «Camera da letto» ci sono in questo piano? | 23 | 1 | 89506 |
| Count / Cellar rooms | Wie viele Räume mit der Bezeichnung «Kellerabteil» gibt es in diesem Geschoss? | 2 | 1 | 92800 |
| Count / Cellar rooms | How many rooms labelled 'Vano cantina' are there on this floor? | 3 | 2 | 90261 |
| Count / Cellar rooms | Quanti locali con la denominazione «Vano cantina» ci sono in questo piano? | 1 | 1 | 90262 |
| Count / Corridors | Wie viele Räume mit der Bezeichnung «Korridor» gibt es in diesem Geschoss? | 619 | 1 | 89476 |
| Count / Corridors | How many rooms labelled 'Korridor' are there on this floor? | 930 | 3 | 89475 |
| Count / Corridors | Combien de pièces portant la désignation « Couloir » y a-t-il à cet étage ? | 227 | 1 | 89548 |
| Count / Corridors | Quanti locali con la denominazione «Corridoio» ci sono in questo piano? | 84 | 1 | 89512 |
| Count / Doors | Combien de portes (portes intérieures et portes d'entrée confondues) sont dessinées sur ce plan ? | 247 | 1 | 89552 |
| Count / Doors | How many doors (interior doors and entrance doors together) are drawn on this floor plan? | 1,040 | 1 | 89479 |
| Count / Doors | Quante porte (porte interne e porte d'ingresso insieme) sono disegnate in questa pianta? | 95 | 1 | 89516 |
| Count / Doors | Wie viele Türen (Innentüren und Eingangstüren zusammen) sind auf diesem Grundriss eingezeichnet? | 698 | 1 | 89480 |
| Count / Generic labelled rooms (not necessarily bedrooms) | Wie viele Räume mit der Bezeichnung «Zimmer» gibt es in diesem Geschoss? | 522 | 1 | 89616 |
| Count / Generic labelled rooms (not necessarily bedrooms) | How many rooms labelled 'Pièce' are there on this floor? | 771 | 3 | 89537 |
| Count / Generic labelled rooms (not necessarily bedrooms) | Combien de pièces portant la désignation « Pièce » y a-t-il à cet étage ? | 178 | 1 | 89538 |
| Count / Generic labelled rooms (not necessarily bedrooms) | Quanti locali con la denominazione «Stanza» ci sono in questo piano? | 71 | 1 | 89788 |
| Count / Kitchen and dining rooms together | Wie viele Räume mit der Bezeichnung «Küche/Essen» gibt es in diesem Geschoss? | 4 | 1 | 104726 |
| Count / Kitchen and dining rooms together | How many rooms labelled 'Küche/Essen' are there on this floor? | 4 | 1 | 104725 |
| Count / Kitchens | Wie viele Räume mit der Bezeichnung «Küche» gibt es in diesem Geschoss? | 659 | 1 | 89468 |
| Count / Kitchens | How many rooms labelled 'Küche' are there on this floor? | 982 | 3 | 89467 |
| Count / Kitchens | Combien de pièces portant la désignation « Cuisine » y a-t-il à cet étage ? | 233 | 1 | 89544 |
| Count / Kitchens | Quanti locali con la denominazione «Cucina» ci sono in questo piano? | 90 | 1 | 89508 |
| Count / Living and dining rooms together | Wie viele Räume mit der Bezeichnung «Wohnen/Essen» gibt es in diesem Geschoss? | 351 | 1 | 89618 |
| Count / Living and dining rooms together | How many rooms labelled 'Séjour/repas' are there on this floor? | 532 | 3 | 89541 |
| Count / Living and dining rooms together | Combien de pièces portant la désignation « Séjour/repas » y a-t-il à cet étage ? | 136 | 1 | 89542 |
| Count / Living and dining rooms together | Quanti locali con la denominazione «Soggiorno/pranzo» ci sono in questo piano? | 45 | 1 | 90248 |
| Count / Living rooms | Wie viele Räume mit der Bezeichnung «Wohnen» gibt es in diesem Geschoss? | 181 | 1 | 89466 |
| Count / Living rooms | How many rooms labelled 'Wohnen' are there on this floor? | 269 | 3 | 89465 |
| Count / Living rooms | Combien de pièces portant la désignation « Séjour » y a-t-il à cet étage ? | 62 | 1 | 89540 |
| Count / Living rooms | Quanti locali con la denominazione «Soggiorno» ci sono in questo piano? | 26 | 1 | 89962 |
| Count / Loggias | Wie viele Räume mit der Bezeichnung «Loggia» gibt es in diesem Geschoss? | 62 | 1 | 89824 |
| Count / Loggias | How many rooms labelled 'Loggia' are there on this floor? | 102 | 1 | 89823 |
| Count / Loggias | Combien de pièces portant la désignation « Loggia » y a-t-il à cet étage ? | 35 | 1 | 90296 |
| Count / Loggias | Quanti locali con la denominazione «Loggia» ci sono in questo piano? | 5 | 1 | 103304 |
| Count / Showers | Combien de douches sont dessinées sur ce plan ? | 72 | 1 | 89562 |
| Count / Showers | How many showers are drawn on this floor plan? | 322 | 1 | 89489 |
| Count / Showers | Quante docce sono disegnate in questa pianta? | 35 | 1 | 90274 |
| Count / Showers | Wie viele Duschen sind auf diesem Grundriss eingezeichnet? | 215 | 1 | 89490 |
| Count / Sinks and washbasins | Combien de lavabos sont dessinés sur ce plan ? | 247 | 1 | 89558 |
| Count / Sinks and washbasins | How many washbasins are drawn on this floor plan? | 1,040 | 1 | 89485 |
| Count / Sinks and washbasins | Quanti lavabi sono disegnati in questa pianta? | 95 | 1 | 89522 |
| Count / Sinks and washbasins | Wie viele Lavabos sind auf diesem Grundriss eingezeichnet? | 698 | 1 | 89486 |
| Count / Stairwell rooms | Wie viele Räume mit der Bezeichnung «Treppenhaus» gibt es in diesem Geschoss? | 441 | 1 | 89478 |
| Count / Stairwell rooms | How many rooms labelled 'Treppenhaus' are there on this floor? | 642 | 3 | 89477 |
| Count / Stairwell rooms | Combien de pièces portant la désignation « Cage d'escalier » y a-t-il à cet étage ? | 138 | 1 | 89550 |
| Count / Stairwell rooms | Quanti locali con la denominazione «Vano scala» ci sono in questo piano? | 63 | 1 | 89514 |
| Count / Storage rooms | Wie viele Räume mit der Bezeichnung «Reduit» gibt es in diesem Geschoss? | 211 | 1 | 89472 |
| Count / Storage rooms | How many rooms labelled 'Reduit' are there on this floor? | 298 | 3 | 89471 |
| Count / Storage rooms | Combien de pièces portant la désignation « Réduit » y a-t-il à cet étage ? | 61 | 1 | 90184 |
| Count / Storage rooms | Quanti locali con la denominazione «Ripostiglio» ci sono in questo piano? | 26 | 1 | 90254 |
| Count / Toilet bowls and WC fixtures | Combien de WC sont dessinés sur ce plan ? | 247 | 1 | 89556 |
| Count / Toilet bowls and WC fixtures | How many toilets (WC) are drawn on this floor plan? | 1,040 | 1 | 89483 |
| Count / Toilet bowls and WC fixtures | Quanti WC sono disegnati in questa pianta? | 95 | 1 | 89520 |
| Count / Toilet bowls and WC fixtures | Wie viele WCs sind auf diesem Grundriss eingezeichnet? | 698 | 1 | 89484 |
| Count / Windows | Combien de fenêtres sont dessinées sur ce plan ? | 247 | 1 | 89554 |
| Count / Windows | How many windows are drawn on this floor plan? | 1,040 | 1 | 89481 |
| Count / Windows | Quante finestre sono disegnate in questa pianta? | 95 | 1 | 89518 |
| Count / Windows | Wie viele Fenster sind auf diesem Grundriss eingezeichnet? | 698 | 1 | 89482 |

</details>

### IFC models

<details>
<summary>3,062 rows in 124 exact texts or parameterized templates</summary>

| Family | Verbatim question or example | Rows | Distinct question texts | First JSONL line |
| --- | --- | --- | --- | --- |
| Area / Net floor area of all spaces on one level | Hvad er det samlede nettoareal af alle rum på 'Kælder' i m²? | 8 | 8 | 87348 |
| Area / Net floor area of all spaces on one level | Jaka jest łączna powierzchnia netto wszystkich pomieszczeń na kondygnacji „-1” (w m²)? | 3 | 3 | 89358 |
| Area / Net floor area of all spaces on one level | Kui suur on kõigi ruumide netopõrandapind kokku korrusel „1.korrus“ (m²)? | 5 | 5 | 86790 |
| Area / Net floor area of all spaces on one level | Wat is de totale netto vloeroppervlakte van alle ruimtes op '00 Begane grond', in m²? | 5 | 5 | 87800 |
| Area / Net floor area of all spaces on one level | What is the total net floor area of all rooms (spaces) on 'Level 1', in m²? | 40 | 35 | 86355 |
| Area / Net floor area of all spaces on one level | Wie groß ist die gesamte Netto-Grundfläche aller Räume im Geschoss „B01_OKRD“ in m²? | 4 | 4 | 88078 |
| Area / Net floor area of all spaces on one level | ¿Cuál es la superficie útil total de todos los locales de la planta «P0», en m²? | 10 | 5 | 88492 |
| Area / Net side area of walls | Hvad er det samlede nettosideareal af alle vægge på 'Grundplan' i m²? | 7 | 7 | 87390 |
| Area / Net side area of walls | Wat is de totale netto zijoppervlakte van alle wanden op '00 Begane grond', in m²? | 6 | 6 | 87804 |
| Area / Net side area of walls | What is the total net side area of all walls on 'Grundplan', in m²? | 32 | 30 | 87389 |
| Area / Net side area of walls | Wie groß ist die gesamte Netto-Seitenfläche aller Wände im Geschoss „Erdgeschoss“ in m²? | 19 | 17 | 87850 |
| Area / One room or space | Hvad er nettoarealet af rummet 'Depot (Rum nr. K08)' på 'Kælder' i m²? | 117 | 117 | 87320 |
| Area / One room or space | Jaka jest powierzchnia netto pomieszczenia „Comunication (-1.1)” na kondygnacji „-1” (w m²)? | 19 | 19 | 89342 |
| Area / One room or space | Kui suur on ruumi „KORIDOR (119)“ netopõrandapind korrusel „1.korrus“ (m²)? | 285 | 285 | 86690 |
| Area / One room or space | Wat is de netto vloeroppervlakte van de ruimte 'werkkast (3)' op '00 Begane grond', in m²? | 223 | 223 | 87712 |
| Area / One room or space | What is the net floor area of the room 'Living Room (A102)' on 'Level 1', in m²? | 1,183 | 1117 | 86345 |
| Area / One room or space | Wie groß ist die Netto-Grundfläche des Raums „Küche (6)“ im Geschoss „Erdgeschoss“ in m²? | 110 | 110 | 87846 |
| Area / One room or space | ¿Cuál es la superficie útil del local «0GARAJE (01.11)» en la planta «P0», en m²? | 142 | 76 | 88486 |
| Count / Beams | Care este numărul de grinzi din modelul „BIM-Speed Barlad apartment block (architecture + MEP)”? | 1 | 1 | 89300 |
| Count / Beams | Hoeveel balken bevat het model 'Gymzaal Hambakendreef, Amersfoort (example project location)'? | 1 | 1 | 87702 |
| Count / Beams | How many beams are there in the model 'Duplex Apartment - architectural'? | 16 | 16 | 86339 |
| Count / Beams | Hvor mange bjælker er der i modellen 'Molio Demo-hus'? | 1 | 1 | 87308 |
| Count / Beams | Ile belek znajduje się w modelu „BIM-Speed Gdynia - semi-detached house Ruchu Oporu 18”? | 1 | 1 | 89330 |
| Count / Beams | Mitu tala on mudelis „Maleva tänav 18 korterelamu (Esplanades example model)“? | 1 | 1 | 86678 |
| Count / Beams | Wie viele Träger enthält das Modell „FZK-Haus (Simple Phantasy Building)“? | 6 | 6 | 87832 |
| Count / Beams | ¿Cuál es el número de vigas en el modelo «BIM-Speed Vitoria-Gasteiz - ALD26 (baseline, before renovation)»? | 2 | 2 | 88478 |
| Count / Columns | Care este numărul de stâlpi de pe planul nivelului „Level 1”? | 4 | 4 | 89308 |
| Count / Columns | Care este numărul de stâlpi din modelul „BIM-Speed Barlad apartment block (architecture + MEP)”? | 1 | 1 | 89298 |
| Count / Columns | Hoeveel kolommen staan er op de plattegrond van '00 Begane grond'? | 2 | 2 | 87710 |
| Count / Columns | Hoeveel kolommen bevat het model 'Gymzaal Hambakendreef, Amersfoort (example project location)'? | 1 | 1 | 87700 |
| Count / Columns | How many columns are shown on the floor plan of '1.korrus'? | 22 | 21 | 86685 |
| Count / Columns | How many columns are there in the model 'Medical-Dental Clinic - structural'? | 14 | 14 | 86660 |
| Count / Columns | Hvor mange søjler er vist på plantegningen for 'Kælder'? | 7 | 7 | 87318 |
| Count / Columns | Hvor mange søjler er der i modellen 'Molio Demo-hus'? | 1 | 1 | 87306 |
| Count / Columns | Mitu posti on mudelis „Maleva tänav 18 korterelamu (Esplanades example model)“? | 2 | 2 | 86676 |
| Count / Columns | Wie viele Stützen sind im Grundriss „Erdgeschoss“ dargestellt? | 8 | 7 | 87906 |
| Count / Columns | Wie viele Stützen enthält das Modell „Buerogebaeude (Phantasy Office Building, AC20-Institute-Var-2)“? | 6 | 6 | 87876 |
| Count / Columns | ¿Cuál es el número de pilares en el modelo «BIM-Speed Vitoria-Gasteiz - ALD26 (baseline, before renovation)»? | 2 | 2 | 88476 |
| Count / Doors | Hoeveel deuren staan er op de plattegrond van '00 Begane grond'? | 1 | 1 | 87706 |
| Count / Doors | Hoeveel deuren bevat het model 'Gymzaal Hambakendreef, Amersfoort (example project location)'? | 2 | 2 | 87692 |
| Count / Doors | How many doors are shown on the floor plan of 'Level 1'? | 47 | 40 | 86341 |
| Count / Doors | How many doors are there in the model 'Duplex Apartment - architectural'? | 17 | 17 | 86335 |
| Count / Doors | Hvor mange døre er vist på plantegningen for 'Kælder'? | 8 | 8 | 87312 |
| Count / Doors | Hvor mange døre er der i modellen 'Molio Demo-hus'? | 1 | 1 | 87298 |
| Count / Doors | Ile drzwi pokazano na rzucie kondygnacji „-1”? | 3 | 3 | 89334 |
| Count / Doors | Ile drzwi znajduje się w modelu „BIM-Speed Gdynia - semi-detached house Ruchu Oporu 18”? | 1 | 1 | 89322 |
| Count / Doors | Mitu ust on mudelis „Maleva tänav 18 korterelamu (Esplanades example model)“? | 6 | 6 | 86668 |
| Count / Doors | Qual è il numero di porte nel modello «BIM-Speed Frigento - Palazzo Testa Cipriano (baseline)»? | 1 | 1 | 88460 |
| Count / Doors | Wie viele Türen sind im Grundriss „Erdgeschoss“ dargestellt? | 17 | 15 | 87836 |
| Count / Doors | Wie viele Türen enthält das Modell „FZK-Haus (Simple Phantasy Building)“? | 7 | 7 | 87824 |
| Count / Doors | ¿Cuál es el número de puertas en el plano de la planta «P0»? | 10 | 5 | 88482 |
| Count / Doors | ¿Cuál es el número de puertas en el modelo «BIM-Speed Vitoria-Gasteiz - ALD26 (baseline, before renovation)»? | 2 | 2 | 88468 |
| Count / Light fixtures | Care este numărul de corpuri de iluminat din modelul „BIM-Speed Barlad apartment block (architecture + MEP)”? | 1 | 1 | 89304 |
| Count / Light fixtures | How many light fixtures are there in the model 'Duplex Apartment - MEP'? | 5 | 5 | 86374 |
| Count / Rooms and spaces | Hoeveel ruimtes staan er op de plattegrond van '00 Begane grond'? | 5 | 5 | 87708 |
| Count / Rooms and spaces | Hoeveel ruimtes bevat het model 'Gymzaal Hambakendreef, Amersfoort (example project location)'? | 2 | 2 | 87696 |
| Count / Rooms and spaces | How many rooms (spaces) are shown on the floor plan of 'Level 1'? | 52 | 43 | 86343 |
| Count / Rooms and spaces | How many rooms (spaces) are there in the model 'Duplex Apartment - architectural'? | 22 | 22 | 86337 |
| Count / Rooms and spaces | Hvor mange rum er vist på plantegningen for 'Kælder'? | 7 | 7 | 87314 |
| Count / Rooms and spaces | Hvor mange rum er der i modellen 'Molio Demo-hus'? | 1 | 1 | 87302 |
| Count / Rooms and spaces | Ile pomieszczeń pokazano na rzucie kondygnacji „-1”? | 2 | 2 | 89336 |
| Count / Rooms and spaces | Ile pomieszczeń znajduje się w modelu „BIM-Speed Gdynia - semi-detached house Ruchu Oporu 18”? | 1 | 1 | 89326 |
| Count / Rooms and spaces | Mitu ruumi on mudelis „Maleva tänav 18 korterelamu (Esplanades example model)“? | 6 | 6 | 86672 |
| Count / Rooms and spaces | Wie viele Räume sind im Grundriss „Erdgeschoss“ dargestellt? | 17 | 14 | 87840 |
| Count / Rooms and spaces | Wie viele Räume enthält das Modell „FZK-Haus (Simple Phantasy Building)“? | 7 | 7 | 87828 |
| Count / Rooms and spaces | ¿Cuál es el número de locales en el plano de la planta «P0»? | 12 | 6 | 88484 |
| Count / Rooms and spaces | ¿Cuál es el número de locales en el modelo «BIM-Speed Vitoria-Gasteiz - ALD26 (baseline, before renovation)»? | 2 | 2 | 88472 |
| Count / Sanitary fixtures (combined) | Hoeveel sanitaire toestellen bevat het model 'Gymzaal Hambakendreef, Amersfoort (example project location)'? | 1 | 1 | 87704 |
| Count / Sanitary fixtures (combined) | How many sanitary fixtures are there in the model 'Duplex Apartment - MEP'? | 8 | 8 | 86373 |
| Count / Sanitary fixtures (combined) | Wie viele Sanitärobjekte enthält das Modell „DigitalHub v2 - Fachmodell Sanitär“? | 3 | 3 | 88230 |
| Count / Stairs | Care este numărul de scări de pe planul nivelului „Ground Level”? | 4 | 4 | 89306 |
| Count / Stairs | Care este numărul de scări din modelul „BIM-Speed Barlad apartment block (architecture + MEP)”? | 1 | 1 | 89302 |
| Count / Stairs | How many stairs are shown on the floor plan of 'Level 1'? | 34 | 28 | 86344 |
| Count / Stairs | How many stairs are there in the model 'Duplex Apartment - architectural'? | 16 | 16 | 86340 |
| Count / Stairs | Hvor mange trapper er vist på plantegningen for '4. Sal'? | 2 | 2 | 87564 |
| Count / Stairs | Hvor mange trapper er der i modellen 'Molio Demo-hus'? | 1 | 1 | 87310 |
| Count / Stairs | Ile schodów pokazano na rzucie kondygnacji „-1”? | 1 | 1 | 89340 |
| Count / Stairs | Ile schodów znajduje się w modelu „BIM-Speed Gdynia - semi-detached house Ruchu Oporu 18”? | 1 | 1 | 89332 |
| Count / Stairs | Mitu treppi on mudelis „Maleva tänav 18 korterelamu (Esplanades example model)“? | 5 | 5 | 86680 |
| Count / Stairs | Wie viele Treppen sind im Grundriss „Erdgeschoss“ dargestellt? | 13 | 12 | 87844 |
| Count / Stairs | Wie viele Treppen enthält das Modell „FZK-Haus (Simple Phantasy Building)“? | 7 | 7 | 87834 |
| Count / Stairs | ¿Cuál es el número de escaleras en el plano de la planta «P1»? | 8 | 4 | 88498 |
| Count / Stairs | ¿Cuál es el número de escaleras en el modelo «BIM-Speed Vitoria-Gasteiz - ALD26 (baseline, before renovation)»? | 2 | 2 | 88480 |
| Count / Walls | Care este numărul de pereți din modelul „BIM-Speed Barlad apartment block (architecture + MEP)”? | 1 | 1 | 89296 |
| Count / Walls | Hoeveel wanden staan er op de plattegrond van '01 Eerste verdieping'? | 4 | 4 | 87810 |
| Count / Walls | Hoeveel wanden bevat het model 'Gymzaal Hambakendreef, Amersfoort (example project location)'? | 2 | 2 | 87698 |
| Count / Walls | How many walls are shown on the floor plan of '2.korrus'? | 31 | 30 | 86795 |
| Count / Walls | How many walls are there in the model 'Duplex Apartment - architectural'? | 20 | 20 | 86338 |
| Count / Walls | Hvor mange vægge er vist på plantegningen for 'Kælder'? | 8 | 8 | 87316 |
| Count / Walls | Hvor mange vægge er der i modellen 'Molio Demo-hus'? | 1 | 1 | 87304 |
| Count / Walls | Ile ścian pokazano na rzucie kondygnacji „-1”? | 3 | 3 | 89338 |
| Count / Walls | Ile ścian znajduje się w modelu „BIM-Speed Gdynia - semi-detached house Ruchu Oporu 18”? | 1 | 1 | 89328 |
| Count / Walls | Mitu seina on mudelis „Maleva tänav 18 korterelamu (Esplanades example model)“? | 4 | 4 | 86674 |
| Count / Walls | Qual è il numero di muri nella pianta del piano «0_Piano terra»? | 1 | 1 | 88466 |
| Count / Walls | Qual è il numero di muri nel modello «BIM-Speed Frigento - Palazzo Testa Cipriano (baseline)»? | 1 | 1 | 88464 |
| Count / Walls | Wie viele Wände sind im Grundriss „Erdgeschoss“ dargestellt? | 12 | 11 | 87842 |
| Count / Walls | Wie viele Wände enthält das Modell „FZK-Haus (Simple Phantasy Building)“? | 7 | 7 | 87830 |
| Count / Walls | ¿Cuál es el número de muros en el modelo «BIM-Speed Vitoria-Gasteiz - ALD26 (baseline, before renovation)»? | 2 | 2 | 88474 |
| Count / Windows | Care este numărul de ferestre din modelul „BIM-Speed Barlad apartment block (architecture + MEP)”? | 1 | 1 | 89294 |
| Count / Windows | Hoeveel ramen staan er op de plattegrond van 'Entrance'? | 3 | 3 | 88876 |
| Count / Windows | Hoeveel ramen bevat het model 'Gymzaal Hambakendreef, Amersfoort (example project location)'? | 2 | 2 | 87694 |
| Count / Windows | How many windows are shown on the floor plan of 'Level 1'? | 21 | 20 | 86342 |
| Count / Windows | How many windows are there in the model 'Duplex Apartment - architectural'? | 18 | 18 | 86336 |
| Count / Windows | Hvor mange vinduer er vist på plantegningen for '2. Sal'? | 4 | 4 | 87448 |
| Count / Windows | Hvor mange vinduer er der i modellen 'Molio Demo-hus'? | 1 | 1 | 87300 |
| Count / Windows | Ile okien pokazano na rzucie kondygnacji „1”? | 1 | 1 | 89378 |
| Count / Windows | Ile okien znajduje się w modelu „BIM-Speed Gdynia - semi-detached house Ruchu Oporu 18”? | 1 | 1 | 89324 |
| Count / Windows | Mitu akent on mudelis „Maleva tänav 18 korterelamu (Esplanades example model)“? | 1 | 1 | 86670 |
| Count / Windows | Qual è il numero di finestre nel modello «BIM-Speed Frigento - Palazzo Testa Cipriano (baseline)»? | 1 | 1 | 88462 |
| Count / Windows | Wie viele Fenster sind im Grundriss „Erdgeschoss“ dargestellt? | 10 | 9 | 87838 |
| Count / Windows | Wie viele Fenster enthält das Modell „FZK-Haus (Simple Phantasy Building)“? | 7 | 7 | 87826 |
| Count / Windows | ¿Cuál es el número de ventanas en el modelo «BIM-Speed Vitoria-Gasteiz - ALD26 (baseline, before renovation)»? | 2 | 2 | 88470 |
| Length / All walls on one level | Hvad er den samlede længde af alle vægge på 'Grundplan' i meter? | 7 | 7 | 87388 |
| Length / All walls on one level | Wat is de totale lengte van alle wanden op '00 Begane grond', in meter? | 6 | 6 | 87802 |
| Length / All walls on one level | What is the total length of all walls on 'Grundplan', in metres? | 32 | 30 | 87387 |
| Length / All walls on one level | Wie lang sind alle Wände im Geschoss „Erdgeschoss“ zusammen, in Metern? | 19 | 17 | 87848 |
| Volume / Net slab volume | Hvad er det samlede nettovolumen af alle dæk og plader på 'Kælder' i m³? | 8 | 8 | 87350 |
| Volume / Net slab volume | Wat is het totale netto volume van alle vloeren op '00 Begane grond', in m³? | 9 | 9 | 87808 |
| Volume / Net slab volume | What is the total net volume of all slabs on 'Kælder', in m³? | 36 | 33 | 87349 |
| Volume / Net slab volume | Wie groß ist das gesamte Netto-Volumen aller Decken und Bodenplatten im Geschoss „Erdgeschoss“ in m³? | 19 | 16 | 87854 |
| Volume / Net wall volume | Hvad er det samlede nettovolumen af alle vægge på 'Grundplan' i m³? | 7 | 7 | 87392 |
| Volume / Net wall volume | Wat is het totale netto volume van alle wanden op '00 Begane grond', in m³? | 6 | 6 | 87806 |
| Volume / Net wall volume | What is the total net volume of all walls on 'Grundplan', in m³? | 33 | 31 | 87391 |
| Volume / Net wall volume | Wie groß ist das gesamte Netto-Volumen aller Wände im Geschoss „Erdgeschoss“ in m³? | 20 | 18 | 87852 |

</details>

### IFC-Bench

<details>
<summary>820 rows in 701 exact texts or parameterized templates</summary>

| Family | Verbatim question or example | Rows | Distinct question texts | First JSONL line |
| --- | --- | --- | --- | --- |
| Area / Building footprint | What is the building's footprint area? | 4 | 1 | 85904 |
| Area / Duct cross-sections and distribution | What is the total cross-sectional area of ductwork in the building, including the average per duct, the count of ducts with area data, and a breakdown of the area by building level? | 1 | 1 | 85749 |
| Area / Exterior facade surface | What is the facade's total surface area? | 1 | 1 | 85674 |
| Area / Exterior facade surface | What is the total surface area of the facade? | 1 | 1 | 85547 |
| Area / Exterior facade surface | What is the total surface area of the façade? | 1 | 1 | 85782 |
| Area / Floor finishes, tiles or specialty flooring | How many square meters of flooring are required for each room? | 1 | 1 | 85785 |
| Area / Floor finishes, tiles or specialty flooring | What is the total amount of tiling needed to redo the flooring in all bathrooms, and what is the breakdown by bathroom? | 1 | 1 | 85800 |
| Area / Floor finishes, tiles or specialty flooring | What is the total area of tiles in all bathrooms of house A, and could you provide a breakdown by each bathroom? | 1 | 1 | 85796 |
| Area / Floor finishes, tiles or specialty flooring | What is the total square meters of specialty flooring needed for the Labs, and could you provide a breakdown by individual laboratory space? | 1 | 1 | 85625 |
| Area / Floor finishes, tiles or specialty flooring | What materials are used for floor finishes, and what is the total area covered by each material type? | 1 | 1 | 85880 |
| Area / Glazed windows | What is the estimated total area of glazed windows in the building? | 1 | 1 | 85758 |
| Area / Gross floor area, optionally by level | Could you provide the total gross floor area of the building, along with a breakdown of the approximate gross floor area for each storey? | 1 | 1 | 86218 |
| Area / Gross floor area, optionally by level | What is the GFA ? | 1 | 1 | 85642 |
| Area / Gross floor area, optionally by level | What is the building's total gross floor area, with breakdown by level? | 2 | 1 | 85664 |
| Area / Gross floor area, optionally by level | What is the building's total gross floor area? | 1 | 1 | 86145 |
| Area / Gross floor area, optionally by level | What is the gross floor area of each floor? | 2 | 1 | 85885 |
| Area / Gross floor area, optionally by level | What is the total gross area of each floor? | 1 | 1 | 85958 |
| Area / Gross floor area, optionally by level | What is the total gross floor area of the building? | 3 | 1 | 85520 |
| Area / Gross floor area, optionally by level | What is the total gross floor area of the dental clinic? | 1 | 1 | 85640 |
| Area / Interior wall painting | What is the total area of interior wall surfaces requiring painting? | 1 | 1 | 85788 |
| Area / Interior wall painting | What is the total interior wall surface area to be painted? | 1 | 1 | 85538 |
| Area / Net or usable floor area, optionally by level | What is the UFA ? | 1 | 1 | 85641 |
| Area / Net or usable floor area, optionally by level | What is the building's total net floor area, broken down by level? | 1 | 1 | 86044 |
| Area / Net or usable floor area, optionally by level | What is the building's total net usable floor area with the breakdown by level? | 1 | 1 | 85585 |
| Area / Net or usable floor area, optionally by level | What is the total net floor area of the building, broken down by level? | 2 | 1 | 85859 |
| Area / Net or usable floor area, optionally by level | What is the total net floor area of the building? | 1 | 1 | 86146 |
| Area / One room or space | What is the size of the tech office on the second floor? | 1 | 1 | 85635 |
| Area / Selected room or function totals | What is the estimated area of office space in the building in square meters? | 1 | 1 | 85629 |
| Area / Selected room or function totals | What is the total area of the sterilization rooms? | 1 | 1 | 85613 |
| Area / Selected room or function totals | What is the total estimated storage space available in the building, and can you provide a breakdown by storage type? | 1 | 1 | 85615 |
| Area / Town enclosed by inner wall | What is the total area of the town within the inner wall (Mauer-Innen)? | 1 | 1 | 85839 |
| Compliance / Internal-door accessibility requirements | Are all internal doors compliant with accessibility requirements? | 1 | 1 | 85756 |
| Compound / Door and window counts together | What is the total number of building openings, and how many are doors versus windows? | 1 | 1 | 85833 |
| Compound / Room counts and areas | How many Laundry/Utility Rooms are present in the building, and what is the area of each room? | 1 | 1 | 86008 |
| Compound / Room counts and areas | How many balconies are there on each floor? And what are their areas? | 1 | 1 | 86011 |
| Compound / Room counts and areas | How many individual office rooms are available on each floor, including their total areas? | 1 | 1 | 85964 |
| Compound / Room counts and areas | How many restrooms are there on each floor, along with their areas? | 1 | 1 | 85908 |
| Compound / Room counts and locations | How many meeting rooms are available, and where are they? | 1 | 1 | 85907 |
| Compound / Staircase counts and widths | What is the total number of staircases, and what is the width of each staircase? | 1 | 1 | 85878 |
| Compound / Wall counts and total length | What is the total length of exterior walls and how many exterior walls are there in the building? | 1 | 1 | 85903 |
| Connectivity / Plumbing network ports and integration | Could you provide a comprehensive analysis of the plumbing distribution network connectivity, including the connectivity rate and network integration metrics? | 1 | 1 | 86261 |
| Connectivity / Ventilation network ports and integration | Could you provide a comprehensive analysis of the ventilation distribution network connectivity, including total ports, connected ports, connectivity rate, and network integration metrics? | 1 | 1 | 86292 |
| Count / Apartments and residential units | How many residential units are in this building? | 1 | 1 | 85990 |
| Count / Bathrooms and washrooms | How many bathrooms are there in total, and how are they distributed across the floors? | 1 | 1 | 86010 |
| Count / Bathrooms and washrooms | how many bathroom are there ? | 1 | 1 | 85798 |
| Count / Bedrooms | How many bedrooms are there? | 1 | 1 | 85794 |
| Count / Buildings | How many buildings are modeled in this IFC file? | 1 | 1 | 85821 |
| Count / Buildings | How many residential buildings exist in the model? | 1 | 1 | 85827 |
| Count / Door hardware | How many doorknobs are there in this house? | 1 | 1 | 85799 |
| Count / Doors | How many doors are there in this building? | 1 | 1 | 85637 |
| Count / Doors | How many interior doors are there in this building? | 1 | 1 | 85787 |
| Count / Guest rooms by floor | What is the total number of guest rooms in the building, and how are they distributed by floor? | 1 | 1 | 85847 |
| Count / Light switches | How many light switches are there? | 1 | 1 | 85552 |
| Count / Radiators | How many radiator are there in room A202? | 1 | 1 | 85804 |
| Count / Roof vapor barriers | How many vapor barriers are in the roof construction? | 1 | 1 | 85775 |
| Count / Rooms and spaces | How many rooms are there in house A? | 1 | 1 | 85792 |
| Count / Rooms and spaces | How many rooms are there in the clinic ? | 1 | 1 | 85612 |
| Count / Rooms with outdoor access | How many rooms have access to outdoor space? | 1 | 1 | 85759 |
| Count / Separate toilet rooms | How many toilet rooms are there on the second floor? | 1 | 1 | 85630 |
| Count / Stair steps | How many steps does the stair in house A have? | 1 | 1 | 85795 |
| Count / Toilets (fixture-versus-room unspecified) | How many toilets are located on the ground floor? | 1 | 1 | 86049 |
| Count / Toilets (fixture-versus-room unspecified) | How many toilets are on the fifth floor? | 1 | 1 | 86155 |
| Count / Toilets (fixture-versus-room unspecified) | How many toilets are on the ground floor? | 1 | 1 | 86154 |
| Count / Toilets (fixture-versus-room unspecified) | How many toilets are there on the ground floor? | 1 | 1 | 86098 |
| Count / Toilets (fixture-versus-room unspecified) | How many toilets exist on the ground floor? | 1 | 1 | 85590 |
| Count / Wells and fountains | How many wells and fountains are in the town? | 1 | 1 | 85828 |
| Count / Windows | How many windows are there on the north facade? | 1 | 1 | 85754 |
| Count / Windows | how many windows are there in this building? | 1 | 1 | 85636 |
| Count / X-ray rooms | How many X-RAY rooms are there in total? | 1 | 1 | 85608 |
| Derived / Clinical-to-nonclinical space ratio | What is the ratio of clinical to non-clinical space? | 1 | 1 | 85616 |
| Derived / Door cost by type or total | What is the total cost of doors used in this building and the breakdown by door type? | 1 | 1 | 85525 |
| Derived / Load-bearing wall volume proportion | What is the percentage of wall volume that is load-bearing, including the volume breakdown? | 1 | 1 | 85527 |
| Derived / Net-to-gross floor area ratio | What is the ratio of UFA to GFA? | 1 | 1 | 85643 |
| Derived / Net-to-gross floor area ratio | What is the ratio of net to gross floor area? | 1 | 1 | 86147 |
| Derived / Space use by function, areas or percentages | How is the building's space allocated by function, with areas and percentages for each? | 1 | 1 | 86054 |
| Derived / Space use by function, areas or percentages | How is the building's space allocated by function, with areas and percentages? | 1 | 1 | 86160 |
| Derived / Space use by function, areas or percentages | How is the building's space utilized by function, with area distribution? | 1 | 1 | 85682 |
| Derived / Space use by function, areas or percentages | What is the building's space utilization by function, with areas and percentages? | 1 | 1 | 86104 |
| Derived / Structural embodied carbon | What is the estimated embodied carbon of the structural elements, including a detailed breakdown by material type, the methodology and assumptions used in the calculation? | 1 | 1 | 85789 |
| Derived / Window total cost | What is the total cost of windows used in this building? | 1 | 1 | 85526 |
| Inventory / Air terminals | How many air terminals serve each building storey? | 1 | 1 | 85750 |
| Inventory / Air terminals | What air terminal types are used in this building with their respective counts, and how are they distributed by building level? | 1 | 1 | 85742 |
| Inventory / Air terminals | What different types of air terminals are used in this building, with quantity distribution? | 1 | 1 | 86278 |
| Inventory / Apartments by level and elevation | What is the distribution of residential units by building level, including elevation information? | 1 | 1 | 86180 |
| Inventory / Beam types and quantities or properties | What beam types are used in this building, and what are their quantities? | 1 | 1 | 85870 |
| Inventory / Beam types and quantities or properties | What beam types are used in this building, including their quantities? | 1 | 1 | 86227 |
| Inventory / Beam types and quantities or properties | What beam types are used in this building, with their quantities and percentages? | 1 | 1 | 86108 |
| Inventory / Beam types and quantities or properties | What beam types are used in this building, with their quantities? | 1 | 1 | 86269 |
| Inventory / Beam types and quantities or properties | Which beam types are present in the building, with quantities? | 1 | 1 | 85686 |
| Inventory / Beam types and quantities or properties | Which beam types are used in the structure, with their quantities and properties? | 1 | 1 | 86058 |
| Inventory / Beam types and quantities or properties | Which beams are used in the building? | 1 | 1 | 85598 |
| Inventory / Beam types and quantities or properties | Which types of beams are used in the building, with their quantities? | 1 | 1 | 86164 |
| Inventory / Beam types and quantities or properties | Which types of beams are used, and how many of each? | 1 | 1 | 86324 |
| Inventory / Boilers, specifications and locations | Could you provide a detailed list of all boilers in the building, including their specifications and exact locations? | 1 | 1 | 85805 |
| Inventory / Cable routing and cable trays | Could you provide a detailed breakdown of the cable routing systems used in this building, including the quantities of each component type and their materials? | 1 | 1 | 86233 |
| Inventory / Cable routing and cable trays | What cable tray systems are used, including their quantities? | 1 | 1 | 86241 |
| Inventory / Coils | What are the types of coils used in this building, their respective counts, and how are they distributed by building level? | 1 | 1 | 85745 |
| Inventory / Coils | What types of coils are integrated in the building systems, with unit counts? | 1 | 1 | 86285 |
| Inventory / Column types, dimensions and quantities | Could you provide a breakdown of all steel column types in the structural model, including their dimensions? | 1 | 1 | 85645 |
| Inventory / Column types, dimensions and quantities | Could you provide a breakdown of each column type, including the number of elements and their respective dimensions? | 1 | 1 | 86110 |
| Inventory / Column types, dimensions and quantities | What are the different column types present in this building, including their quantities and specifications? | 1 | 1 | 85914 |
| Inventory / Column types, dimensions and quantities | What are the different types of columns in this building and how many of each type are present? | 1 | 1 | 86018 |
| Inventory / Column types, dimensions and quantities | What are the dimensions of the columns, with distribution by size? | 1 | 1 | 85695 |
| Inventory / Column types, dimensions and quantities | What column types are used in this building, including their quantities? | 1 | 1 | 86263 |
| Inventory / Column types, dimensions and quantities | What column types are used in this building, with their quantities and percentages? | 1 | 1 | 86109 |
| Inventory / Column types, dimensions and quantities | What column types are used in this building, with their quantities? | 1 | 1 | 85871 |
| Inventory / Column types, dimensions and quantities | Which column types are present here and how many of each? | 1 | 1 | 85599 |
| Inventory / Column types, dimensions and quantities | Which column types are present in the building, including their quantities? | 1 | 1 | 86165 |
| Inventory / Column types, dimensions and quantities | Which column types are present in the building? | 1 | 1 | 86059 |
| Inventory / Column types, dimensions and quantities | Which column types are present in this building, and how many of each type are there? | 1 | 1 | 85946 |
| Inventory / Column types, dimensions and quantities | Which column types are present in this building, including their dimensions and quantities? | 1 | 1 | 85982 |
| Inventory / Column types, dimensions and quantities | Which columns are used in the building, showing distribution by type? | 1 | 1 | 85687 |
| Inventory / Column types, dimensions and quantities | Which types of columns are present in this building, with their quantities? | 1 | 1 | 86325 |
| Inventory / Controllers | What types of controllers are installed in the building, along with their occurrence frequency and quantities? | 1 | 1 | 86277 |
| Inventory / Cooling systems and quantities | What cooling systems are installed, and how many of each type? | 1 | 1 | 86275 |
| Inventory / Cooling systems and quantities | What cooling systems are installed? | 2 | 1 | 85876 |
| Inventory / Cooling systems and quantities | Which cooling systems are installed? | 2 | 1 | 86065 |
| Inventory / Coverings and finishes | Could you provide a comprehensive breakdown of all coverings used in the building, including total count, categorization by function and name with quantities, and separate lists for wall and ceiling finishes? | 1 | 1 | 86220 |
| Inventory / Coverings and finishes | What coverings are used in the building? | 2 | 1 | 85860 |
| Inventory / Coverings and finishes | Which coverings are applied in the building? | 1 | 1 | 86149 |
| Inventory / Coverings and finishes | Which coverings are applied inside the building? | 1 | 1 | 86045 |
| Inventory / Coverings and finishes | Which coverings are applied throughout the building, with element counts? | 1 | 1 | 85679 |
| Inventory / Coverings and finishes | Which coverings are applied throughout the building? | 1 | 1 | 85586 |
| Inventory / Curtain-wall types and quantities | What curtain wall types are present in this building, including their quantities, and distribution by floor? | 1 | 1 | 85852 |
| Inventory / Curtain-wall types and quantities | What types of curtain walls are installed in the building, and how many of each type are there? | 1 | 1 | 85905 |
| Inventory / Curtain-wall types and quantities | What types of curtain walls are installed in the building, and how many of each type? | 1 | 1 | 86004 |
| Inventory / Curtain-wall types and quantities | Which types of curtain walls are installed, specifying their quantities? | 1 | 1 | 85975 |
| Inventory / Curtain-wall types and quantities | Which types of curtain walls are installed? | 1 | 1 | 85939 |
| Inventory / Dampers | What damper types are used in this building, their respective counts, and how are they distributed across building levels? | 1 | 1 | 85743 |
| Inventory / Dampers | What different types of dampers are used in this building, with distribution by application? | 1 | 1 | 86286 |
| Inventory / Data and communication devices | Could you provide a breakdown of all data and communication devices installed in the building, including quantities by category and a detailed breakdown of data device types? | 1 | 1 | 86240 |
| Inventory / Door types with quantities, optionally dimensions or percentages | What door types are present in the building, how many of each type, and what are their dimensions? | 1 | 1 | 86028 |
| Inventory / Door types with quantities, optionally dimensions or percentages | What door types are present in this building, with their quantities and percentages? | 1 | 1 | 86079 |
| Inventory / Door types with quantities, optionally dimensions or percentages | What door types are present in this building, with their quantities? | 1 | 1 | 85850 |
| Inventory / Door types with quantities, optionally dimensions or percentages | What door types are used in this building and their counts? | 1 | 1 | 85522 |
| Inventory / Door types with quantities, optionally dimensions or percentages | What door types are used in this building, including their quantities? | 1 | 1 | 86203 |
| Inventory / Door types with quantities, optionally dimensions or percentages | Which door types are installed in the building, along with their quantities? | 1 | 1 | 86132 |
| Inventory / Door types with quantities, optionally dimensions or percentages | Which door types are installed in the building, with their quantities? | 4 | 1 | 85895 |
| Inventory / Door types with quantities, optionally dimensions or percentages | Which door types are installed in this building with quantities? | 1 | 1 | 85569 |
| Inventory / Door types with quantities, optionally dimensions or percentages | Which doors are installed in this building, showing distribution by type? | 1 | 1 | 85659 |
| Inventory / Door types with quantities, optionally dimensions or percentages | Which doors are installed in this building, with quantities by type? | 1 | 1 | 86302 |
| Inventory / Duct fittings and accessories | What are the duct fitting types and their respective quantities? | 1 | 1 | 86282 |
| Inventory / Duct fittings and accessories | What are the specific types of duct accessories used in this building, including their quantities and percentages, and what are the general functional categories of these accessories? | 1 | 1 | 86291 |
| Inventory / Duct fittings and accessories | What duct fitting types are used in this building with their respective counts, and how are these fittings distributed across each building level? | 1 | 1 | 85741 |
| Inventory / Duct types and specifications | What are the different duct types used in this building, broken down by specifications? | 1 | 1 | 86281 |
| Inventory / Duct types and specifications | What different types of ducts are used in this building, showing counts by shape and material? | 1 | 1 | 86280 |
| Inventory / Duct types and specifications | What duct types are used in this building and their respective counts? | 1 | 1 | 85740 |
| Inventory / Electrical receptacles and switches by type | What electrical receptacles are installed, with their quantities? | 1 | 1 | 86230 |
| Inventory / Electrical receptacles and switches by type | What electrical switches are installed, along with their counts? | 1 | 1 | 86231 |
| Inventory / Electrical systems and components | What electrical components are in this building and their counts? | 1 | 1 | 85551 |
| Inventory / Electrical systems and components | What electrical components are present in the building? | 1 | 1 | 86066 |
| Inventory / Electrical systems and components | What electrical components are present in this building, grouped by type with their counts? | 1 | 1 | 86228 |
| Inventory / Electrical systems and components | What electrical components are present in this building? | 2 | 1 | 86119 |
| Inventory / Electrical systems and components | What electrical distribution equipment is installed, including quantities? | 1 | 1 | 86232 |
| Inventory / Electrical systems and components | What is the distribution of electrical system components by building level? | 1 | 1 | 86242 |
| Inventory / Electrical systems and components | What is the electrical equipment distribution in level 1? | 1 | 1 | 86243 |
| Inventory / Electrical systems and components | Which electrical systems are installed? | 1 | 1 | 86330 |
| Inventory / Fans | What different types of fans are used in this building, including how many of each? | 1 | 1 | 86284 |
| Inventory / Fans | What fan types are used in this building, their respective counts, and how are they distributed by building level? | 1 | 1 | 85744 |
| Inventory / Filters | What filter types are used in this building, their respective counts, and how are they distributed by building level? | 2 | 1 | 85733 |
| Inventory / Foundation types and quantities | How many piles are used in this building, and could you provide a breakdown by pile type including quantities and percentages? | 1 | 1 | 86266 |
| Inventory / Foundation types and quantities | What footing types are used in this building, along with their quantities? | 1 | 1 | 86265 |
| Inventory / Foundation types and quantities | What foundation system is used in this building, and what are the quantities of its components? | 1 | 1 | 86272 |
| Inventory / Foundation types and quantities | Which foundation system is used? | 1 | 1 | 85690 |
| Inventory / Furniture by type, room or level | Could you provide a breakdown of all furniture types in this building with the quantity of each type? | 1 | 1 | 85548 |
| Inventory / Furniture by type, room or level | Could you provide a breakdown of the furniture inventory in the building, showing the quantities of each furniture type? | 1 | 1 | 85927 |
| Inventory / Furniture by type, room or level | Could you provide a complete furniture inventory for the building, including the total count and a breakdown of quantities by furniture type? | 1 | 1 | 85893 |
| Inventory / Furniture by type, room or level | Could you provide a detailed breakdown of all furniture elements in this building, including quantities for each furniture type and their categorization by room type? | 1 | 1 | 86222 |
| Inventory / Furniture by type, room or level | Could you provide a detailed inventory of all furniture in the building, including quantities and dimensions for each type? | 1 | 1 | 85862 |
| Inventory / Furniture by type, room or level | Could you provide a detailed inventory of all furniture items in the building, including quantities for each type? | 1 | 1 | 86006 |
| Inventory / Furniture by type, room or level | What furniture can be found in room 112? | 1 | 1 | 85863 |
| Inventory / Furniture by type, room or level | What furniture can be found in the staff room on the third floor? | 1 | 1 | 86096 |
| Inventory / Furniture by type, room or level | What furniture is available in Open-plan office on the ground floor? | 1 | 1 | 85962 |
| Inventory / Furniture by type, room or level | What furniture is available in office 13? | 1 | 1 | 85928 |
| Inventory / Furniture by type, room or level | What furniture is in this building? | 1 | 1 | 86095 |
| Inventory / Furniture by type, room or level | What furniture is present in the building? | 1 | 1 | 86312 |
| Inventory / Furniture by type, room or level | What furniture is present in this building? | 1 | 1 | 86151 |
| Inventory / Furniture by type, room or level | What furniture items are available in working space 28, and how many of each type are there? | 1 | 1 | 85894 |
| Inventory / Furniture by type, room or level | What furniture items are in space 5 (kitchen) on the ground floor, and what is the basic information about this space? | 1 | 1 | 86007 |
| Inventory / Furniture by type, room or level | What furniture items are present in the building? | 1 | 1 | 86047 |
| Inventory / Furniture by type, room or level | What furniture items are present inside the building including quantities for each type? | 1 | 1 | 85588 |
| Inventory / Furniture by type, room or level | What furniture types are present in the building, specifying quantities and distribution by floor? | 1 | 1 | 85961 |
| Inventory / Furniture by type, room or level | Which furniture items are in the kitchen on the ground floor? | 1 | 1 | 86152 |
| Inventory / Furniture by type, room or level | Which furniture items are located in the building? | 1 | 1 | 85673 |
| Inventory / Heat recovery units | What heat recovery unit types are used in this building, their respective counts, and how are they distributed by building level? | 1 | 1 | 85747 |
| Inventory / Heat recovery units | What types of heat recovery units are used in this building, and how many? | 1 | 1 | 86287 |
| Inventory / Heating sensors | Which heating sensor types are used in this building with their quantities, and how are they distributed by building level? | 1 | 1 | 85718 |
| Inventory / Heating systems and component categories | What components make up the heating system? | 1 | 1 | 86329 |
| Inventory / Heating systems and component categories | What heating systems are installed? | 2 | 1 | 85875 |
| Inventory / Heating systems and component categories | What heating systems are present in this building, and what is the count of systems by category? | 1 | 1 | 85724 |
| Inventory / Heating systems and component categories | What is the complete overview of the heating systems installation, including system types, total component counts, and distribution network details? | 1 | 1 | 86276 |
| Inventory / Heating systems and component categories | What type of heating system is used in the bathrooms? | 1 | 1 | 85808 |
| Inventory / Heating systems and component categories | Which component types comprise the heating system and how many of each? | 1 | 1 | 85713 |
| Inventory / Heating systems and component categories | Which heating systems are included in this building? | 1 | 1 | 85605 |
| Inventory / Heating systems and component categories | Which heating systems are installed? | 2 | 1 | 86064 |
| Inventory / Junction components and junction boxes | Could you provide a comprehensive breakdown of all junction components used in the project, including counts by type and density analysis? | 1 | 1 | 86237 |
| Inventory / Junction components and junction boxes | Could you provide a comprehensive breakdown of junction box types used in this building, including quantities of each type and an overview of the junction system? | 1 | 1 | 86236 |
| Inventory / Lighting systems, fixtures and devices | Could you provide a comprehensive breakdown of all lighting components installed in the building, including both lighting fixtures and lighting devices with their quantities and distribution by type? | 1 | 1 | 86229 |
| Inventory / Lighting systems, fixtures and devices | How many light fixtures are specified in the model, and what is the breakdown by type? | 1 | 1 | 85815 |
| Inventory / Lighting systems, fixtures and devices | List all lighting fixture types and their respective quantities on the ground floor. | 1 | 1 | 85879 |
| Inventory / Lighting systems, fixtures and devices | What lighting fixtures are present in this building, and how many of each type are installed? | 1 | 1 | 85877 |
| Inventory / Lighting systems, fixtures and devices | What lighting systems are installed? | 1 | 1 | 85709 |
| Inventory / Lighting systems, fixtures and devices | Which lighting systems are implemented? | 1 | 1 | 86327 |
| Inventory / MEP systems and components by category, space or level | Could you provide a breakdown of the MEP systems serving Level B01_OKRD, including the number of major components for each system type, along with the primary functions of this level? | 1 | 1 | 85702 |
| Inventory / MEP systems and components by category, space or level | Could you provide a breakdown of the MEP systems serving Level E00_OKRD, including component counts for each system type, along with the primary functions of this level? | 1 | 1 | 85703 |
| Inventory / MEP systems and components by category, space or level | Could you provide a detailed breakdown of all MEP systems present in this building, including their components and a quantitative summary of systems by category? | 1 | 1 | 85699 |
| Inventory / MEP systems and components by category, space or level | How many MEP components are there by system type? | 3 | 1 | 85700 |
| Inventory / MEP systems and components by category, space or level | How many MEP components exist by system type? | 1 | 1 | 86173 |
| Inventory / MEP systems and components by category, space or level | How many MEP terminals serve each space? | 1 | 1 | 86174 |
| Inventory / MEP systems and components by category, space or level | What MEP components are used in this model, grouped by the MEP system they belong to, and how are these components distributed across the floors? | 1 | 1 | 85977 |
| Inventory / MEP systems and components by category, space or level | What MEP components are used in this model, grouped by the MEP system they belong to? | 1 | 1 | 85941 |
| Inventory / MEP systems and components by category, space or level | What MEP systems are present in this building? | 1 | 1 | 86112 |
| Inventory / MEP systems and components by category, space or level | What MEP systems serve Level E01_OKRD, and what are their primary functions? | 1 | 1 | 85704 |
| Inventory / MEP systems and components by category, space or level | What are the specific MEP system names and their corresponding types present in the building? | 1 | 1 | 85553 |
| Inventory / MEP systems and components by category, space or level | What is the overall distribution of MEP terminals in the building, including total counts, average per space, and breakdown by type? | 1 | 1 | 85701 |
| Inventory / MEP systems and components by category, space or level | Which HVAC systems serve the building? | 1 | 1 | 86328 |
| Inventory / MEP systems and components by category, space or level | Which MEP systems are installed in the building? | 1 | 1 | 86326 |
| Inventory / MEP systems and components by category, space or level | Which MEP systems are installed in this building? | 3 | 1 | 85603 |
| Inventory / Measuring equipment | What measuring equipment is present in the ventilation system, with quantities by type? | 1 | 1 | 86288 |
| Inventory / Measuring equipment | What measuring equipment is used in the plumbing system, with their quantities? | 1 | 1 | 86258 |
| Inventory / Mechanical and unitary equipment | What types of mechanical equipment are used in this building, along with unit counts? | 1 | 1 | 86290 |
| Inventory / Mechanical and unitary equipment | Which unitary equipment types are used in this building, including the number of each type and their distribution by building level? | 1 | 1 | 85722 |
| Inventory / Parking equipment and areas | What parking-related elements or areas are defined in the model? | 1 | 1 | 85881 |
| Inventory / Parking equipment and areas | Which installations or equipment are found in the parking lot, with their quantities? | 1 | 1 | 85658 |
| Inventory / Pipe fittings and accessories | What different types of pipe fittings are used in this building, with their quantities? | 1 | 1 | 86251 |
| Inventory / Pipe fittings and accessories | What pipe fitting types and quantities are installed? | 1 | 1 | 86252 |
| Inventory / Pipe fittings and accessories | What pipe fitting types are used in this building, their respective counts, and how are they distributed across each building level? | 1 | 1 | 85728 |
| Inventory / Pipe fittings and accessories | What types of pipe accessories are used in this building, including their quantities? | 1 | 1 | 86259 |
| Inventory / Pipe fittings and accessories | Which pipe fitting types are used in this building including the number of each, and how are they distributed across the different building levels? | 1 | 1 | 85716 |
| Inventory / Pipes by type, application, material or floor | Could you provide a comprehensive breakdown of the pipes used in this building, including the total count, specific pipe types with quantities, material types with quantities, and applications with quantities? | 1 | 1 | 86246 |
| Inventory / Pipes by type, application, material or floor | What different types of pipes are used in this building, including their quantities? | 1 | 1 | 86250 |
| Inventory / Pipes by type, application, material or floor | What is the distribution of flexible pipes by building level, including the quantity found at each level? | 1 | 1 | 86239 |
| Inventory / Pipes by type, application, material or floor | What kind of pipes are used in this building? | 1 | 1 | 86113 |
| Inventory / Pipes by type, application, material or floor | What pipe types are used in this building and their respective counts? | 1 | 1 | 85727 |
| Inventory / Pipes by type, application, material or floor | What types of pipes are used in the building? | 1 | 1 | 85604 |
| Inventory / Pipes by type, application, material or floor | What types of pipes are used throughout the building? | 1 | 1 | 86170 |
| Inventory / Pipes by type, application, material or floor | What types of piping are used throughout the building? | 1 | 1 | 86063 |
| Inventory / Pipes by type, application, material or floor | Which pipe types are used in this building with quantities? | 1 | 1 | 85715 |
| Inventory / Plumbing systems and component categories | Could you provide a breakdown of the plumbing system components by category, including the quantities and percentage distribution of each type? | 1 | 1 | 86245 |
| Inventory / Plumbing systems and component categories | What component types comprise the plumbing system and their respective counts? | 1 | 1 | 85725 |
| Inventory / Plumbing systems and component categories | What plumbing systems are present in this building, including their counts by system type and system category? | 1 | 1 | 85734 |
| Inventory / Plumbing systems and component categories | What types of plumbing sub-systems are defined, and how many instances of each type exist? | 1 | 1 | 86244 |
| Inventory / Plumbing systems and component categories | Which plumbing systems are installed? | 1 | 1 | 86331 |
| Inventory / Pumps | What are the different types of pumps used in this building, their quantities and percentages, and how are they distributed by building level? | 1 | 1 | 85720 |
| Inventory / Pumps | What is the total count of plumbing pumps installed, and what are the details of each pump type? | 1 | 1 | 86247 |
| Inventory / Pumps | What pumps are used in the system, including their quantities? | 1 | 1 | 86257 |
| Inventory / Radiator types and quantities | What are the radiator types used in this building with their counts, and how are they distributed by building level? | 1 | 1 | 85719 |
| Inventory / Railings, types, quantities or materials | Could you provide a breakdown of all railing types used in the building, including the quantities of each type? | 1 | 1 | 86012 |
| Inventory / Railings, types, quantities or materials | Could you provide a complete breakdown of all railings installed in the building, including the total count, quantities of each railing type with their percentages, and the materials used? | 1 | 1 | 86224 |
| Inventory / Railings, types, quantities or materials | What railings are installed? | 1 | 1 | 86101 |
| Inventory / Railings, types, quantities or materials | What types of railings are used in the building, and how many of each type are there? | 1 | 1 | 85925 |
| Inventory / Railings, types, quantities or materials | Which railing types are installed in the building? | 1 | 1 | 85593 |
| Inventory / Railings, types, quantities or materials | Which railings are installed in the building? | 1 | 1 | 86158 |
| Inventory / Railings, types, quantities or materials | Which types of railings are installed, including element counts? | 1 | 1 | 85680 |
| Inventory / Railings, types, quantities or materials | Which types of railings are installed? | 1 | 1 | 86052 |
| Inventory / Roof types, components, materials or areas | Could you provide a breakdown of roof materials by type, including the quantities for each material? | 1 | 1 | 86320 |
| Inventory / Roof types, components, materials or areas | Identify all roof types in the building and specify the construction material layers and area information for each roof type. | 1 | 1 | 85947 |
| Inventory / Roof types, components, materials or areas | What type of roof is used in this building, what materials is it made of, and what is the breakdown of roof slabs? | 1 | 1 | 86019 |
| Inventory / Roof types, components, materials or areas | What type of roof structure is used? | 2 | 1 | 85549 |
| Inventory / Roof types, components, materials or areas | Which roof structural components are employed, including slabs, members, and beams? | 1 | 1 | 86061 |
| Inventory / Roof types, components, materials or areas | Which roof structural components are employed? | 1 | 1 | 86168 |
| Inventory / Roof types, components, materials or areas | Which roof structural components are used, with type distribution? | 1 | 1 | 85697 |
| Inventory / Roof types, components, materials or areas | Which roof structure elements are used? | 1 | 1 | 85602 |
| Inventory / Roof types, components, materials or areas | Which roof types are used in this building, including element count? | 1 | 1 | 86319 |
| Inventory / Rooms and spaces by name or function | Can you give me the list of all room types? | 1 | 1 | 85610 |
| Inventory / Rooms and spaces by name or function | Can you give me the list of each room available in house A? | 1 | 1 | 85791 |
| Inventory / Rooms and spaces by name or function | Could you provide a breakdown of working spaces by floor, including the count and details of each space? | 1 | 1 | 85892 |
| Inventory / Rooms and spaces by name or function | Give me the names of all the rooms in the building. | 1 | 1 | 85753 |
| Inventory / Rooms and spaces by name or function | What are all the spaces on level 1, grouped by function? | 1 | 1 | 85846 |
| Inventory / Rooms and spaces by name or function | What are all the spaces on the ground level, grouped by function? | 1 | 1 | 85845 |
| Inventory / Rooms and spaces by name or function | What are the bathroom spaces on each floor? | 1 | 1 | 85865 |
| Inventory / Rooms and spaces by name or function | What is the space breakdown by level, grouped by space function? | 1 | 1 | 85843 |
| Inventory / Rooms and spaces by name or function | What types of office spaces are available in this building, and could you provide a breakdown of their quantities? | 1 | 1 | 85960 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | Does this building have an underground level? If so, what are all the spaces in the underground level with their areas? | 1 | 1 | 85844 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the residential units on level 11, with their approximate gross areas? | 1 | 1 | 86192 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the residential units on level 12, with their approximate gross areas? | 1 | 1 | 86193 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the residential units on level 13, with their approximate gross areas? | 1 | 1 | 86194 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the residential units on level 14, with their approximate gross areas? | 1 | 1 | 86195 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the residential units on level 3, with their approximate gross areas? | 1 | 1 | 86184 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the residential units on level 5, with their approximate gross areas? | 1 | 1 | 86186 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the residential units on level 7, with their approximate gross areas? | 1 | 1 | 86188 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the residential units on level 8, with their approximate gross areas? | 1 | 1 | 86189 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the residential units on the first floor, with their approximate gross areas? | 1 | 1 | 86182 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the residential units on the ground level, with their approximate gross areas? | 1 | 1 | 86181 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the residential units on the second floor, with their approximate gross areas? | 1 | 1 | 86183 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the residential units on the sixth floor, with their approximate gross areas? | 1 | 1 | 86187 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the rooms in the attic level, including their areas and ceiling heights? | 1 | 1 | 86025 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the rooms on the ground level, including their areas and ceiling heights? | 1 | 1 | 86024 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the spaces in the underground level, with their areas? | 1 | 1 | 86072 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the spaces on ground floor, with their areas? | 4 | 1 | 85886 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the spaces on level 1, grouped by function with their areas? | 1 | 1 | 86074 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the spaces on level 1, with their areas? | 4 | 1 | 85887 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the spaces on level 17, with their areas? | 1 | 1 | 86198 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the spaces on level 2, grouped by function with their areas? | 1 | 1 | 86075 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the spaces on level 2, with their areas? | 4 | 1 | 85888 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the spaces on level 3, grouped by function with their areas? | 1 | 1 | 86076 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the spaces on level 3, with their areas? | 3 | 1 | 85889 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the spaces on level 4, with their areas? | 4 | 1 | 85890 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the spaces on level 5, with their areas? | 1 | 1 | 86129 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the spaces on level 6, with their areas? | 1 | 1 | 86130 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the spaces on the ground level, grouped by function with their areas? | 1 | 1 | 86073 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are all the spaces on the ground level, with their areas? | 1 | 1 | 86124 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are the residential units on level 10, with their approximate gross areas? | 1 | 1 | 86191 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are the residential units on level 15, with their approximate gross areas? | 1 | 1 | 86196 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are the residential units on level 4, with their approximate gross areas? | 1 | 1 | 86185 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are the residential units on the ninth floor, with their approximate gross areas? | 1 | 1 | 86190 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What are the residential units on the sixteenth floor, with their approximate gross areas? | 1 | 1 | 86197 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What is the complete space breakdown for all building levels, listing room names and areas? | 1 | 1 | 85652 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What is the complete space breakdown for all floors, including room names, functions, and areas? | 1 | 1 | 86296 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What is the distribution of offices by floor, including their individual areas? | 1 | 1 | 85926 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What is the space breakdown by level and function, including areas? | 1 | 1 | 86023 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What is the space breakdown by level, including total spaces and floor areas? | 1 | 1 | 86071 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What is the space breakdown by level, with individual room areas? | 5 | 1 | 85884 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What is the space breakdown of the attic floor with areas? | 1 | 1 | 85566 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What is the space breakdown of the basement floor grouped by function with areas? | 1 | 1 | 85562 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What is the space breakdown of the building grouped by floor with their respective areas and totals? | 1 | 1 | 85516 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What is the space breakdown of the first floor grouped by function with areas? | 1 | 1 | 85564 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What is the space breakdown of the first floor with respective areas and total? | 1 | 1 | 85517 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What is the space breakdown of the ground level grouped by function with areas? | 1 | 1 | 85563 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What is the space breakdown of the second floor with respective areas and total? | 1 | 1 | 85518 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What is the space breakdown of the second level grouped by function with areas? | 1 | 1 | 85565 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What is the space breakdown of the third floor with respective areas and total? | 1 | 1 | 85519 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What is the space distribution by level with areas and primary space functions with percentages? | 1 | 1 | 85561 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What restroom spaces are on the second floor, along with their areas? | 1 | 1 | 85963 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What spaces are on Level B01_OKRD, with their room names and areas? | 1 | 1 | 85653 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What spaces are on Level E00_OKRD, with their room names and areas? | 1 | 1 | 85654 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What spaces are on Level E01_OKRD, with their room names and areas? | 1 | 1 | 85655 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What spaces are on the 1.OG floor, with their functions and areas? | 1 | 1 | 86297 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What spaces are on the 2.OG floor, with their functions and areas? | 1 | 1 | 86298 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What spaces are on the EG floor, with their functions and areas? | 1 | 1 | 86299 |
| Inventory / Rooms and spaces with areas, optionally heights or functional groups | What spaces are on the KG floor, with their functions and areas? | 1 | 1 | 86300 |
| Inventory / Sanitary fixtures and equipment by type or location | Could you provide a breakdown of the sanitary equipment in this building by type, along with a detailed list of all fixtures? | 1 | 1 | 85864 |
| Inventory / Sanitary fixtures and equipment by type or location | Could you provide a complete inventory of sanitary equipment in the building, including the total count and a breakdown by equipment type with quantities? | 1 | 1 | 86009 |
| Inventory / Sanitary fixtures and equipment by type or location | How many plumbing fixtures serve each building storey? | 1 | 1 | 85737 |
| Inventory / Sanitary fixtures and equipment by type or location | What different types of sanitary terminals are used in this building, with their counts? | 1 | 1 | 86253 |
| Inventory / Sanitary fixtures and equipment by type or location | What plumbing fixture data is available for the building, organized by storey level? | 1 | 1 | 85736 |
| Inventory / Sanitary fixtures and equipment by type or location | What plumbing fixtures are in this building and their respective counts? | 1 | 1 | 85556 |
| Inventory / Sanitary fixtures and equipment by type or location | What sanitary equipment can be found in this building? | 1 | 1 | 86097 |
| Inventory / Sanitary fixtures and equipment by type or location | What sanitary furniture are in room 01.014? | 1 | 1 | 86115 |
| Inventory / Sanitary fixtures and equipment by type or location | What sanitary terminal types are used in this building with their respective counts and percentages, and how are they distributed across each building level? | 1 | 1 | 85730 |
| Inventory / Sanitary fixtures and equipment by type or location | Which sanitary fixtures and equipment are present in the building? | 1 | 1 | 86048 |
| Inventory / Sanitary fixtures and equipment by type or location | Which sanitary fixtures are available in the building? | 1 | 1 | 86153 |
| Inventory / Sanitary fixtures and equipment by type or location | Which sanitary fixtures are available in this building? | 1 | 1 | 85589 |
| Inventory / Sanitary fixtures and equipment by type or location | Which sanitary furniture is present in room 110? | 1 | 1 | 86172 |
| Inventory / Slab types, quantities and thicknesses | Could you provide a breakdown of all slab types in the building with their quantities and percentages, and include any available thickness information? | 1 | 1 | 85691 |
| Inventory / Slab types, quantities and thicknesses | Could you provide a breakdown of all slab types in the project, including their quantities and thicknesses? | 1 | 1 | 85873 |
| Inventory / Slab types, quantities and thicknesses | What are the slab types and their thicknesses? | 2 | 1 | 85910 |
| Inventory / Slab types, quantities and thicknesses | What are the slab types and thicknesses? | 1 | 1 | 86111 |
| Inventory / Slab types, quantities and thicknesses | What are the slab types in the building, their quantities, and available thickness information? | 1 | 1 | 86014 |
| Inventory / Slab types, quantities and thicknesses | What are the slab types, their thicknesses, and quantities, grouped by category? | 1 | 1 | 85978 |
| Inventory / Slab types, quantities and thicknesses | What information is available about the ground floor slab, including its dimensions and concrete specification? | 1 | 1 | 85762 |
| Inventory / Slab types, quantities and thicknesses | What slab types are used in this building, with their quantities? | 1 | 1 | 86264 |
| Inventory / Slab types, quantities and thicknesses | What slab types are used, how many of each, and what are their thicknesses? | 1 | 1 | 86060 |
| Inventory / Slab types, quantities and thicknesses | Which floor slab types are present, and how many of each? | 1 | 1 | 85678 |
| Inventory / Slab types, quantities and thicknesses | Which slab types are present with quantities and thicknesses? | 1 | 1 | 85601 |
| Inventory / Slab types, quantities and thicknesses | Which slab types are used and what are their thicknesses? | 1 | 1 | 86167 |
| Inventory / Slab types, quantities and thicknesses | Which slab types are used between floors, with distribution by level? | 1 | 1 | 86313 |
| Inventory / Slab types, quantities and thicknesses | Which slabs are used on the 1.OG floor, with type quantities? | 1 | 1 | 86316 |
| Inventory / Slab types, quantities and thicknesses | Which slabs are used on the 2.OG floor, with type quantities? | 1 | 1 | 86317 |
| Inventory / Slab types, quantities and thicknesses | Which slabs are used on the EG floor, with type quantities? | 1 | 1 | 86315 |
| Inventory / Slab types, quantities and thicknesses | Which slabs are used on the KG floor, with type quantities? | 1 | 1 | 86314 |
| Inventory / Stair types, quantities or specifications | Could you please provide me with the names and quantities of all the stair types used in the building? | 1 | 1 | 86223 |
| Inventory / Stair types, quantities or specifications | What are the specifications for the stairs used in the building? | 1 | 1 | 85541 |
| Inventory / Stair types, quantities or specifications | What kinds of stairs are used here, with quantities by type? | 1 | 1 | 85677 |
| Inventory / Stair types, quantities or specifications | What stair types are used, with their quantities? | 1 | 1 | 86099 |
| Inventory / Stair types, quantities or specifications | Which stair types are installed, with quantities for each type? | 1 | 1 | 86321 |
| Inventory / Stair types, quantities or specifications | Which stair types are used here with quantities? | 1 | 1 | 85591 |
| Inventory / Stair types, quantities or specifications | Which stair types are used in the building? | 1 | 1 | 86050 |
| Inventory / Stair types, quantities or specifications | Which types of stairs are used, including their quantities? | 1 | 1 | 86156 |
| Inventory / Structural components and quantities | Could you provide a detailed breakdown of the building's structural system, including the quantities of each component type for both the superstructure and foundation systems? | 1 | 1 | 86262 |
| Inventory / Structural components and quantities | What are the load-bearing structural elements in the building, including their quantities, and what is the typical load path for vertical loads? | 1 | 1 | 85693 |
| Inventory / Structural components and quantities | What are the main structural elements in this building, grouped by type with their counts? | 1 | 1 | 86057 |
| Inventory / Structural components and quantities | What structural elements are in this building, grouped by type with their counts? | 2 | 1 | 85869 |
| Inventory / Structural components and quantities | What structural elements are present in this building, grouped by type with their counts? | 1 | 1 | 86163 |
| Inventory / Structural components and quantities | Which structural components exist in this building? | 1 | 1 | 85597 |
| Inventory / Structural components and quantities | Which structural elements are present in this building, with counts by element type? | 1 | 1 | 86323 |
| Inventory / Structural components and quantities | Which types of structural members are present, showing quantity breakdown? | 1 | 1 | 85696 |
| Inventory / Tanks | What are the types of tanks used in this building, their quantities, and how are they distributed by building level? | 1 | 1 | 85721 |
| Inventory / Town buildings and categories | What are the names of the religious buildings in the town? | 1 | 1 | 85824 |
| Inventory / Town buildings and categories | What civic buildings are present in the town? | 1 | 1 | 85826 |
| Inventory / Town buildings and categories | What is the breakdown of buildings by category, including their counts? | 1 | 1 | 85832 |
| Inventory / Town gates and fortifications | What are the names of the fortified tower gates in the town? | 1 | 1 | 85822 |
| Inventory / Town gates and fortifications | What are the names of the town gates (without towers)? | 1 | 1 | 85823 |
| Inventory / Town gates and fortifications | What defensive structures exist in the town, broken down by type? | 1 | 1 | 85831 |
| Inventory / Town roads and paths | What road and path elements are modeled in the town? | 1 | 1 | 85829 |
| Inventory / Town water features | What are the water features in the town model? | 1 | 1 | 85830 |
| Inventory / Valves | What are the different types of valves used in this building, how many of each type are there, and how are they distributed across the building levels? | 1 | 1 | 85717 |
| Inventory / Valves | What different types of valves are used in this building, along with their quantities? | 1 | 1 | 86249 |
| Inventory / Valves | What valve types are used in this building, their respective counts, and how are they distributed by building level? | 1 | 1 | 85729 |
| Inventory / Ventilation systems and component categories | What HVAC systems are present in this building, with a breakdown of ventilation systems by type and quantity? | 1 | 1 | 86273 |
| Inventory / Ventilation systems and component categories | What are the components of the HVAC ventilation system, including both a detailed breakdown by category and the major component groups? | 1 | 1 | 86274 |
| Inventory / Ventilation systems and component categories | What component types comprise the ventilation system and their respective counts? | 1 | 1 | 85738 |
| Inventory / Ventilation systems and component categories | What ventilation systems are present in this building and their counts by system type? | 1 | 1 | 85748 |
| Inventory / Vertical circulation types, counts and subcomponents | What types of vertical circulation elements are present in the building (stairs, elevators, ramps, escalators), and how many of each type exist? | 1 | 1 | 85924 |
| Inventory / Vertical circulation types, counts and subcomponents | What types of vertical circulation elements are present in the building (stairs, elevators, ramps, escalators), and how many of each type exist? Please include any relevant sub-components or detailed breakdowns. | 1 | 1 | 85959 |
| Inventory / Wall thickness distribution | What are the different wall thicknesses used in the structural walls, and how many walls have each thickness? | 1 | 1 | 86268 |
| Inventory / Wall types with quantities, optionally materials or properties | Could you provide a categorized breakdown of all walls in the building, including quantities of each wall type and their complete material compositions? | 1 | 1 | 85528 |
| Inventory / Wall types with quantities, optionally materials or properties | Could you provide me with a list of all the different types of interior wall in the building and how many of each type there are? | 1 | 1 | 85577 |
| Inventory / Wall types with quantities, optionally materials or properties | What are the load-bearing wall types, their quantities, and material compositions? | 1 | 1 | 86305 |
| Inventory / Wall types with quantities, optionally materials or properties | What are the non-load-bearing wall types, their quantities, and material compositions? | 1 | 1 | 86306 |
| Inventory / Wall types with quantities, optionally materials or properties | What are the types of interior walls used in the building, and what is the quantity of each type? | 1 | 1 | 85855 |
| Inventory / Wall types with quantities, optionally materials or properties | What structural wall types are used in this building, including their quantities? | 1 | 1 | 86267 |
| Inventory / Wall types with quantities, optionally materials or properties | What types of walls are used in the building, with their quantities? | 4 | 1 | 85897 |
| Inventory / Wall types with quantities, optionally materials or properties | What types of walls are used in the exterior of the building, how many of each type are there, and what are their material compositions? | 1 | 1 | 85529 |
| Inventory / Wall types with quantities, optionally materials or properties | What types of walls are used throughout the building, along with their quantities? | 1 | 1 | 86304 |
| Inventory / Wall types with quantities, optionally materials or properties | What wall types are present in the building and how many of each? | 1 | 1 | 85575 |
| Inventory / Wall types with quantities, optionally materials or properties | What wall types are used in the building, along with their quantities and percentages? | 1 | 1 | 86083 |
| Inventory / Wall types with quantities, optionally materials or properties | What wall types are used in the building, along with their quantities? | 3 | 1 | 85661 |
| Inventory / Wall types with quantities, optionally materials or properties | What wall types are used in the building, including their quantities? | 1 | 1 | 86136 |
| Inventory / Wall types with quantities, optionally materials or properties | What wall types are used in the exterior of the building, with their quantities and percentages? | 1 | 1 | 86084 |
| Inventory / Wall types with quantities, optionally materials or properties | What wall types are used in the exterior of the building, with their quantities? | 1 | 1 | 86210 |
| Inventory / Wall types with quantities, optionally materials or properties | What wall types are used in the interior of the building, including their quantities? | 1 | 1 | 86211 |
| Inventory / Wall types with quantities, optionally materials or properties | What wall types are used in the interior of the building, with their quantities and percentages? | 1 | 1 | 86085 |
| Inventory / Wall types with quantities, optionally materials or properties | What wall types are used throughout the building, with their respective quantities? | 1 | 1 | 86034 |
| Inventory / Wall types with quantities, optionally materials or properties | What walls are used on the interior side of the building, showing quantity breakdown? | 1 | 1 | 85663 |
| Inventory / Wall types with quantities, optionally materials or properties | Which wall types are used for interior partitions, with their counts? | 1 | 1 | 85997 |
| Inventory / Wall types with quantities, optionally materials or properties | Which wall types are used for interior, with their counts? | 3 | 1 | 85899 |
| Inventory / Wall types with quantities, optionally materials or properties | Which wall types are used internally, with their quantities? | 1 | 1 | 86138 |
| Inventory / Wall types with quantities, optionally materials or properties | Which wall types are used on the exterior of the building, including their quantities? | 4 | 1 | 85898 |
| Inventory / Wall types with quantities, optionally materials or properties | Which wall types are used on the exterior side of the building and how many of each? | 1 | 1 | 85576 |
| Inventory / Wall types with quantities, optionally materials or properties | Which wall types form the exterior of the building, with their quantities? | 1 | 1 | 86137 |
| Inventory / Wall types with quantities, optionally materials or properties | Which walls are used for the exterior of the building, with type distribution? | 1 | 1 | 85662 |
| Inventory / Wall types with quantities, optionally materials or properties | Which walls are used on the exterior of the building, with their type distribution? | 1 | 1 | 86307 |
| Inventory / Wall types with quantities, optionally materials or properties | Which walls are used on the interior of the building, with their type distribution? | 1 | 1 | 86308 |
| Inventory / Wall types with quantities, optionally materials or properties | Which walls are used on the interior partitions, and what are their properties including thickness and total length? | 1 | 1 | 86036 |
| Inventory / Wall types with quantities, optionally materials or properties | Which walls form the exterior envelope, and what are their properties including thickness and total length? | 1 | 1 | 86035 |
| Inventory / Walls by load-bearing status, counts or proportions | Could you provide a breakdown of all walls by load-bearing classification, including counts and percentages for load-bearing, non-load-bearing, and unclassified walls? | 1 | 1 | 86216 |
| Inventory / Walls by load-bearing status, counts or proportions | Could you provide a breakdown of the walls by load-bearing status, including the counts and the proportion of load-bearing walls? | 1 | 1 | 86001 |
| Inventory / Walls by load-bearing status, counts or proportions | How many of the walls are load-bearing compared with non-load-bearing? | 1 | 1 | 85582 |
| Inventory / Walls by load-bearing status, counts or proportions | How many walls are load-bearing compared with non-load-bearing? | 1 | 1 | 85671 |
| Inventory / Walls by load-bearing status, counts or proportions | What is the proportion of load-bearing walls in the building, including the total number of walls, the count of load-bearing walls, and the breakdown of load-bearing wall types? | 1 | 1 | 85936 |
| Inventory / Walls by load-bearing status, counts or proportions | What percentage of walls are load-bearing versus non-load-bearing? | 2 | 1 | 86041 |
| Inventory / Walls by load-bearing status, counts or proportions | What percentage of walls are load-bearing vs non-load-bearing? | 2 | 1 | 85858 |
| Inventory / Walls by load-bearing status, counts or proportions | What proportion of walls are load-bearing, including the total count and breakdown of load-bearing walls by type? | 1 | 1 | 85972 |
| Inventory / Walls by load-bearing status, counts or proportions | What proportion of walls are load-bearing? | 1 | 1 | 85902 |
| Inventory / Waste terminals | What different types of waste terminals are used in this building, including their quantities? | 1 | 1 | 86254 |
| Inventory / Waste terminals | What waste terminal types are used in this building, their respective counts, and how are they distributed by building level? | 1 | 1 | 85732 |
| Inventory / Water heaters and water-heating systems | What water heater types are used in this building, their respective counts, and how are they distributed by building level? | 1 | 1 | 85731 |
| Inventory / Water heaters and water-heating systems | What water heating systems are installed in the building, and what are their quantities? | 1 | 1 | 86255 |
| Inventory / Window types and sizes with quantities or percentages | Could you provide a breakdown of all windows in the building by type and size, including the quantity and percentage distribution for each size variation? | 1 | 1 | 86303 |
| Inventory / Window types and sizes with quantities or percentages | What are the different window widths used in the building and how many windows use each width? | 1 | 1 | 85853 |
| Inventory / Window types and sizes with quantities or percentages | What are the distinct window sizes present, along with how many windows exist for each size? | 1 | 1 | 85851 |
| Inventory / Window types and sizes with quantities or percentages | What window types are present in the building, how many of each, and how are they distributed by floor? | 1 | 1 | 86031 |
| Inventory / Window types and sizes with quantities or percentages | What window types are present in this building, including their quantities, percentages, and distribution by floor? | 1 | 1 | 86081 |
| Inventory / Window types and sizes with quantities or percentages | What window types are used in this building and their respective counts? | 1 | 1 | 85523 |
| Inventory / Window types and sizes with quantities or percentages | What window types are used in this building, with their quantities? | 1 | 1 | 86206 |
| Inventory / Window types and sizes with quantities or percentages | Which types of windows are present in the building, with quantity distribution? | 1 | 1 | 85660 |
| Inventory / Window types and sizes with quantities or percentages | Which window types are present in the building and how many of each? | 1 | 1 | 85572 |
| Inventory / Window types and sizes with quantities or percentages | Which window types are present in this building, including their sizing and quantities? | 4 | 1 | 85896 |
| Inventory / Window types and sizes with quantities or percentages | Which window types are present in this building, with their quantities? | 1 | 1 | 86134 |
| Length / Electrical conduits, optionally with segment statistics | Could you provide a comprehensive analysis of conduit usage in this building, including the total length, number of segments, and distribution by floor? | 1 | 1 | 86234 |
| Length / Exterior and interior walls together or compared | What is the total combined length of the exterior and interior walls? | 1 | 1 | 85672 |
| Length / Exterior and interior walls together or compared | What is the total length of exterior compared to interior walls? | 1 | 1 | 86144 |
| Length / Exterior and interior walls together or compared | What is the total length of exterior vs interior walls? | 1 | 1 | 86217 |
| Length / Exterior walls | What is the total length of exterior walls? | 6 | 1 | 85534 |
| Length / Exterior walls | What is the total length of outside walls? | 1 | 1 | 85584 |
| Length / Flexible cable pipes, quantities and proportions | Could you provide a comprehensive analysis of the flexible cable pipe usage in this building, including total quantities, lengths, proportions, and a breakdown by component types? | 1 | 1 | 86238 |
| Length / Heating pipe network, optionally with segment statistics | Could you provide a comprehensive analysis of the hydronic pipe network, including total pipe length, segment counts, and distribution statistics? | 1 | 1 | 86283 |
| Length / Heating pipe network, optionally with segment statistics | What is the total length of pipe used in the heating system, and how is this distributed by building level? | 1 | 1 | 85714 |
| Length / Interior walls | What is the total combined length of inside walls? | 1 | 1 | 85583 |
| Length / Interior walls | What is the total length of interior walls? | 2 | 1 | 85533 |
| Length / Pipes (system unspecified) | What is the total length of piping in the building? | 1 | 1 | 86171 |
| Length / Pipes (system unspecified) | What is the total length of piping used in this building? | 1 | 1 | 86114 |
| Length / Pipes and ducts together | What is the total length of pipes and ducts in the building, broken down by type (heating pipes, plumbing pipes, and ventilation ducts)? | 1 | 1 | 85712 |
| Length / Plumbing pipe network, optionally with segment statistics | Could you provide a comprehensive analysis of the pipe lengths in the plumbing system, including total length, segment counts, and distribution metrics? | 1 | 1 | 86248 |
| Length / Plumbing pipe network, optionally with segment statistics | What is the total length of pipe used in the plumbing system, and how is this distributed by building level? | 1 | 1 | 85726 |
| Length / Plumbing pipe network, optionally with segment statistics | What is the total length of water supply piping in the building? | 2 | 1 | 85555 |
| Length / Skirting boards | What is the total length of skirting boards needed? | 1 | 1 | 85784 |
| Length / Steel beams by type | What is the total length of steel beams used in this building, broken down by each beam type? | 1 | 1 | 86271 |
| Length / Ventilation ductwork, optionally with segment statistics | Could you provide a comprehensive analysis of the ductwork in the ventilation system, including total length, segment counts, and distribution by building levels? | 1 | 1 | 86279 |
| Length / Ventilation ductwork, optionally with segment statistics | What is the total length of ductwork used in the ventilation system and the breakdown by building level? | 1 | 1 | 85739 |
| Overview / Building metrics combining counts, areas or elevations | What are the key building metrics including element counts, number of levels, total spaces, and footprint area? | 1 | 1 | 86021 |
| Overview / Building metrics combining counts, areas or elevations | What are the key building metrics including total elements, number of spaces, and building levels with their elevations? | 1 | 1 | 86121 |
| Overview / Building metrics combining counts, areas or elevations | What are the number of levels, building footprint area, total floor area, and total number of rooms/spaces? | 1 | 1 | 85560 |
| Overview / Building metrics combining counts, areas or elevations | What is the building's total floor area, number of levels, total spaces, and program breakdown by floor? | 1 | 1 | 85650 |
| Overview / Building metrics combining counts, areas or elevations | What is the building's total gross floor area, number of levels, total spaces, and area distribution by floor? | 1 | 1 | 86294 |
| Overview / Project, location, building function or historical identity | What are the key project information and spatial layout specifications for this building? | 1 | 1 | 86178 |
| Overview / Project, location, building function or historical identity | What is the building's type and its function? | 1 | 1 | 85558 |
| Overview / Project, location, building function or historical identity | What is the project information and location details for this building? | 1 | 1 | 86020 |
| Overview / Project, location, building function or historical identity | What is the project information and location for this building? | 3 | 1 | 85882 |
| Overview / Project, location, building function or historical identity | What is the project information, building name and usage, and location data for this building? | 2 | 1 | 85841 |
| Overview / Project, location, building function or historical identity | What is the project information, site location, and building details for this project? | 1 | 1 | 85948 |
| Overview / Project, location, building function or historical identity | What is the project name and location coordinates for this building? | 1 | 1 | 86120 |
| Overview / Project, location, building function or historical identity | What is the project name, building name, location, and basic characteristics of this building? | 1 | 1 | 86293 |
| Overview / Project, location, building function or historical identity | What town does this model represent and what historical period does it depict? | 1 | 1 | 85840 |
| Overview / Project, location, building function or historical identity | What type of building is this and where is it situated? | 1 | 1 | 85649 |
| Overview / Residential or level layout and organization | What is the general composition and description of Level 1 in the building? | 1 | 1 | 86200 |
| Overview / Residential or level layout and organization | What is the general composition and layout of level 12? | 1 | 1 | 86201 |
| Overview / Residential or level layout and organization | What is the interior layout of the residential buildings? | 1 | 1 | 85835 |
| Overview / Residential or level layout and organization | What is the typical room configuration found in the residential units? | 1 | 1 | 85991 |
| Overview / Residential or level layout and organization | What space distribution information is available for this building, including building type, number of residential units, and floor organization? | 1 | 1 | 86199 |
| Overview / Structural system, concept or efficiency | Can you provide an analysis of the building's structural system, including the likely structural type, a breakdown of structural components with their quantities, and the materials used? | 1 | 1 | 85909 |
| Overview / Structural system, concept or efficiency | Could you provide a comprehensive assessment of the building's structural system efficiency, including the system type, element ratios, building characteristics, and overall efficiency rating? | 1 | 1 | 85698 |
| Overview / Structural system, concept or efficiency | What are the possible structural systems of this building, given the available model data? | 1 | 1 | 86013 |
| Overview / Structural system, concept or efficiency | What is the structural concept of the building? | 2 | 1 | 85550 |
| Overview / Structural system, concept or efficiency | What is the structural system applied in this building, including element counts? | 1 | 1 | 85685 |
| Overview / Structural system, concept or efficiency | What is the structural system of the building? | 1 | 1 | 86322 |
| Overview / Structural system, concept or efficiency | What type of structural system is used in the building, and how is the structural grid determined? | 1 | 1 | 85692 |
| Overview / Town defensive layout and strategy | What are the specific components of the town's defensive layout, and what does this structure suggest about the fortification strategy? | 1 | 1 | 85834 |
| Property / Beam spans and sizes | What are the spans and sizes of the beams? | 1 | 1 | 85689 |
| Property / Building envelope airtightness | What is the air tightness rating of the building envelope? | 1 | 1 | 85778 |
| Property / Building level heights and elevations | Could you provide a detailed breakdown of all building levels, including their elevation heights and floor-to-floor heights? | 1 | 1 | 86219 |
| Property / Building level heights and elevations | What are the elevation and floor-to-floor heights for each level? | 1 | 1 | 86077 |
| Property / Building level heights and elevations | What are the elevation, floor height, and floor-to-floor height for each level? | 1 | 1 | 86026 |
| Property / Building level heights and elevations | What are the elevations for each level? | 1 | 1 | 85848 |
| Property / Building level heights and elevations | What are the elevations of the building levels? | 1 | 1 | 85957 |
| Property / Building level heights and elevations | What are the floor-to-floor heights between all consecutive levels? | 1 | 1 | 85521 |
| Property / Building level heights and elevations | What are the heights of each level? | 1 | 1 | 85567 |
| Property / Building level heights and elevations | What are the heights of the building levels? | 3 | 1 | 85891 |
| Property / Building level heights and elevations | What are the heights of the individual levels? | 2 | 1 | 86148 |
| Property / Building level heights and elevations | What is the floor to floor height between the first and the second floor? | 1 | 1 | 85631 |
| Property / Building level heights and elevations | What is the floor-to-floor height between the ground floor and first floor? | 1 | 1 | 85757 |
| Property / Building thermal bridges | Are there any thermal bridges identified in the model? | 1 | 1 | 85777 |
| Property / Ceiling GUID | What is the GUID of the ceiling in the living room of house A? | 1 | 1 | 85797 |
| Property / Ceiling materials or systems | What materials are used in the ceilings? | 3 | 1 | 85861 |
| Property / Ceiling materials or systems | What type of ceiling system is installed in office areas? | 1 | 1 | 85624 |
| Property / Ceiling materials or systems | Which ceiling materials are used in the building? | 1 | 1 | 85587 |
| Property / Ceiling materials or systems | Which materials are applied in the ceilings, including element counts? | 1 | 1 | 85669 |
| Property / Ceiling materials or systems | Which materials are used for the ceilings? | 1 | 1 | 86046 |
| Property / Ceiling materials or systems | Which materials are used in the ceilings? | 5 | 1 | 85906 |
| Property / Column dimensions | What are the column dimensions? | 2 | 1 | 85872 |
| Property / Column dimensions | What are the sizes of the columns? | 1 | 1 | 85600 |
| Property / Conduit materials and applications | Could you provide a detailed analysis of conduit materials in the building, including the breakdown by type with quantities, materials from specifications, and the primary materials used for different conduit applications? | 1 | 1 | 86235 |
| Property / Construction phasing and renovation status | What phasing information is available? | 1 | 1 | 85557 |
| Property / Construction phasing and renovation status | Which construction phases are represented in the model? | 1 | 1 | 86067 |
| Property / Construction phasing and renovation status | Which elements correspond to renovation work versus existing construction? | 1 | 1 | 86068 |
| Property / Defensive wall heights | What are the heights of the defensive walls? | 1 | 1 | 85836 |
| Property / Door fire ratings or rating availability | Is fire rating information available for any door types in this model? | 1 | 1 | 85980 |
| Property / Door fire ratings or rating availability | Is fire rating information available for doors in this model? | 3 | 1 | 85683 |
| Property / Door fire ratings or rating availability | What is the fire rating of the internal doors? | 1 | 1 | 85768 |
| Property / Door fire ratings or rating availability | Which door types have fire rating information, and how many doors of each type are there? | 1 | 1 | 86225 |
| Property / Door fire ratings or rating availability | Which door types have fire rating information? | 3 | 1 | 85535 |
| Property / Door fire ratings or rating availability | Which door types include fire rating data? | 1 | 1 | 86055 |
| Property / Door fire ratings or rating availability | Which door types include fire rating information? | 2 | 1 | 85944 |
| Property / Door fire ratings or rating availability | Which types of doors include fire rating details? | 1 | 1 | 85595 |
| Property / Door width or dimensions | What is the width of the door 1hOSvn6df7F8_7GcBWlRGQ ? | 1 | 1 | 85755 |
| Property / Door width or dimensions | What is the width of the main entrance door? | 1 | 1 | 85611 |
| Property / Electrical distribution capacity availability | Are electrical distribution equipment capacities available? | 1 | 1 | 85706 |
| Property / Electrical loads, optionally equipment or floor breakdowns | Could you provide a comprehensive breakdown of the electrical load for water heaters, including the total load, average per unit, number of units with load data, and the load distribution by building level? | 1 | 1 | 85735 |
| Property / Electrical loads, optionally equipment or floor breakdowns | What are the electrical loads by system type? | 1 | 1 | 85707 |
| Property / Electrical loads, optionally equipment or floor breakdowns | What electrical load information is available for water heaters, including any typical specifications? | 1 | 1 | 86256 |
| Property / Electrical loads, optionally equipment or floor breakdowns | What electrical loads are present in the building, broken down by equipment type? | 1 | 1 | 85705 |
| Property / Electrical loads, optionally equipment or floor breakdowns | What is the building's electrical load? | 1 | 1 | 86333 |
| Property / Electrical voltage levels | What are the voltage levels used in the electrical system? | 1 | 1 | 85708 |
| Property / Energy consumption or efficiency | What is the predicted annual energy consumption? | 1 | 1 | 85816 |
| Property / Energy consumption or efficiency | What is the total energy efficiency rating of the building? | 1 | 1 | 85710 |
| Property / External-wall insulation type or thickness | What information is available about the insulation used in the external walls? | 1 | 1 | 85607 |
| Property / External-wall insulation type or thickness | What is the thickness of the insulation of the external walls? | 2 | 1 | 85606 |
| Property / External-wall insulation type or thickness | What type of insulation is used in the external walls? | 1 | 1 | 85776 |
| Property / Fire protection or suppression system | What information is available in the BIM model about the fire protection systems in place? | 1 | 1 | 86332 |
| Property / Fire protection or suppression system | What type of fire suppression system is installed? | 1 | 1 | 85810 |
| Property / Floor live-load capacity | What is the live load capacity of the first floor? | 1 | 1 | 85767 |
| Property / Foundation depth | What is the depth of the foundation? | 1 | 1 | 85761 |
| Property / Foundation materials | What are the foundations made of? | 1 | 1 | 85647 |
| Property / Heating capacity or equipment specifications | What are the specifications of the hot water heating equipment in the model? | 1 | 1 | 85806 |
| Property / Heating capacity or equipment specifications | What is the total heating capacity of all radiators? | 1 | 1 | 85723 |
| Property / Light-fixture presence | Are light fixtures included in this building model? | 1 | 1 | 85916 |
| Property / Maintenance requirements or schedules | Could you provide a categorized breakdown of the technical elements in the building that typically require regular maintenance, organized by system type? | 1 | 1 | 85814 |
| Property / Maintenance requirements or schedules | What is the maintenance schedule for the HVAC system? | 1 | 1 | 85813 |
| Property / Maintenance requirements or schedules | What maintenance requirements exist for MEP systems? | 1 | 1 | 85711 |
| Property / Model software and IFC standards | What modelling program and IFC standard were used to create this model? | 1 | 1 | 85820 |
| Property / Model software and IFC standards | What modelling program and ifc standard were used to create this model? | 1 | 1 | 85515 |
| Property / Model software and IFC standards | What software and ifc standards were used to create this model? | 1 | 1 | 85559 |
| Property / Model software and IFC standards | What software and modeling standards were used in this BIM model? Please provide a breakdown of each component. | 1 | 1 | 86179 |
| Property / Model software and IFC standards | What software and modeling standards were used? | 2 | 1 | 85842 |
| Property / Model software and IFC standards | Which software and modeling standards were applied? | 6 | 1 | 85883 |
| Property / Model software and IFC standards | Which software and standards were applied? | 1 | 1 | 86022 |
| Property / Model software and IFC standards | Which software tools and modeling standards were applied? | 1 | 1 | 85651 |
| Property / Parking dimensions and capacity | What are the dimensions and parking capacity of the lot? | 1 | 1 | 85657 |
| Property / Pipe materials and quantities | What is the breakdown of pipe materials in the building, including the quantities and percentages of each type? | 1 | 1 | 86260 |
| Property / Renewable-energy systems presence | Are there any renewable energy systems integrated into the design? | 1 | 1 | 85817 |
| Property / Residential-building construction materials | What construction materials were used for the residential buildings? | 1 | 1 | 85837 |
| Property / Roof material lifespan | Can you provide information about the expected lifespan of the roofing material, including whether this data is available in the BIM model? | 1 | 1 | 85780 |
| Property / Roof material lifespan | What is the expected lifespan of the roofing material? | 1 | 1 | 85639 |
| Property / Room and ceiling heights | What are the heights of the ceilings? | 1 | 1 | 85665 |
| Property / Room and ceiling heights | What is the average room height for the interaction stations? | 1 | 1 | 85617 |
| Property / Room and ceiling heights | What is the ceiling height in treatment room 2A12? | 1 | 1 | 85609 |
| Property / Room and ceiling heights | What is the height of the ceiling in room A203? | 1 | 1 | 85752 |
| Property / Room wall or floor finishes | What is the wall finishing material in treatment room 1D34? | 1 | 1 | 85623 |
| Property / Room wall or floor finishes | What type of flooring is used in the sterilization room? | 1 | 1 | 85622 |
| Property / Slab materials | What materials are used in the slabs, organized by slab type? | 1 | 1 | 86318 |
| Property / Steel beams spanning a specified room | Are there any steel beams spanning the living room of Duplex B? | 1 | 1 | 85763 |
| Property / Structural materials | What materials are used for the structural system? | 1 | 1 | 85688 |
| Property / Structural reinforcement for medical equipment | Are there any reinforced areas for heavy medical equipment? | 1 | 1 | 85621 |
| Property / Toilet water efficiency | What is the water efficiency rating of the toilets? | 1 | 1 | 85818 |
| Property / Ventilation insulation and coverage | What insulation types are used in the ventilation system, showing coverage distribution? | 1 | 1 | 86289 |
| Property / Ventilation requirements | What are the specified ventilation requirements? | 1 | 1 | 86334 |
| Property / Waiting-area capacities | What are the estimated capacities for each waiting area in the building? | 1 | 1 | 85614 |
| Property / Wall acoustic rating | What is the sound transmission class (STC) rating between treatment rooms? If this information is not directly available in the BIM model, what are the typical STC ratings for similar partition wall constructions? | 1 | 1 | 85626 |
| Property / Wall fire ratings or rating availability | What information is available in the BIM model regarding fire-rated walls between different zones? | 1 | 1 | 85771 |
| Property / Wall fire ratings or rating availability | What is the fire rating of the walls between treatment rooms? | 1 | 1 | 85644 |
| Property / Wall load-bearing status | Are the interior walls load bearing? | 1 | 1 | 85627 |
| Property / Wall load-bearing status | What are the different wall types in room A203 and what are their load-bearing characteristics? | 1 | 1 | 85760 |
| Property / Wall load-bearing status | Which walls are the main structural ones? | 1 | 1 | 85766 |
| Property / Wall materials and construction layers | Could you provide a comprehensive breakdown of all wall materials used in the building, including the total count of unique materials, a complete list of all materials, and the material composition for each wall type? | 1 | 1 | 86212 |
| Property / Wall materials and construction layers | Could you provide a detailed breakdown of the external wall construction, including all layers, their materials, and thickness measurements? | 1 | 1 | 85801 |
| Property / Wall materials and construction layers | What materials are applied in the outer walls and their distribution across wall types? | 1 | 1 | 85579 |
| Property / Wall materials and construction layers | What materials are found in the internal walls and their distribution across wall types? | 1 | 1 | 85580 |
| Property / Wall materials and construction layers | What materials are specified for the interior walls? | 1 | 1 | 86039 |
| Property / Wall materials and construction layers | What materials are used for each wall type? | 1 | 1 | 85934 |
| Property / Wall materials and construction layers | What materials are used for the exterior walls? | 1 | 1 | 86038 |
| Property / Wall materials and construction layers | What materials are used in each wall type, along with their layer thicknesses? | 1 | 1 | 85900 |
| Property / Wall materials and construction layers | What materials are used in each wall type? | 2 | 1 | 85856 |
| Property / Wall materials and construction layers | What materials are used in the exterior walls? | 3 | 1 | 86087 |
| Property / Wall materials and construction layers | What materials are used in the interior walls? | 3 | 1 | 86088 |
| Property / Wall materials and construction layers | What materials are used in the walls? | 1 | 1 | 86086 |
| Property / Wall materials and construction layers | What materials are used on the building's exterior walls? | 1 | 1 | 85667 |
| Property / Wall materials and construction layers | What walls are used in the interior of the building and what are they made of? | 1 | 1 | 85530 |
| Property / Wall materials and construction layers | Which materials are used for the walls, organized by wall type? | 1 | 1 | 86311 |
| Property / Wall materials and construction layers | Which materials are used for the walls? | 2 | 1 | 85666 |
| Property / Wall materials and construction layers | Which materials are used in the interior walls? | 2 | 1 | 85668 |
| Property / Wall materials and construction layers | Which materials are used to construct the walls and their usage across wall types? | 1 | 1 | 85578 |
| Property / Wall materials and construction layers | Which materials are used to construct the walls? | 1 | 1 | 86037 |
| Property / Wall materials and construction layers | Which materials is used in the exterior walls? | 1 | 1 | 85998 |
| Property / Wall thicknesses or layer dimensions | Could you provide a list of all wall types used in the project and their corresponding thickness measurements? | 1 | 1 | 86215 |
| Property / Wall thicknesses or layer dimensions | What are specific thickness values for each wall type? | 1 | 1 | 85857 |
| Property / Wall thicknesses or layer dimensions | What are the thicknesses of the different wall types? | 5 | 1 | 85901 |
| Property / Wall thicknesses or layer dimensions | What are the thicknesses of the various wall types? | 2 | 1 | 85581 |
| Property / Wall thicknesses or layer dimensions | What is the thickness of each wall type? | 1 | 1 | 85532 |
| Property / Wall thicknesses or layer dimensions | What is the thickness of the external walls? | 1 | 1 | 85764 |
| Property / Wall thicknesses or layer dimensions | What is the thickness range and specific thickness values for each wall type? | 1 | 1 | 86089 |
| Property / Wall thicknesses or layer dimensions | What thicknesses do the different wall types have? | 1 | 1 | 85670 |
| Property / Window fire ratings or rating availability | Is fire rating data available for windows in this model? | 1 | 1 | 85684 |
| Property / Window fire ratings or rating availability | Is fire rating information available for windows in this model? | 3 | 1 | 85913 |
| Property / Window fire ratings or rating availability | Which window types have fire rating data? | 1 | 1 | 86162 |
| Property / Window fire ratings or rating availability | Which window types have fire rating information? | 3 | 1 | 85868 |
| Property / Window fire ratings or rating availability | Which window types include fire rating information? | 2 | 1 | 86017 |
| Property / Window fire ratings or rating availability | Which windows have fire rating information? | 1 | 1 | 85596 |
| Property / Window glazing type | Can you determine whether the windows are single or double glazed based on the available BIM model data? | 1 | 1 | 85628 |
| Property / Window glazing type | Which type of glazing is used in the windows? | 2 | 1 | 85524 |
| Property / Window height or dimensions | Can you give me the height of each window type? | 1 | 1 | 85793 |
| Property / Window height or dimensions | What are the dimensions of the window with guid 0otfaO0qPDAhynjJ6DmgH8? | 1 | 1 | 85632 |
| Property / Window solar heat gain coefficient | What is the solar heat gain coefficient of the windows? | 1 | 1 | 85779 |
| Property / Window warranty | What is the warranty period for the installed windows? | 1 | 1 | 85781 |
| Ranking / Door widths, extrema, top-k or statistics | Could you please provide the names and widths of the five largest types of door (by width) used in the building? Could you also provide the average door width and the range of door widths? | 1 | 1 | 86080 |
| Ranking / Door widths, extrema, top-k or statistics | What is the average door width in the building? | 1 | 1 | 85536 |
| Ranking / Door widths, extrema, top-k or statistics | What is the building's average door width, including maximum and minimum? | 1 | 1 | 85675 |
| Ranking / Door widths, extrema, top-k or statistics | What is the largest door width that is used in the building? | 1 | 1 | 85537 |
| Ranking / Door widths, extrema, top-k or statistics | What is the largest door width used in the building, and what type of door has this width? | 1 | 1 | 86204 |
| Ranking / Door widths, extrema, top-k or statistics | What is the narrowest door width used here? | 1 | 1 | 85571 |
| Ranking / Door widths, extrema, top-k or statistics | What is the narrowest door width used in the building, and which doors have this width? | 1 | 1 | 86030 |
| Ranking / Door widths, extrema, top-k or statistics | What is the smallest door width used in the building? | 1 | 1 | 86205 |
| Ranking / Door widths, extrema, top-k or statistics | What is the widest door used in the building? | 1 | 1 | 86133 |
| Ranking / Door widths, extrema, top-k or statistics | Which door has the largest width in the building? | 1 | 1 | 85676 |
| Ranking / Door widths, extrema, top-k or statistics | Which door model has the largest width? | 1 | 1 | 85993 |
| Ranking / Door widths, extrema, top-k or statistics | Which three doors have the greatest widths in the building? | 1 | 1 | 86029 |
| Ranking / Door widths, extrema, top-k or statistics | Which two doors have the greatest widths in the building? | 1 | 1 | 85570 |
| Ranking / Largest room or rooms by area | Can room sizes be compared to identify the largest room on the first floor? | 1 | 1 | 86202 |
| Ranking / Largest room or rooms by area | What is the largest room in the building? | 2 | 1 | 85849 |
| Ranking / Largest room or rooms by area | Which room in the building is the largest? | 4 | 1 | 85568 |
| Ranking / Largest room or rooms by area | Which rooms in the building are the largest, and what are their details? | 1 | 1 | 86301 |
| Ranking / Rooms with highest or lowest ceilings | What are the top 5 rooms with the highest ceiling heights? | 1 | 1 | 86102 |
| Ranking / Rooms with highest or lowest ceilings | What are the top 5 rooms with the lowest ceiling heights? | 1 | 1 | 86103 |
| Ranking / Rooms with highest or lowest ceilings | Which rooms have the highest ceiling heights, and what is that height value? | 1 | 1 | 86053 |
| Ranking / Rooms with highest or lowest ceilings | Which rooms have the tallest ceilings? | 2 | 1 | 85594 |
| Ranking / Rooms with highest or lowest ceilings | Which spaces have the tallest ceiling heights? | 1 | 1 | 85681 |
| Ranking / Window widths, extrema or top-k | What are the top 5 largest window widths used in the building? | 1 | 1 | 86082 |
| Ranking / Window widths, extrema or top-k | What is the largest window width used in the building, and which window type has this width? | 1 | 1 | 86207 |
| Ranking / Window widths, extrema or top-k | What is the largest window width used in this building? | 1 | 1 | 86135 |
| Ranking / Window widths, extrema or top-k | What is the maximum window width used in this building, and which windows have this width? | 1 | 1 | 86032 |
| Ranking / Window widths, extrema or top-k | What is the minimum window width used in the building, and which windows have this width? | 1 | 1 | 86033 |
| Ranking / Window widths, extrema or top-k | What is the narrowest window width used in this building? | 1 | 1 | 85574 |
| Ranking / Window widths, extrema or top-k | What is the smallest window width used in the building, and which window type has this dimension? | 1 | 1 | 86208 |
| Ranking / Window widths, extrema or top-k | What is the widest window in the building? | 1 | 1 | 85573 |
| Spatial / Emergency escape-route width | What is the width of the emergency escape routes? | 1 | 1 | 85772 |
| Spatial / Emergency-exit route distance | What is the distance from the furthest point to the nearest emergency exit? | 1 | 1 | 85770 |
| Spatial / Emergency-exit route distance | What is the estimated distance from treatment room 1E12 to the nearest emergency exit, including the path taken for this estimation? | 1 | 1 | 85618 |
| Spatial / Emergency-exit route distance | What is the estimated distance from treatment room 1E23 to the nearest emergency exit, including the path taken? | 1 | 1 | 85619 |
| Spatial / Equipment locations | Where are the main electrical panels located? | 1 | 1 | 85803 |
| Spatial / Equipment locations | Where are the main utility shut-off valves located? | 1 | 1 | 85812 |
| Spatial / Equipment locations | Where are the scanning equipments located? | 1 | 1 | 85638 |
| Spatial / Equipment locations | Where are the smoke detectors located? | 1 | 1 | 85809 |
| Spatial / Fire exits and their locations | Could you provide a breakdown of potential fire exits by room/space on each floor? | 1 | 1 | 85539 |
| Spatial / Fire exits and their locations | What information is available about fire exits in the building? | 1 | 1 | 85769 |
| Spatial / Fire-extinguisher presence and locations | Are there any fire extinguishers in the BIM model, and if so, where are they located? | 1 | 1 | 85811 |
| Spatial / Highest-ground buildings and location | Which building(s) stand on the highest ground elevation, and in which part of the town are they located? | 1 | 1 | 85825 |
| Spatial / Nearest town gate | Which gate is closest to the hospital? | 1 | 1 | 85838 |
| Spatial / Room adjacency or connectivity | Which rooms are adjacent to room 1B07? | 1 | 1 | 85634 |
| Spatial / Room adjacency or connectivity | Which rooms are connected to room 1B07? | 1 | 1 | 85633 |
| Spatial / Rooms served by thermostats or air systems | Which rooms have thermostats installed? | 1 | 1 | 85807 |
| Spatial / Rooms served by thermostats or air systems | Which spaces have supply air and return air systems? | 1 | 1 | 85554 |
| Spatial / Rooms with direct outdoor access | Which rooms have direct access to outdoor spaces? | 1 | 1 | 85540 |
| Spatial / Server-room location and identifier | Where is the server room located and what is its designation? | 1 | 1 | 85620 |
| Sustainability / Material recyclability | What is the recyclability assessment of different building material types at end-of-life? | 1 | 1 | 85790 |
| Sustainability / Recycled material content | Which materials have recycled content? | 1 | 1 | 85819 |
| Volume / Concrete across structural components | What is the total concrete volume used in slabs, columns and beams? | 1 | 1 | 85915 |
| Volume / Concrete across structural components | What is the total concrete volume used in this building, and how is it distributed across different structural elements? | 1 | 1 | 86270 |
| Volume / Concrete across structural components | What is the total concrete volume used structurally, with breakdown by element type? | 1 | 1 | 85694 |
| Volume / Concrete across structural components | What is the total volume of concrete used? | 1 | 1 | 85543 |
| Volume / Foundation concrete | What is the total volume of concrete used in foundation? | 1 | 1 | 85546 |
| Volume / Foundation concrete | What is the volume of concrete required for the foundation? | 2 | 1 | 85648 |
| Volume / Insulation | What is the estimated volume of insulation material needed for each building component? | 1 | 1 | 85786 |
| Volume / Insulation | What is the total volume of insulation material needed for exterior walls that have insulation material in their structure? | 1 | 1 | 85531 |
| Volume / Slabs, optionally grouped by type or level | What is the combined total volume of all the floor slabs ? | 1 | 1 | 85943 |
| Volume / Slabs, optionally grouped by type or level | What is the sum of all floor slab volumes in the building? | 1 | 1 | 85866 |
| Volume / Slabs, optionally grouped by type or level | What is the total volume of all floor slabs combined, and could you provide a breakdown of the volume by slab type? | 1 | 1 | 85911 |
| Volume / Slabs, optionally grouped by type or level | What is the total volume of all floor slabs combined? | 5 | 1 | 85979 |
| Volume / Slabs, optionally grouped by type or level | What is the total volume of concrete used in floor slabs? | 1 | 1 | 85545 |
| Volume / Slabs, optionally grouped by type or level | What is the total volume of the slabs with the breakdown by slab type? | 1 | 1 | 85592 |
| Volume / Slabs, optionally grouped by type or level | What is the volume breakdown of floor slabs grouped by floor and the total volume? | 1 | 1 | 85542 |
| Volume / Wall concrete | What is the total volume of concrete used in walls? | 1 | 1 | 85544 |

</details>

### Opening Design

<details>
<summary>64 rows in 64 exact texts or parameterized templates</summary>

| Family | Verbatim question or example | Rows | Distinct question texts | First JSONL line |
| --- | --- | --- | --- | --- |
| Area / One room or space | On sheet A-801 of the Xcel Sports Complex drawings, what is the area of room 118 (Fitness Center) in the finish room schedule? | 1 | 1 | 89422 |
| Area / One room or space | On sheet A-801 of the Xcel Sports Complex drawings, what is the area of room 121 (Clinic) in the finish room schedule? | 1 | 1 | 89424 |
| Area / One room or space | On sheet A-801 of the Xcel Sports Complex drawings, what is the area of room 122 (Wrestling) in the finish room schedule? | 1 | 1 | 89423 |
| Area / One room or space | On sheet A-801 of the Xcel Sports Complex drawings, what is the area of room 128 (Fieldhouse) in the finish room schedule? | 1 | 1 | 89421 |
| Area / Room areas filtered by finish | On sheet A-801 of the Xcel Sports Complex drawings, what is the total area of rooms with floor finish F4 (resilient flooring)? | 1 | 1 | 89430 |
| Area / Selected room or function totals | On sheet A-801 of the Xcel Sports Complex drawings, what is the combined area of the women's and men's locker rooms? | 1 | 1 | 89428 |
| Area / Selected room or function totals | On sheet A-801 of the Xcel Sports Complex drawings, what is the total area of all rooms that have an area listed in the finish room schedule? | 1 | 1 | 89425 |
| Area / Selected room or function totals | On sheet A-801 of the Xcel Sports Complex drawings, what is the total area of the rooms named OFFICE in the finish room schedule? | 1 | 1 | 89426 |
| Area / Selected room or function totals | On sheet A-801 of the Xcel Sports Complex drawings, what is the total area of the rooms named RESTROOM in the finish room schedule? | 1 | 1 | 89427 |
| Compound / Room counts and areas | On sheet A-801 of the Xcel Sports Complex drawings, how many rooms have floor finish F0 (unfinished concrete slab), and what is their total area? | 1 | 1 | 89429 |
| Compound / Toilet, washbasin and shower counts together | On sheet A-701 (Restrooms) of the Xcel Sports Complex drawings, how many water closets, lavatories and showers are drawn in enlarged plan 6B 'Restroom with Shower'? | 1 | 1 | 89440 |
| Count / Door leaves | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many door leaves of the types whose description starts with 'SWING' are scheduled? | 1 | 1 | 89448 |
| Count / Door-schedule entries including non-door items | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many items in total are counted in the door type schedule (all type marks, including gates, access panels and clear openings)? | 1 | 1 | 89447 |
| Count / Doors | On sheet A-801 of the Xcel Sports Complex drawings, how many doors (door numbers) are listed in the door schedule? | 1 | 1 | 89397 |
| Count / Doors | On sheet A-801 of the Xcel Sports Complex drawings, how many doors does the door schedule list for room 118 (Fitness Center)? | 1 | 1 | 89412 |
| Count / Doors | On sheet A-801 of the Xcel Sports Complex drawings, how many doors does the door schedule list for room 128 (Fieldhouse)? | 1 | 1 | 89413 |
| Count / Doors | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule are 3'-0" wide? | 1 | 1 | 89410 |
| Count / Doors | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule are 7'-0" high? | 1 | 1 | 89411 |
| Count / Doors | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule are door type A1 (swing door)? | 1 | 1 | 89398 |
| Count / Doors | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule are door type A2 (double swing door)? | 1 | 1 | 89399 |
| Count / Doors | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule are door type B1 (aluminium door with glazing)? | 1 | 1 | 89400 |
| Count / Doors | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule are door type B2 (double aluminium door with glazing)? | 1 | 1 | 89401 |
| Count / Doors | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule are door type B3 (aluminium sliding door)? | 1 | 1 | 89402 |
| Count / Doors | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule are door type C1 (roll-up insulated door)? | 1 | 1 | 89403 |
| Count / Doors | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule carry note A (wide stile)? | 1 | 1 | 89407 |
| Count / Doors | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule carry note B (opens 180°)? | 1 | 1 | 89408 |
| Count / Doors | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule carry note C (card reader)? | 1 | 1 | 89409 |
| Count / Doors | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule have a wood solid core door (material WD-1)? | 1 | 1 | 89404 |
| Count / Doors | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule have aluminium storefront frames (AL-1 or AL-2)? | 1 | 1 | 89406 |
| Count / Doors | On sheet A-801 of the Xcel Sports Complex drawings, how many doors in the door schedule have an interior-grade hollow metal frame (STL-1)? | 1 | 1 | 89405 |
| Count / Doors | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many 2'-10" x 6'-8" privacy swing doors (type U02) are scheduled? | 1 | 1 | 89442 |
| Count / Doors | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many Marvin Essential sliding patio doors are scheduled in total? | 1 | 1 | 89443 |
| Count / Doors | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many Marvin Essential sliding patio doors are scheduled on the 3rd floor? | 1 | 1 | 89444 |
| Count / Doors | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many Vistagrande fiberglass entry doors are scheduled on the 1st floor? | 1 | 1 | 89445 |
| Count / Doors | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many doors with an acoustical seal (type U41) are scheduled? | 1 | 1 | 89446 |
| Count / Doors | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many sliding flush wood doors (types U06 and U44) are scheduled? | 1 | 1 | 89449 |
| Count / Doors | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many unit entry doors (type U01) are scheduled? | 1 | 1 | 89441 |
| Count / Gates | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many chain-link gates (type U22) are scheduled? | 1 | 1 | 89452 |
| Count / Rooms and spaces | On sheet A-801 of the Xcel Sports Complex drawings, how many rooms are listed in the finish room schedule? | 1 | 1 | 89420 |
| Count / Rooms filtered by finish | On sheet A-801 of the Xcel Sports Complex drawings, how many rooms have a ceramic tile base (B2)? | 1 | 1 | 89431 |
| Count / Rooms filtered by finish | On sheet A-801 of the Xcel Sports Complex drawings, how many rooms have all four walls finished with W1 (painted gypsum board)? | 1 | 1 | 89432 |
| Count / Sinks and washbasins | On sheet A-701 (Restrooms) of the Xcel Sports Complex drawings, how many lavatories are drawn inside the two restrooms of enlarged plan 6A? | 1 | 1 | 89439 |
| Count / Toilet bowls and WC fixtures | On sheet A-701 (Restrooms) of the Xcel Sports Complex drawings, how many water closets are drawn in enlarged plan 6A 'Restrooms'? | 1 | 1 | 89438 |
| Count / Windows | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many 2-wide window assemblies (types SS, TT and UU) are scheduled? | 1 | 1 | 89458 |
| Count / Windows | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many windows (window assemblies) are listed in the window schedule in total? | 1 | 1 | 89453 |
| Count / Windows | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many windows of type QQ (1-WIDE (TEMP ALL) ESDH3066) are scheduled? | 1 | 1 | 89456 |
| Count / Windows | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many windows of type RR (1-WIDE (TEMP LOWER) ESDH3066) are scheduled? | 1 | 1 | 89455 |
| Count / Windows | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many windows of type SS (2-WIDE (TEMP ALL LOW) ESDH3066) are scheduled? | 1 | 1 | 89454 |
| Count / Windows | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), how many windows of type VV (3-WIDE (TEMP ALL LOW) ESDH3066) are scheduled? | 1 | 1 | 89457 |
| Derived / Window-unit count from assembly multiplicities | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), if every N-wide window assembly consists of N ESDH3066 window units, how many ESDH3066 units are needed in total? | 1 | 1 | 89459 |
| Property / Ceiling materials or systems | On sheet A-801 of the Xcel Sports Complex drawings, what is the ceiling finish of the Fieldhouse (room 128)? | 1 | 1 | 89435 |
| Property / Door fire ratings or rating availability | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), what fire rating is scheduled for the unit doors (type U01)? | 1 | 1 | 89450 |
| Property / Door hardware group | On sheet A-801 of the Xcel Sports Complex drawings, which hardware group is specified for door 107.A? | 1 | 1 | 89417 |
| Property / Door or frame material | On sheet A-801 of the Xcel Sports Complex drawings, what door material is specified for door 115.A? | 1 | 1 | 89418 |
| Property / Door or frame material | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), what frame material is scheduled for the unit doors (type U01)? | 1 | 1 | 89451 |
| Property / Door type and description | On sheet A-801 of the Xcel Sports Complex drawings, what door type is door 121.A, and what kind of door is that? | 1 | 1 | 89415 |
| Property / Door width or dimensions | On sheet A-801 of the Xcel Sports Complex drawings, what are the width and height of door 128.B? | 1 | 1 | 89416 |
| Property / Door width or dimensions | On sheet A-801 of the Xcel Sports Complex drawings, what is the height of the four doors of type B2 that serve the Fitness Center (118.A1-118.B2)? | 1 | 1 | 89419 |
| Property / Door width or dimensions | On sheet A-801 of the Xcel Sports Complex drawings, what is the width of door 121.A? | 1 | 1 | 89414 |
| Property / Room wall or floor finishes | On sheet A-801 of the Xcel Sports Complex drawings, what floor finishes are scheduled for the Fieldhouse (room 128)? | 1 | 1 | 89434 |
| Property / Room wall or floor finishes | On sheet A-801 of the Xcel Sports Complex drawings, what is the floor finish of room 113 (Aerobics &amp; Yoga), and what does it mean? | 1 | 1 | 89433 |
| Property / Room wall or floor finishes | On sheet A-801 of the Xcel Sports Complex drawings, what is the north wall finish of the Fitness Center (room 118)? | 1 | 1 | 89436 |
| Property / Window height or dimensions | On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), what are the width and height of a window unit in the window schedule? | 1 | 1 | 89460 |
| Ranking / Largest room or rooms by area | On sheet A-801 of the Xcel Sports Complex drawings, which room in the finish room schedule has the largest area? | 1 | 1 | 89437 |

</details>

## Provenance and reproduction

- Input: the full `dataset/junction-dataset/questions.jsonl`, not the preview and not previously aggregated audits.
- SHA-256 of the exact input bytes: `0e6322c74561a63f42bac35f5c1be8a2c6a37516b14a81e66ab88b74950a6d1f`.
- Parsed records: **127,044**. Blank lines skipped: **0**. Unclassified rows: **0**.
- Classification uses reviewed multilingual templates plus an explicit text-to-family taxonomy for all 701 distinct IFC-Bench questions, 24 CubiCasa questions, and 64 Opening Design questions. These semantic assignments were reviewed during this analysis; running the generator uses no LLM/API calls, sampling, or reference-answer inference.
- The generator rejects unknown questions/labels/sources and checks coverage and reconciled totals. A changed corpus may require taxonomy review before regeneration.

Run from the repository root:

```sh
python scripts/classify_questions.py --report-date 2026-11-14
python scripts/classify_questions.py --report-date 2026-11-14 --check
# Optional: export every source row with its family (analysis data, no answers).
python scripts/classify_questions.py --rows-out /tmp/junction-question-classification.jsonl
python scripts/check_docs.py
```

On Windows, replace `/tmp/junction-question-classification.jsonl` with a writable local path.

Sources: [classifier](../scripts/classify_questions.py), [reviewed taxonomy](../scripts/question_classification_taxonomy.json), [dataset question file](../dataset/junction-dataset/questions.jsonl), [dataset README](../dataset/junction-dataset/README.md), [full dataset findings](../dataset/FULL_DATASET_FINDINGS.md), and [project scope](PROJECT_SCOPE.md).
