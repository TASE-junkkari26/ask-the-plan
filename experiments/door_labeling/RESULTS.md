# First door-labeling result

Run reviewed on 14 November 2026 (Europe/Helsinki). The API integration was
committed first as `ab470cf`; the experiment code and this report were added
afterward. This is a single development example, not an independent benchmark.

## Method

- Source: `data/cubicasa5k/colorful-10052.png` in the full challenge dataset.
- Input: the original 2730 by 2048 PNG, uploaded without resizing or cropping.
- Model: the configured Verda `nemotron-3.5-super-vl` deployment.
- One request; temperature 0; thinking disabled; max output 4096 tokens; no retries.
- The [prompt](prompt.txt) asks for door instances with whole-image normalized
  boxes, door kind, an uncertainty flag, and a short visual cue.
- The reference answer was read only after saving the model's output.
- Coordinates were validated and mapped to original pixels for the overlay.
  The displayed count is the length of the returned instance list.

## Observed result

| Measurement | Result |
|---|---|
| Returned door instances | 5 |
| Supplied reference count | 5; count matches |
| Inference elapsed time | 1775 ms |
| Prompt / completion tokens | 4009 / 459 |
| Total tokens | 4468 |
| Reasoning tokens | 0 |
| Nominal API-equivalent cost | USD 0.00083085 at the reference tariff below |
| Effective project cost | USD 0, as reported by the owner |
| Output schema | Passed coordinate-range, positive-area, unique-ID and JSON checks |
| Visual location review | All five proposals point to visible doors; no additional doors or false-positive locations observed in this review |

These tokens include the image and schema instructions. One timing observation
does not establish typical latency.

The reference tariff is Together's listing on [OpenRouter's model page](https://openrouter.ai/nvidia/nemotron-3.5-super-vl),
checked 14 November 2026: USD 0.15 per million uncached input tokens and USD 0.50
per million output tokens. Calculation:

```text
4009 / 1,000,000 * $0.15 = $0.00060135 input
 459 / 1,000,000 * $0.50 = $0.00022950 output
                         $0.00083085 total
```

This is about USD 0.83 for 1,000 requests with the same token usage. No published
per-token tariff for the custom Verda deployment was found, so this is explicitly
an API-equivalent comparison from another provider. It does not estimate GPU
hardware cost or establish a Verda invoice. The effective project cost is zero
under the owner's reported free access; billing was not independently checked.

## Visual review

This review was performed by the assistant by inspecting the full overlay and
individual context crops. It is not independent human annotation or an IoU-based
box benchmark. Raw predictions were preserved without modification.

| ID | Location | Finding |
|---|---|---|
| D1 | Left-side double-leaf opening | One logical instance correctly located; box covers both leaves/arcs. **Kind is wrong:** predicted `single_swing`, visually `double_swing`. |
| D2 | Upper-right internal door | Correct location; a usable visual box. The room description is not validated. |
| D3 | Diagonal internal door | Correct location; box clips the upper extent of the leaf/symbol and needs expansion. |
| D4 | Lower-right internal door | Correct location; box clips part of the swing at its left/bottom edges and needs expansion. |
| D5 | Bottom entrance | Correct location; box slightly clips the top/bottom symbol extent and needs expansion. |

The model set `uncertain=false` for every proposal despite those errors. That flag
must not be treated as a calibrated quality score or automatic approval signal.
The plan's decorative/open gaps were not returned as additional doors.

## Saved artifacts

The [checked-in example run](../runs/door-labeling/20261113T234605960384Z/README.md) is
`experiments/runs/door-labeling/20261113T234605960384Z/` (UTC run ID;
the local date was 14 November). It contains the input image, attribution/licence,
exact request/schema/settings, runner and source hashes, response, predictions,
annotated PNG, crop sheet, count comparison, summary and separate visual review.
This one example is tracked in Git; all future runs remain ignored. Cost reporting
was added afterward using the saved token usage, without a new inference request.
The original request, response and predictions remain unchanged, and a runner
source snapshot preserves the exact code matching the recorded hash. Rerun the
command in [the guide](README.md) to generate another timestamped run.

Source credit: CubiCasa5K, (c) 2019 CubiCasa. Ahti Kalervo, Juha Ylioinas,
Markus Haikio, Antti Karhu, Juho Kannala, SCIA 2019. CC BY-NC-SA 4.0.
The overlay and crops are adaptations for the non-commercial challenge and retain
the source attribution. Original distributed files were left unchanged.

## Implication

This clean example supports trying Nemotron as an annotation proposal generator.
It recovered every visible door location and the correct logical count in one
request, while box extents and one subtype still needed review. Use corrected
instances for training and evaluate on more varied, fully reviewed plans before
scaling to overnight labeling. The next comparison should check whether localized
crop refinement improves box extents and double-leaf classification while keeping
the original predictions and human/assistant corrections separate.
