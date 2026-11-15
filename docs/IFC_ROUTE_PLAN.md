# Source-backed IFC modeled walking routes

Implemented and checked on 15 November 2026. This replaces the earlier proposal;
certified evacuation compliance and physical clear passage width remain source
limitations rather than inferred facts.

## Supplied requirements

| Full question line | Source | Requirement |
| --- | --- | --- |
| 85618 | `dental_clinic_arc.ifc` | Estimated route from treatment room `1E12` to the nearest emergency exit, including its path. |
| 85619 | `dental_clinic_arc.ifc` | Estimated route from `1E23` to the nearest emergency exit, including its path. |
| 85770 | `duplex_arc.ifc` | Distance from the farthest point to the nearest emergency exit. |
| 85772 | `duplex_arc.ifc` | Emergency escape-route width. |

Both models contain room bodies, door boundaries and VIRTUAL space-boundary
surfaces. Neither has a stored evacuation-path annotation, stored route length
or actual clear-width inventory. The property named `IsFireExit` is a literal
`IfcLabel('IsFireExit')` in Revit metadata, not a typed boolean certification.
Recorded physical exterior-door boundaries establish potential outdoor targets.
If `target_basis=certified_fire_exit` has any eligible typed true targets, only
those are routed. If none exists, a qualified recorded-outdoor fallback can be
returned with `certification_requested_unavailable=true`; it never becomes a
certified-exit answer.

## Implemented operation and method

`route_query` selects native `IfcSpace` origins and can reference a prior target
door selection. `mode=shortest` starts at an exported deterministic interior
point or an explicit physical start point. `mode=farthest` requires
`start_basis=farthest_sampled`; it samples the selected room regions, minimizes
each sample's modeled distance to the candidate exits, then retains the largest.
The sampling scale and unreachable rooms accompany that estimate. A sampled
maximum is not an exact continuous-domain maximum.

The CPU worker uses validated room footprint polygons with concavity and holes,
source filled-opening geometry to bridge wall thickness, matched VIRTUAL passage
patches, and native straight stair walking lines. One shared visibility graph per
room supplies feasible polygon paths; weighted shortest-path search connects
those paths through physical portals. It never substitutes a room-centroid
distance, a shared wall alone, or an invented vertical line for a walking route.
Every exported segment is checked in its modeled room/opening/stair region,
and the executor recomputes the reported distance from the exported coordinates.

VIRTUAL patches must have coincident support and rooms on opposite interior
sides. Patch frames are checked against the owning room body. The supplied
duplex contains exporter coordinate inconsistencies: for example, applying
`A201`'s full placement moves a patch outside its own room. The source XY-world /
Z-relative interpretation is retained only when actual room-boundary support
verifies it; distinct equally supported frames remain unresolved. Source loops
with equal normals can be accepted only when the actual room interiors prove
opposite sides.

Stairs require a native walking line, source rise data consistent with the body,
and lower/upper endpoints supported by room footprints and physical floors. The
source `Pset_StairFlightCommon` riser dimensions in the duplex agree with its mesh
and floor levels, while the native scalar attributes disagree. Both remain in
the proof; the verified source property basis is stated. Length along a stair's
pitch line is an approximation, not a tread-by-tread pedestrian distance.

Work is bounded to 500 rooms, 1,000 doors, 64 stair flights, 2,000 portal samples,
8,000 visibility nodes, 50,000 edges, 128 reflex/hole vertices per room, 3,000
farthest samples and a ten-second isolated worker deadline. Source hashes,
authorized native inventories and settings bind successful cached proofs; failed
attempts do not establish permanent absence. Hidden required objects remain
incomplete coverage. Path highlighting uses route objects, while full graph
inventory anchors remain in calculation evidence.

## Source predictions and evidence

Predictions were saved before examining reference values. On the reported Linux /
Python 3.14 / IfcOpenShell 0.9 environment, one native clinic batch took about
4.4 seconds. Starting at the exported modeled interior points produced:

| Origin | Ordered modeled room path | Estimated length |
| --- | --- | ---: |
| `1E12` | `1E12`, `1E33`, `1DC6`, `1EC3`, `1EC1`, `1EC4` | 18.2045 m |
| `1E23` | `1E23`, `1EC1`, `1EC4` | 8.1573 m |

The paths end at the modeled exterior opening associated with native door
`#1890`; their 13 and 7 physical points are exported. An engine integration check
validated the full result proof, not just a textual room sequence. The clinic
has six source exterior classifications without a recorded exterior room
boundary; those are unresolved candidates. Its stacked stair/landing connectors
are also unresolved by this initial straight-flight method. The two checked
first-floor paths use no stairs.

In the duplex, the modeled upper-room route from `A203` traversed native flight
`#5984` and reached `A101`'s exterior door, measuring 16.2038 m. A bounded sampled
whole-room-domain search found a 19.6452 m known path from `B203`, through `B201`
and a native stair to `B101`. The source roof room `R301` has no recorded supported
connector and remains unresolved, so that is a known sampled route estimate,
not a complete whole-building maximum. Scope changes after a warm cache cannot
reuse a hidden opening.

## Width and qualification

The table separates nominal authored door width, modeled gross opening-contact
width and unavailable actual clear width. These have different meanings: room
contact geometry can be narrower than the rough opening, and frames, hardware,
leaf state, locks and obstructions can reduce physical passage. A route-specific
nominal bottleneck can be reported with its source inputs, but cannot be relabeled
as certified emergency escape width. An unspecified route is not assigned the
smallest door anywhere in the building.

Current route rows remain partial estimated potential paths. Strict
`RouteEvaluation` evidence includes source/placement/representation/rise/unit
anchors, ordered objects, source/scope hashes, path points, segment lengths,
portal checks, sampling parameters and unresolved inputs. The absent certification
and clear-width data must remain visible in any natural-language answer.

Further work within the known family is supported landing-to-flight integration
for the clinic's stacked flights, improved farthest-point refinement with a
rigorous geometric coverage bound, and fixed-obstacle/door-clearance geometry
when the source records enough data. These are not advertised as implemented.
