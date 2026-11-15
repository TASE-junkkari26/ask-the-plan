# IFC source size, native networks and measurement findings

Investigation on 14 November 2026. These are CPU source inspections and bounded
extraction profiles, separate from natural-language planner accuracy and live API
tests. Original IFCs and supplied questions/reference answers were not modified.

## Eager extraction exceeds a practical memory budget

The supplied `sixty5_plumbing.ifc` is about 212 MiB and contains 70,182
`IfcProduct` records. In an isolated Linux process, native IfcOpenShell parsing
took 5.73 seconds and reached 1,278 MiB peak resident memory. The previous eager
property extraction then reached 300,000 emitted facts in 39.69 seconds at
2,871 MiB peak RSS, after processing only 8,916 source objects. The deliberate
memory guard stopped the profile; this was not a successful full-model extraction.

The process had a 4 GiB address-space limit, a 2,800 MiB sampled RSS guard,
120-second CPU limit and 150-second wall limit. The RSS guard was sampled every
25,000 facts, explaining the small overshoot. It protected the main application
process from the experiment. The ignored local artifacts were
`/tmp/ifc_extraction_profile.py` and
`/tmp/ifc-plumbing-extraction-profile.log`.

At the stop point, `ApplicationFullName`, `ApplicationIdentifier` and `Version`
had each been repeated 8,916 times. Removing this duplication helps, but those
26,748 facts were only about 9% of the emitted facts. Repeated occurrence/type
property sets remain the larger cost. A larger upload cap alone cannot solve
this memory growth.

The resulting implementation uses a lean initial index for files of at least
32 MiB: canonical source objects and labels, native relationships, class facts,
units and a complete property vocabulary. Scalar/property values and derived
context/material facts are hydrated from the retained immutable source only
when requested. Merely listing a property key does not establish that a given
object has a value for it.

`NativeHydrator` preserves occurrence overrides, inherited values, explicit
nulls, unsupported structures, source units, and eager fact/anchor identities.
It marks an absent value only after inspecting that exact entity/property pair.
Requests are bounded to 200,000 inspected pairs and 200,000 hydrated facts per
question. A failed batch commits no checked-pair state, preventing a later read
from mistaking an interrupted inspection for source absence. Property state is
reset between questions after the preceding response captures its evidence;
native source indexes remain reusable. Source hashes are checked again when a
new question first needs hydration.

The same plumbing file subsequently completed a lean engine/query profile under
the unchanged 4 GiB address-space and sampled 2,800 MiB RSS guards:

| Phase | Elapsed from process start | Peak RSS |
| --- | ---: | ---: |
| Native parse | 5.77 s | 1,280 MiB |
| Lean engine ready | 61.47 s | 2,648 MiB |
| Structured plan validated | 61.96 s | 2,672 MiB |
| Native network query answered | 65.35 s | 2,722 MiB |
| Result/evidence validated | 66.33 s | 2,722 MiB |
| Result serialized | 66.46 s | 2,729 MiB |

The ready engine contained 71,991 entities/class facts, 288,147 anchors and
189,300 native relations. The query used all 47,458 distribution ports and a
separately selected 22,594 distribution components. Its values matched the
independent native source probe below. The serialized `QueryResult` was
25,436,249 bytes, so source evidence is substantial even without inference.
The child exited successfully. Local artifacts were
`/tmp/ifc-plumbing-lean-network-profile.log` and
`/tmp/ifc-lean-network-profile-result.json`.

This is evidence that the lean path can execute a real large network within the
tested bound. It does not establish acceptable latency on every device, arbitrary
property hydration at this scale, or a browser round trip.

## Large-source API and cleanup check

An additional offline ASGI integration check streamed the original plumbing file
through the actual upload/question/delete routes. It used one fixed structured
network proposal adapter, **zero external inference calls**, and the normal
catalog, scope validation, native executor and response/evidence assembly. The
question selected the entire source deliberately. It retained a 4 GiB
address-space cap, with a 3,300 MiB RSS guard to allow the independently measured
API indexing/response overhead, plus 180 CPU and 210 wall seconds.

| Phase | Elapsed from process start | Peak RSS / result |
| --- | ---: | --- |
| Lean engine ready | 65.49 s | 2,729 MiB |
| Upload complete | 71.42 s | 2,908 MiB; HTTP 200 |
| Fixed proposal adapter invoked | 75.27 s | 2,954 MiB; 94,920-character bounded payload |
| Question response complete | 80.15 s | 3,151 MiB; HTTP 200, `answered` |
| Source session deleted | 81.65 s | HTTP 204 |
| Response parsed and source metrics verified | 82.19 s | 3,151 MiB peak |

The process exited normally with status zero, including native-session cleanup
and asyncio shutdown. This confirms that the API can answer the real 212 MiB
network source with the source-backed counts below, without eager millions of
property facts. It does not establish live natural-language interpretation,
browser rendering, repeated-query property hydration at this scale, or a
low-memory-device guarantee. Local artifacts are
`/tmp/ifc-network-api-profile-escalated.log` and
`/tmp/ifc-network-api-profile-summary.json`.

The uncompressed full response was 89,430,980 bytes. Its major fields were:

| Field | Approximate compact JSON size |
| --- | ---: |
| Original native anchors | 44.42 MB |
| Query result, calculations, claims and entity sets | 25.44 MB |
| Included source-element identities | 12.74 MB |
| Coverage, including source anchor references | 6.83 MB |

The native graph needs source identities and relationship anchors rather than
hydrated scalar property facts. The result itself repeats about 6.83 MB of
network anchor references in both the calculation and claim binding, while
selection outputs and entity sets also retain inventory references. Lossless
HTTP compression can reduce transfer size; reducing the proof itself requires a
separate audit of DAG references and persisted source inventories. Neither
truncating matched objects nor dropping anchors silently would be an adequate
performance fix.

Earlier restricted-sandbox runs completed the upload and question but stalled
during asyncio runner shutdown. A five-second faulthandler probe located the
stall in `asyncio.runners.Runner.close` / `selectors.select`, after the app
lifespan had already closed. The identical tiny offline lifecycle probe exited
normally outside that restriction. The successful large-source profile above
therefore used ordinary escalated local thread access. No application shutdown
workaround or extra inference was introduced. Owned retained source files were
removed; shutdown-timeout runs are not described as passing lifecycle checks.

## Recorded distribution-network metrics

The probes below used native `IfcDistributionPort`, `IfcRelConnectsPorts`,
`IfcRelConnectsPortToElement` and port-owner `IfcRelNests` records directly.
Connections are distinct undirected port pairs; duplicate or reverse records
count once. A connected port is an endpoint of at least one such recorded pair.
These computations did not read reference answers. References were compared
after the source results were obtained.

| Native source metric | Plumbing | Ventilation |
| --- | ---: | ---: |
| Distribution ports | 47,458 | 25,434 |
| Connected distinct ports | 45,184 | 21,624 |
| Distinct undirected port connections | 22,592 | 10,812 |
| Connected-port percentage | 95.2083948% | 85.0200519% |
| `IfcDistributionElement` occurrences | 22,594 | 11,825 |
| Additional `IfcBuildingElementProxy` occurrences | Not used in this denominator | 123 |
| Distinct recorded component owners | 22,485 | 11,729 |
| Ports with a recorded owner | 47,458 | 25,434 |
| Port-graph connected components | 24,866 | 14,622 |
| Largest port component | 2 ports | 2 ports |
| Parse plus native graph computation | 5.96 seconds | 2.97 seconds |

The port-only graph has mostly separate pairs because internal flow between
ports of one owning component is not a native port-to-port connection. The
separate owner graph links component occurrences only when a recorded port pair
connects their owners; it does not assume every port of a component permits
internal flow.

The plumbing reference at question line 86261 gives 45,180 connected ports,
four fewer than the exhaustive native source count above. The ventilation
reference at line 86292 gives 21,618, six fewer than the source count. Their
rounded percentages agree. These discrepancies must not be hidden by changing
the executor to reproduce reference numbers.

Component denominators also need a deliberate definition. In ventilation,
11,825 distribution elements plus 123 proxies produce the reference's 11,948
HVAC components. Of those proxies, 108 own distribution ports; selecting only
owners would also omit portless hardware. The runtime `network_query` therefore
accepts a separately selected physical-component set. With no such set it states
that its denominator is the distinct recorded owners of the selected ports.
The plumbing source gives 47,458 / 22,594 = approximately 2.10047 ports per
selected distribution component.

Required owners and connection endpoints must stay inside the captured scope.
An in-scope peer excluded by a deliberate network filter is a reported cut
connection and is excluded from that induced graph's rate. A hidden endpoint
instead produces incomplete coverage. No recorded ports means a recorded count
of zero and an undefined connectivity ratio, never zero percent or proof that
the physical building has no network.

## Town measurements require explicit geometric meaning

The town question about highest ground elevation (line 85825) can use native
`IfcBuilding.ElevationOfTerrain`: both `Kirche` and `Kapelle` store 190 m.
Object-placement Z is not a valid substitute; several town buildings share
placement Z of zero or -169 despite different recorded terrain elevations.
`ElevationOfTerrain` and `ElevationOfRefHeight` are now retained as length
attributes. A cardinal location description still requires an established
orientation; world-axis position alone does not establish north or south.

The defensive-wall question (line 85836) illustrates why a world bounding height
is not a standing wall height. Native meshes have the following world-Z extents:

| Object | Maximum minus minimum mesh Z |
| --- | ---: |
| `Mauer-Innen` | 24 m |
| `Mauer-Mitte` | 21 m |
| `Mauer-Aussen` | Approximately 24.688 m |

The terrain varies along these long objects. Matching source vertices at the
same XY coordinate instead showed local vertical spans of about 2–3 m, 3 m and
0.8 m respectively. This diagnostic is not a complete certified standing-height
measurement; the inner wall's reference of 6 m remains unverified. The explicit
`height` measurement basis `world_z_extent` reports what it measures and must not
be presented as a solution to this different local-height question.

For the nearest-gate question (line 85838), the minimum separation between XY
mesh projections of `Spital-Kirche` and `Unterer-Torturm` was 47.808 m, the
smallest among the six named gate/tower objects. The next, `Unteres-Tor`, was
70.145 m. The reference estimates about 70 m to `Unterer-Torturm`, without a
measurement basis. A gate-center estimate, closest physical surfaces and a
walkable route can differ. The runtime horizontal-distance operation keeps the
selected basis, source objects and nearest XY points in its evidence; it does
not tune the result to the reference or call it an escape route.

The three wall mesh checks took 0.91 seconds; the six gate-reference checks took
2.80 seconds in a single native batch. They are selected source probes, not
dataset-wide geometry coverage or target-device latency guarantees.

See [the engine guide](IFC_ENGINE.md) for implemented operation meanings and
[the IFC question guide](IFC_QUESTIONS.md) for current API and scope behavior.

## Room footprint basis, cached measurements and town enclosure

Checked on 15 November 2026. The duplex `A102` room body has projected footprint
27.660089 m²; its ten Level 1 rooms sum to 126.340954 m², with the same footprint
union to numerical precision. Authored Revit area is instead 30.14164525 m² for
`A102` and 141.790615 m² for that level. Those source values use a different
boundary convention and must not be silently relabeled as the exported room
footprint. The runtime retains that distinction and reports mesh-derived areas
as estimated quantities. A bounded batch measured all 269 clinic room footprints
in 1.79 seconds; a repeated single room reused its numeric record in 0.0077 s.
Meshes are discarded, and authorized-room prefetch never includes hidden rooms.

For the town enclosure, the inner wall alone is disconnected and its narrow
footprint has no meaningful interior region. Jointly adding the six explicitly
selected gate/tower source footprints closes one inner-wall-supported projected
region of 58,464.97919038182 m². The engine proof retained 269 boundary coordinates,
320 source inputs, 987 representation IDs and 1,037.6577 m of genuine inner-wall
boundary support. Three closure footprints contribute to that region; closure-only
courtyards are excluded, and a 1.287e-5 m² tolerance sliver was rejected. No buffers,
convex hulls or invented gap closures enter this calculation. Real extraction
took 7.31 s and the query 4.03 s; result validation passed. The prediction was
saved before reference inspection and differs by about 0.95% from the supplied
approximate 59,027 m² figure; inner-face versus centerline/manual boundary is a
material basis difference, not a reason to tune the runtime value.

Modeled route source predictions and their remaining certification/clear-width
qualifications are documented in [the route findings](IFC_ROUTE_PLAN.md).
