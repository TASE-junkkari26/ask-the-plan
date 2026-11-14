"""Callable region/detail tools. The caller chooses the tool, not a router."""
from __future__ import annotations

import asyncio
import re
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.models import AnalysisCall, ImageCandidateResponse, ImageRegionResponse
from .errors import ApiError
from .images import PreparedImage
from .reconciliation import (SourceCandidate, reconcile_candidates, propose_reinspection_regions,
                             apply_reinspection, partition_tile_observations)
from .region_proposal import GeminiRegionProposer
from .region_tools import crop_region, optimized_tile_regions, validate_source_box
from .candidate_verification import GeminiCandidateVerifier
from .window_regions import propose_window_regions, find_solid_window_boxes


_WINDOW_COUNT = re.compile(
    r"^(?:how\s+many\s+windows|kuinka\s+monta\s+ikkunaa|montako\s+ikkunaa|"
    r"wie\s+viele\s+fenster|combien\s+de\s+fenêtres|quante\s+finestre|"
    r"hur\s+många\s+fönster|hvor\s+mange\s+vinduer|hoeveel\s+ramen)\b", re.IGNORECASE)


def _window_task(question, target_kind):
    return target_kind == "window" or target_kind == "other" and bool(_WINDOW_COUNT.match(question.strip()))


class DetailOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    mode: Literal["auto", "regions", "tiles"] = "auto"
    regions: list[tuple[Annotated[int, Field(strict=True)], Annotated[int, Field(strict=True)],
                        Annotated[int, Field(strict=True)], Annotated[int, Field(strict=True)]]] = Field(default_factory=list, max_length=4)
    tile_size: Annotated[int, Field(ge=128, le=2400, strict=True)] = 1400
    overlap: Annotated[int, Field(ge=32, le=480, strict=True)] = 200
    max_calls: Annotated[int, Field(ge=1, le=12, strict=True)] = 9
    reinspect_edges: bool = True
    target_kind: Literal["door", "window", "toilet", "shower", "bathtub", "bath_fixture", "room", "floor", "schedule_row", "other"] | None = None
    verify_membership: bool = True
    opencv_windows: Annotated[bool, Field(strict=True)] = False
    opencv_window_checks: Annotated[bool, Field(strict=True)] = True

    @model_validator(mode="after")
    def check_options(self):
        if self.mode == "regions" and not self.regions:
            raise ValueError("regions mode requires explicit source-pixel regions")
        if self.mode == "auto" and self.regions:
            raise ValueError("auto mode does not accept explicit regions")
        if self.overlap >= self.tile_size / 2:
            raise ValueError("overlap must be less than half tile size")
        return self


def _image_metadata(image):
    return {"sha256": image.sha256, "inference_sha256": image.inference_sha256,
            "width": image.width, "height": image.height}


def _total_usage(stages, field):
    values = [getattr(stage, field) for stage in stages]
    return sum(values) if values and all(v is not None for v in values) else None


async def _local_work(function, *args, **kwargs):
    # Crop workers must finish before the caller removes their source/temp dir.
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await task
        raise


async def _provider_call(operation, *, client, image, source_box, call_id, purpose, on_call):
    """Record the actual input/model/usage, including failed and cancelled attempts."""
    started = perf_counter()
    result = error = None
    outcome = "completed"
    try:
        result = await operation()
        return result
    except BaseException as exc:
        error = exc
        outcome = "cancelled" if isinstance(exc, asyncio.CancelledError) else "failed"
        raise
    finally:
        if on_call is not None:
            usage = getattr(result, "metrics", result) if result is not None else getattr(error, "usage", None)
            provenance = getattr(result, "provenance", result)
            returned_model = getattr(provenance, "returned_model", None) if result is not None else getattr(error, "returned_model", None)
            on_call(AnalysisCall(id=call_id, purpose=purpose,
                requested_model=client.settings.model, returned_model=returned_model,
                completed_at=datetime.now(timezone.utc).isoformat(), outcome=outcome,
                elapsed_ms=max(0, (perf_counter()-started)*1000),
                input_sha256=image.inference_sha256, input_width=image.model_width,
                input_height=image.model_height, source_box=list(source_box),
                prompt_tokens=getattr(usage, "prompt_tokens", None),
                completion_tokens=getattr(usage, "completion_tokens", None)))


class DetailTools:
    """Bounded operations usable directly by the decision-system implementer.

    Call propose_regions separately, or extract with an explicitly selected mode.
    Native source PNG and caller-owned temporary directory are required.
    """

    def __init__(self, candidate_service, gemini_client, preprocessor=None, *, slots=None):
        self.candidate_service = candidate_service
        self.proposer = GeminiRegionProposer(gemini_client)
        self._slots = slots if slots is not None else asyncio.Semaphore(2)
        self.preprocessor = preprocessor
        self.detector_client = getattr(getattr(candidate_service, "provider", None), "client", gemini_client)
        self.verifier = GeminiCandidateVerifier(self.detector_client)

    async def propose_regions(self, image, question, request_id, *, on_call=None):
        layout_image, hint = image, None
        if self.preprocessor is not None:
            layout_image, hint = await _local_work(self.preprocessor.detail_context, image, image.path.parent)
        async with self._slots:
            proposal = await _provider_call(
                lambda: self.proposer.propose(layout_image, question, layout_hint=hint),
                client=self.proposer.client, image=layout_image,
                source_box=(0, 0, image.width, image.height),
                call_id="region-proposal-call", purpose="region_proposal", on_call=on_call)
        return ImageRegionResponse.model_validate({
            "request_id": request_id, "image": _image_metadata(image),
            "status": proposal.status, "target_kind": proposal.target_kind,
            "regions": [{"id": r.id, "source_box": r.source_box, "reason": r.reason} for r in proposal.regions],
            "limitations": proposal.limitations,
            "provenance": {"requested_model": proposal.requested_model,
                           "returned_model": proposal.returned_model, "prompt_version": proposal.prompt_version},
            "metrics": {"elapsed_ms": proposal.elapsed_ms, "prompt_tokens": proposal.prompt_tokens,
                        "completion_tokens": proposal.completion_tokens}})

    async def extract(self, image: PreparedImage, question: str, request_id: str,
                      directory: Path, options: DetailOptions | None = None, *, on_call=None):
        options = options or DetailOptions()
        started = perf_counter()
        usage, limitations, selection_limitations = [], [], []
        calls = 0
        target_kind = options.target_kind or "other"
        reused_crops = 0
        if options.regions:
            try:
                boxes = [validate_source_box(box, image.width, image.height) for box in options.regions]
            except ValueError:
                raise ApiError(422, "invalid_regions", "Analysis regions must lie within the source image.") from None
        elif options.mode == "tiles" and image.width <= options.tile_size * 1.2 and image.height <= options.tile_size * 1.2:
            # A readable source already fits a native detail pass; retain its
            # context and avoid an unnecessary layout call/crop.
            boxes = [(0, 0, image.width, image.height)]
        else:
            if options.max_calls < 2:
                raise ApiError(422, "call_budget", "Automatic selection requires at least two allowed calls.")
            selection = await self.propose_regions(image, question, request_id + "-regions", on_call=on_call)
            calls += 1
            usage.append(selection.metrics)
            boxes = [tuple(r.source_box) for r in selection.regions]
            target_kind = options.target_kind or selection.target_kind
            selection_limitations = selection.limitations
            limitations.extend(selection.limitations)
        if len(set(boxes)) != len(boxes):
            raise ApiError(422, "duplicate_regions", "Analysis regions must be distinct.")
        remaining = options.max_calls - calls
        crops = []
        try:
            for i, box in enumerate(boxes):
                target = directory / f"region-{i}"
                target.mkdir()
                if options.mode == "tiles" and target_kind not in {"floor", "schedule_row", "room"}:
                    crops.extend(await _local_work(
                        optimized_tile_regions, image, box, target,
                        tile_size=(options.tile_size, options.tile_size), overlap=options.overlap,
                        max_tiles=remaining - len(crops)))
                else:
                    crops.append(await _local_work(crop_region, image, box, target))
        except ValueError:
            raise ApiError(422, "invalid_regions", "Regions or tile settings exceed the source bounds or call budget.") from None
        if not crops or len(crops) > remaining:
            raise ApiError(422, "call_budget", "Requested detail scan exceeds the provider-call budget.")

        async def detect(index, crop, *, purpose="analysis", id_prefix="detail", context_target=None):
            # Distinct invocation IDs avoid collisions when identical regions recur.
            region_id = f"{id_prefix}-{index:03d}"
            async with self._slots:
                try:
                    context = {"source_dimensions": [image.width, image.height],
                        "source_crop_box": list(crop.source_box), "selected_panels": [list(box) for box in boxes],
                        "target_kind": context_target or target_kind, "scope": "selected source page; inspect only the attached crop",
                        "coordinate_frame": "attached crop normalized 0..1000; host maps to original source"}
                    if id_prefix == "cv-window":
                        context["inspection_reason"] = (
                            "Unverified CPU line-geometry proposal for missed windows. Inspect this crop for actual "
                            "window frames or thin fixed glazing, including balcony interfaces. Parallel strokes "
                            "alone are not a window: exclude solid walls, annotation and fitted door leaves. "
                            "Keep independently framed units distinct; do not split glass panes into extra windows.")
                    service = self.candidate_service.with_context(context)
                    response = await _provider_call(
                        lambda: service.extract(crop.image, question, request_id + "-" + region_id),
                        client=self.detector_client, image=crop.image, source_box=crop.source_box,
                        call_id=purpose+"-"+region_id, purpose=purpose, on_call=on_call)
                    return region_id, crop, response, None
                except ApiError as exc:
                    return region_id, crop, None, exc

        # asyncio.gather does not cancel siblings after cancellation by itself on
        # every failure path; explicitly drain all tasks before source cleanup.
        tasks = [asyncio.create_task(detect(i, crop)) for i, crop in enumerate(crops)]
        try:
            outputs = await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        calls += len(crops)
        observations, region_trace, replies = [], [], []
        def consume(batch):
            records = []
            for region_id, crop, reply, error in batch:
                region_trace.append({"id": region_id, "source_box": crop.source_box,
                                 "inference_sha256": crop.image.inference_sha256,
                                 "status": reply.status if reply else "failed",
                                 "candidate_count": len(reply.candidates) if reply else 0})
                if error:
                    limitations.append(f"{region_id}: detail inference failed ({error.code}); this region is unresolved.")
                    continue
                replies.append(reply)
                usage.append(reply.metrics)
                limitations.extend(f"{region_id}: {item}" for item in reply.limitations)
                for candidate in reply.candidates:
                    minimum, maximum = crop.map_box(candidate.geometry.minimum, candidate.geometry.maximum)
                    records.append(SourceCandidate(
                        observation_id=region_id + "/" + candidate.id,
                        region_id=region_id, category=candidate.category, box=(*minimum, *maximum),
                        region_box=crop.source_box, source_label=candidate.source_label,
                        uncertain=candidate.uncertain, uncertainty_reason=candidate.uncertainty_reason,
                        visual_cue=candidate.visual_cue, source_sha256=image.sha256))
            return records
        observations = consume(outputs)
        if not replies:
            raise next(error for _, _, _, error in outputs if error)
        deferred = ()
        if options.mode == "tiles":
            observations, deferred = partition_tile_observations(observations,
                {r["id"]: tuple(r["source_box"]) for r in region_trace if r["status"] == "ok"})
            observations = list(observations)
            if deferred:
                limitations.append("Clipped observations were deferred to overlapping interior views; inspect their recorded source evidence if an object appears missing.")
        result = reconcile_candidates(observations, source_sha256=image.sha256,
                                      source_width=image.width, source_height=image.height, target_kind=target_kind)
        cv_review_ids = set()
        if (options.opencv_window_checks and options.verify_membership
                and _window_task(question, target_kind) and calls < options.max_calls
                and self.detector_client.settings.model == "gemini-4-hydrogen"):
            window_candidates = [c for c in result.candidates
                if c.candidate.category.casefold().replace("_", " ") in {"window", "window assembly"}]
            try:
                flagged = await _local_work(find_solid_window_boxes, image.path,
                    [c.candidate.box for c in window_candidates])
            except (ValueError, OSError):
                flagged = ()
            for index in flagged:
                cv_review_ids.update(window_candidates[index].observation_ids)
            if cv_review_ids:
                observations = [replace(o, uncertain=True, uncertainty_reason=(
                    "Local raster check found predominantly solid dark linework inside this window box; "
                    "verify whether a fitted frame or glazing is actually visible."))
                    if o.observation_id in cv_review_ids else o for o in observations]
                result = reconcile_candidates(observations, source_sha256=image.sha256,
                    source_width=image.width, source_height=image.height, target_kind=target_kind)
        # CV supplies inspection regions only. Model detections remain proposals,
        # and the existing hash-bound reconciliation decides observation identity.
        cv_boxes = []
        if (options.opencv_windows and _window_task(question, target_kind)
                and self.detector_client.settings.model == "gemini-4-hydrogen"
                and calls < options.max_calls and len(result.candidates) < 100):
            known = [c.candidate.box for c in result.candidates
                     if c.candidate.category.casefold().replace("_", " ") in {"window", "window assembly"}]
            for panel in boxes:
                remaining = min(2 - len(cv_boxes), options.max_calls - calls - len(cv_boxes))
                if remaining <= 0:
                    break
                try:
                    proposed = await _local_work(propose_window_regions, image.path,
                        source_box=panel, existing_boxes=known, max_regions=remaining)
                except (ValueError, OSError):
                    limitations.append("Local window-region preparation failed; original detections retained.")
                    break
                for box in proposed:
                    if len(cv_boxes) >= min(2, options.max_calls - calls):
                        break
                    if box not in cv_boxes and box not in [crop.source_box for crop in crops]:
                        cv_boxes.append(box)
            for box in cv_boxes:
                target = directory / f"cv-window-{calls}"
                target.mkdir()
                crop = await _local_work(crop_region, image, box, target)
                batch = [await detect(len(region_trace), crop, purpose="reinspection",
                                      id_prefix="cv-window", context_target="window")]
                calls += 1
                # An empty rescue is not evidence against an existing object.
                fresh = consume(batch)
                # A cut-off fragment does not establish a new whole window.
                clipped = [o for o in fresh if any(abs(a-b) <= 2 for a,b in zip(o.box,o.region_box))]
                deferred += tuple(clipped)
                observations.extend(o for o in fresh if o not in clipped)
                if clipped:
                    limitations.append("Optional window inspection found clipped fragments; retained as unresolved evidence.")
            if cv_boxes:
                result = reconcile_candidates(observations, source_sha256=image.sha256,
                    source_width=image.width, source_height=image.height, target_kind=target_kind)
        membership_checks, checked_ids = [], set(cv_review_ids) | {
            o.observation_id for o in observations if o.region_id.startswith("cv-window-")}
        cv_check_used = False
        if options.verify_membership and calls < options.max_calls:
            for merged in result.candidates:
                if not merged.candidate.uncertain or calls >= options.max_calls:
                    continue
                cv_flagged = bool(set(merged.observation_ids) & cv_review_ids)
                if cv_flagged and cv_check_used:
                    continue
                if any(identifier.startswith("cv-window-") for identifier in merged.observation_ids):
                    checked_ids.update(merged.observation_ids)
                    continue
                # Verify membership of one hypothesis. A new regional inventory
                # is not a membership check and must not inflate the object set.
                review = propose_reinspection_regions(replace(result, candidates=(merged,)), max_regions=1)
                if not review.regions:
                    continue
                target = directory / f"membership-{calls}"
                target.mkdir()
                crop = await _local_work(crop_region, image, review.regions[0].source_box, target)
                x0, y0, _, _ = crop.source_box
                a, b, c, d = merged.candidate.box
                local_box = (a-x0, b-y0, c-x0, d-y0)
                if not (0 <= local_box[0] < local_box[2] <= crop.image.width
                        and 0 <= local_box[1] < local_box[3] <= crop.image.height):
                    continue
                region_id = f"membership-{calls:03d}"
                try:
                    async with self._slots:
                        check = await _provider_call(
                            lambda: self.verifier.verify(crop.image, question,
                                category=merged.candidate.category, candidate_box=local_box,
                                source_label=merged.candidate.source_label),
                            client=self.verifier.client, image=crop.image, source_box=crop.source_box,
                            call_id="candidate-verification-"+region_id,
                            purpose="candidate_verification", on_call=on_call)
                    usage.append(check)
                    verdict, reason = check.verdict, check.reason
                    region_status = "partial" if verdict == "ambiguous" else "ok"
                except ApiError as exc:
                    verdict, reason, region_status = "failed", f"Membership check failed ({exc.code}); original evidence retained.", "failed"
                    limitations.append(reason)
                calls += 1
                cv_check_used = cv_check_used or cv_flagged
                checked_ids.update(merged.observation_ids)
                region_trace.append({"id": region_id, "source_box": crop.source_box,
                    "inference_sha256": crop.image.inference_sha256,
                    "status": region_status, "candidate_count": 0})
                membership_checks.append({"observation_ids": list(merged.observation_ids),
                    "category": merged.candidate.category, "source_box": merged.candidate.box,
                    "region_id": region_id, "verdict": verdict, "reason": reason})
                if verdict == "rejected":
                    observations = [o for o in observations if o.observation_id not in merged.observation_ids]
                elif verdict == "supported":
                    observations = [replace(o, uncertain=False, uncertainty_reason=None)
                        if o.observation_id in merged.observation_ids else o for o in observations]
            result = reconcile_candidates(observations, source_sha256=image.sha256,
                source_width=image.width, source_height=image.height, target_kind=target_kind)
        superseded = []
        seen_crops = {(crop.source_box, crop.image.inference_sha256) for crop in crops}
        if options.reinspect_edges and not cv_boxes and target_kind not in {"floor", "schedule_row", "room"} and calls < options.max_calls and result.status == "partial":
            pending_result = replace(result, candidates=tuple(c for c in result.candidates
                if not set(c.observation_ids) <= checked_ids
                and not any(identifier.startswith("cv-window-") for identifier in c.observation_ids)))
            inspection = propose_reinspection_regions(pending_result, max_regions=options.max_calls-calls)
            for inspection_region in inspection.regions:
                # Recentered observations resolve crop seams using new pixels;
                # no old proposal is removed on the basis of an empty crop result.
                target = directory / f"recheck-{calls}"
                target.mkdir()
                crop = await _local_work(crop_region, image, inspection_region.source_box, target)
                key = (crop.source_box, crop.image.inference_sha256)
                if key in seen_crops:
                    reused_crops += 1
                    continue
                seen_crops.add(key)
                batch = [await detect(len(region_trace), crop, purpose="reinspection")]
                calls += 1
                fresh = consume(batch)
                if batch[0][2] is not None and batch[0][2].status == "ok":
                    applied = apply_reinspection(observations, fresh,
                        source_sha256=image.sha256, source_width=image.width, source_height=image.height,
                        reviewed_box=inspection_region.source_box, target_kind=target_kind)
                    observations, result = list(applied.observations), applied.result
                    superseded.extend(applied.superseded_ids)
                else:
                    observations.extend(fresh)
                    result = reconcile_candidates(observations, source_sha256=image.sha256,
                        source_width=image.width, source_height=image.height, target_kind=target_kind)
        limitations.extend(result.issues)
        if result.status == "partial" and not limitations:
            limitations.append("Some candidate memberships remain uncertain; inspect the source evidence.")
        if any(reply.status != "ok" for reply in replies) and not limitations:
            limitations.append("Some analyzed regions could not be fully interpreted.")
        if len(result.candidates) >= 100:
            limitations.append("Candidate limit reached; additional candidates are not returned.")
        public, provenance = [], []
        lookup = {o.observation_id: o.region_id for o in observations}
        labels = {o.observation_id: o.source_label for o in observations}
        for index, merged in enumerate(result.candidates[:100]):
            candidate = merged.candidate
            candidate_id = f"candidate-{index+1:03d}"
            a, b, c, d = candidate.box
            public.append({"id": candidate_id, "category": candidate.category,
                           "source_label": candidate.source_label,
                           "geometry": {"kind": "box", "minimum": [a, b], "maximum": [c, d]},
                           "uncertain": merged.uncertain,
                           "uncertainty_reason": merged.uncertainty_reason[:1000] if merged.uncertainty_reason else None,
                           "visual_cue": candidate.visual_cue})
            provenance.append({"candidate_id": candidate_id, "observation_ids": list(merged.observation_ids),
                               "region_ids": sorted({lookup[o] for o in merged.observation_ids}),
                               "clipped": merged.clipped,
                               "source_labels": list(dict.fromkeys(labels[o] for o in merged.observation_ids))})
        # Failed attempts have unknown usage; never report their cost as zero.
        incomplete_usage = any(region["status"] == "failed" for region in region_trace)
        status = "partial" if limitations or result.status == "partial" else "ok"
        # A uniform non-answer across every attempted region retains its reason.
        # Mixed statuses or failed regions remain partial, never a proven zero.
        if not public and not incomplete_usage:
            reply_statuses = {reply.status for reply in replies}
            if reply_statuses == {"unsupported"}:
                status = "unsupported"
            elif reply_statuses == {"unreadable"}:
                status = "unreadable"
        pending = propose_reinspection_regions(result, max_regions=12)
        return ImageCandidateResponse.model_validate({
            "request_id": request_id, "image": _image_metadata(image),
            "status": status,
            "candidates": public, "limitations": [item[:2000] for item in dict.fromkeys(limitations)][:100],
            "provenance": {"requested_model": replies[0].provenance.requested_model,
                           "returned_model": replies[0].provenance.returned_model,
                           "prompt_version": "detail-tools-v3"},
            "metrics": {"elapsed_ms": (perf_counter()-started)*1000,
                        "prompt_tokens": None if incomplete_usage else _total_usage(usage, "prompt_tokens"),
                        "completion_tokens": None if incomplete_usage else _total_usage(usage, "completion_tokens"),
                        "preparation_ms": image.preparation_ms},
            "detail": {"mode": options.mode, "selection": "explicit" if options.regions else "automatic",
                       "selected_regions": boxes, "regions": region_trace,
                       "observations": provenance, "provider_calls": calls,
                       "selection_limitations": selection_limitations,
                       "target_kind": target_kind, "reused_crops": reused_crops,
                       "membership_checks": membership_checks,
                       "superseded_observation_ids": superseded,
                       "reinspection_regions": [r.source_box for r in pending.regions],
                       "deferred_observations": [{"observation_id": o.observation_id,
                           "region_id": o.region_id, "category": o.category, "source_box": o.box,
                           "reason": ("Clipped optional window inspection; not an established additional whole instance."
                                      if o.region_id.startswith("cv-window-") else
                                      "Clipped crop-edge observation; overlapping successful tile provides more interior context.")}
                           for o in deferred]}})
