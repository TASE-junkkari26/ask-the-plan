# 250-question development run

**15 November 2026 | revision `7904dbd` | seed `20261115`**

All **250 selected questions** produced recorded outcomes. Numeric outputs agreed with the supplied references on **135/214 numeric questions (63.1%)**. The stricter exact-numeric and evidence-structure check passed **19/214**. The remaining **36 text questions require human grading**.

The sample spans 83 semantic families and 207 original assets. Fixed category allocations and family cycling give smaller categories more coverage than their share of the dataset. These results describe this development sample.

## Results by source category

| Category | Questions | Answered | Partial | Non-answer | Numeric agreement | Strict passes | Text ungraded |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CubiCasa PNG | 75 | 0 | 66 | 9 | 55/75 | 0 | 0 |
| Swiss PDF | 75 | 1 | 59 | 15 | 51/75 | 0 | 0 |
| IFC-derived floor PDF | 25 | 2 | 10 | 13 | 3/25 | 0 | 0 |
| Opening Design PDF | 25 | 11 | 4 | 10 | 2/14 | 0 | 11 |
| Quantitative IFC | 25 | 25 | 0 | 0 | 24/25 | 19 | 0 |
| IFC-Bench | 25 | 6 | 1 | 18 | Ungraded | Ungraded | 25 |
| **Total** | **250** | **45** | **140** | **65** | **135/214** | **19** | **36** |

Numeric denominators retain every selected numeric question, including non-answers. Count matching requires exact equality. Area, length and volume matching uses compatible units/dimensions and 2% relative tolerance. Partial and estimated visual results can contribute numeric agreement. Strict passes additionally require an answered exact claim and passing evidence structure.

`Answered` and `Partial` are case-level runtime outcomes. Compound cases with a successful part and an unresolved part appear under Partial. The 65 non-answers comprise 29 clarification requests, 21 unsupported operations, 12 incomplete-coverage outcomes and three missing-information outcomes. **HTTP/import errors were zero.** The scorer's CSV outcome `failed` refers to those 12 incomplete-coverage cases.

## Results by question type

| Type | Selected | Numeric agreement | Strict passes |
| --- | ---: | ---: | ---: |
| area | 30 | 5/30 | 0 |
| count | 178 | 130/178 | 19 |
| length | 2 | 0/2 | 0 |
| text | 36 | Human grading required | Ungraded |
| volume | 4 | 0/4 | 0 |

## Observed limitations

- All 19 strict passes are IFC counts. Five IFC net-area answers matched the reference numbers while their quantity basis remained unresolved under the strict scorer.
- One IFC stair count returned an exact zero against a reference of one. Source inspection found one `IfcStair` and one `IfcStairFlight` in `bsc-clinic_clinic-structural.ifc`. The saved plan selected `concept:stair` with `entity_kinds=["element"]`. Case Q206 retains this failure.
- Floor-plan measurements and several schedule/lookup questions returned unsupported or clarification outcomes. IFC-derived floor PDFs had 3/25 numeric agreement in this sample.
- Automatic evidence checks cover hashes, question/scope bindings, calculation references and structural consistency. Correct source localization, object membership and descriptive answers require human review.

## Runtime, calls and concurrency

The question execution window was **17.9 minutes**, including the concurrency handoff and source imports after the first question began. Input selection/rendering and the first source import precede that window. Median recorded question time was **10.4 s**, excluding each source's cold import. Timing combines two concurrency phases.

Phase 1 saved 218 outcomes using three drawing workers and one serialized IFC worker. At the user's request, phase 2 processed the remaining 32 drawing questions using up to eight drawing workers and finished in 40.2 s. Questions on the same registered source retain their order. All IFC questions had completed before phase 2. Production runtime files were identical across phases.

**Three in-flight questions (Q168, Q170 and Q171) were interrupted at the handoff and retried. Prior usage for those attempts is unknown.** Completed predictions were reused. The saved final responses report **424 external attempts**, a lower bound on total attempted/billed work. One saved Nemotron call also lacks token usage.

| Model | Recorded calls | Reported input tokens | Reported output tokens |
| --- | ---: | ---: | ---: |
| `gemini-4-hydrogen` | 331 | 860,271 | 267,400 |
| `nemotron-3.5-super-vl` | 93 | 4,129,206 | 34,489 |

The repository's 14 November Gemini tariff gives **$3.2959** for the 331 recorded Hydrogen calls, before cache discounts, credits and taxes. Nemotron has 93 recorded calls with no configured tariff. Total billed spend remains unknown, including the interrupted attempts.

Images used the configured Gemini Hydrogen-low analyzer with routing off. Nemotron planned IFC and native PDF operations. Native IFC grammar and PDF tools could finish with zero external calls. Original IFC parsing and query execution ran locally.

## Reproducibility and artifacts

Execution used production source-registration and common-answer routes through in-process ASGI HTTP transport, with live external model services. Windows, Python 3.14.10, Node 24.22.3, IfcOpenShell 0.9.0.post1 and PDF.js 5.5.207 were installed. PDFs used their first page with preserved native rotation, viewport transform and the frontend's raster limits.

The frozen manifest binds original question lines, wording, source hashes and allocation. Display PNG hashes and rendering metadata are additionally recorded in the local runtime artifact. Scoring opened references only after all 250 final predictions were saved. Original drawing files and reference answers retain their supplied contents.

- [Frozen input-only sample](../review_250_sample.json)
- [Per-case outcomes](results.csv)
- [Machine-readable summary](../review_250_summary.json)
- [Runner and reproduction instructions](README.md)

Full compressed answers, source/evidence bundles, runtime code hashes, phase records and interrupted-attempt markers remain in ignored `build/review-250-20261115/`. The tracked artifacts contain aggregate results and input provenance. Source assets retain the supplied CubiCasa5K, Swiss Dwellings/Archilyse, OpeningDesign and per-model IFC licenses.

Sample manifest SHA-256 `715a2010fb48906cdaac244d761631ae0c160ceaac794a649ec0b960df3c4dc7`.
