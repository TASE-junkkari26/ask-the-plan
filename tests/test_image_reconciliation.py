"""Offline source-instance reconciliation checks; no inference or accuracy claim."""
from __future__ import annotations

import unittest

from image_api.reconciliation import SourceCandidate, box_iou, reconcile_candidates, propose_reinspection_regions, apply_reinspection, partition_tile_observations


SOURCE_SHA = "a" * 64


def observation(identifier, box, *, region="full", region_box=(0, 0, 1000, 1000),
                label=None, category="door", uncertain=False):
    return SourceCandidate(identifier, region, category, box, region_box, label,
                           uncertain, "Membership unclear" if uncertain else None,
                           "Visible leaf and swing arc")


def reconcile(items):
    return reconcile_candidates(items, source_sha256=SOURCE_SHA, source_width=1000, source_height=1000)


class ReconciliationTests(unittest.TestCase):
    def test_repeated_cross_crop_object_retains_original_geometry_and_both_sources(self):
        a = observation("wide-1", (100, 100, 200, 200))
        b = observation("detail-1", (104, 101, 202, 201), region="detail", region_box=(50, 50, 300, 300))
        result = reconcile([a, b])
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].candidate, b)
        self.assertEqual(set(result.candidates[0].observation_ids), {"wide-1", "detail-1"})
        self.assertEqual(result.candidates[0].candidate.box, b.box)
        self.assertEqual(result.merges[0].absorbed_observation_id, "wide-1")
        self.assertEqual(result.status, "ok")
        public = result.to_dict()
        self.assertEqual(public["source_sha256"], SOURCE_SHA)
        self.assertEqual(public["candidates"][0]["geometry"]["minimum"], [104, 101])
        self.assertEqual(public["inventory_completeness"], "unverified")

    def test_full_observation_absorbs_truncated_crop_observation(self):
        complete = observation("complete", (100, 100, 200, 200))
        partial = observation("partial", (100, 100, 150, 200), region="edge", region_box=(50, 50, 150, 250))
        result = reconcile([partial, complete])
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].candidate, complete)
        self.assertFalse(result.candidates[0].clipped)
        self.assertFalse(result.candidates[0].uncertain)

    def test_unresolved_truncation_is_partial_and_requests_recenter(self):
        item = observation("clipped", (100, 100, 150, 200), region="edge", region_box=(50, 50, 150, 250))
        result = reconcile([item])
        self.assertEqual(result.status, "partial")
        self.assertTrue(result.candidates[0].uncertain)
        self.assertIn("recentered", result.candidates[0].uncertainty_reason)

    def test_adjacent_doorways_are_not_merged(self):
        a = observation("left", (100, 100, 200, 200))
        b = observation("right", (205, 100, 305, 200), region="detail", region_box=(50, 50, 400, 400))
        result = reconcile([a, b])
        self.assertEqual(len(result.candidates), 2)
        self.assertEqual(result.status, "ok")
        self.assertFalse(result.merges)

    def test_ambiguous_overlap_keeps_both_and_marks_membership_uncertain(self):
        a = observation("left", (100, 100, 200, 200))
        b = observation("drift", (145, 100, 245, 200), region="detail", region_box=(50, 50, 400, 400))
        result = reconcile([a, b])
        self.assertEqual(len(result.candidates), 2)
        self.assertTrue(all(item.uncertain for item in result.candidates))
        self.assertEqual(result.status, "partial")
        self.assertFalse(result.merges)

    def test_conflicting_literal_labels_remain_distinct(self):
        a = observation("label-a", (100, 100, 200, 200), label="121.A")
        b = observation("label-b", (101, 101, 201, 201), label="121.B", region="detail", region_box=(50, 50, 400, 400))
        result = reconcile([a, b])
        self.assertEqual(len(result.candidates), 2)
        self.assertEqual({c.candidate.source_label for c in result.candidates}, {"121.A", "121.B"})
        self.assertEqual(result.status, "partial")

    def test_same_region_duplicates_are_not_silently_merged(self):
        result = reconcile([observation("first", (100, 100, 200, 200)),
                            observation("second", (101, 101, 201, 201))])
        self.assertEqual(len(result.candidates), 2)
        self.assertEqual(result.status, "partial")

    def test_different_categories_at_same_box_require_review(self):
        result = reconcile([observation("door", (100, 100, 200, 200)),
                            observation("window", (100, 100, 200, 200), category="window", region="detail")])
        self.assertEqual(len(result.candidates), 2)
        self.assertEqual(result.status, "partial")

    def test_no_transitive_chain_merges_separate_instances(self):
        items = [observation("a", (100, 100, 200, 200), region="a"),
                 observation("b", (125, 100, 225, 200), region="b"),
                 observation("c", (150, 100, 250, 200), region="c")]
        result = reconcile(items)
        self.assertEqual(len(result.candidates), 2)
        self.assertEqual(result.status, "partial")
        self.assertLessEqual(max(len(c.observation_ids) for c in result.candidates), 2)

    def test_centered_fixture_extents_share_fixed_anchor_without_box_averaging(self):
        anchor = observation("detail", (100,100,160,230), category="toilet", region="detail", region_box=(70,70,300,300))
        bowl = observation("bowl", (101,134,149,206), category="toilet", region="wide")
        shifted_bowl = observation("shifted", (114,135,163,216), category="toilet", region="other")
        result = reconcile_candidates([bowl,shifted_bowl,anchor], source_sha256=SOURCE_SHA,
            source_width=1000, source_height=1000, target_kind="toilet")
        self.assertEqual(len(result.candidates),1)
        self.assertEqual(result.candidates[0].candidate.box,anchor.box)
        self.assertEqual(set(result.candidates[0].observation_ids),{"detail","bowl","shifted"})

    def test_room_containment_is_not_generic_fixture_identity(self):
        whole = observation("whole", (100,100,300,300), category="room")
        small = observation("small", (150,150,250,250), category="room", region="detail")
        result = reconcile_candidates([whole,small], source_sha256=SOURCE_SHA,
            source_width=1000, source_height=1000, target_kind="room")
        self.assertEqual(len(result.candidates),2)

    def test_floor_aliases_and_different_panel_labels_need_explicit_count_grain(self):
        a=observation("a",(100,100,500,700),category="floor_plan",label="A5 3HKS / 75,5 m2")
        b=observation("b",(101,102,499,698),category="floor",label="lattia +20.97",region="again")
        self.assertEqual(len(reconcile([a,b]).candidates),2)
        typed=reconcile_candidates([a,b],source_sha256=SOURCE_SHA,source_width=1000,source_height=1000,target_kind="floor")
        self.assertEqual(len(typed.candidates),1)
        self.assertIn(typed.candidates[0].candidate.source_label,{a.source_label,b.source_label})

    def test_schedule_row_id_and_spatial_evidence_reconcile_full_and_bare_labels(self):
        a=observation("a",(100,100,900,120),category="room_schedule_row",label="121.A  Käytävä")
        b=observation("b",(102,104,898,124),category="room",label="121.A",region="again")
        typed=reconcile_candidates([a,b],source_sha256=SOURCE_SHA,source_width=1000,source_height=1000,target_kind="schedule_row")
        self.assertEqual(len(typed.candidates),1)
        self.assertEqual(typed.candidates[0].candidate.source_label,"121.A  Käytävä")
        self.assertEqual(len(reconcile([a,b]).candidates),2)

    def test_equal_row_ids_in_distant_panels_do_not_merge(self):
        a=observation("a",(50,100,450,120),category="room_schedule_row",label="100 LOBBY")
        b=observation("b",(550,100,950,120),category="room",label="100",region="other-panel")
        result=reconcile_candidates([a,b],source_sha256=SOURCE_SHA,source_width=1000,source_height=1000,target_kind="schedule_row")
        self.assertEqual(len(result.candidates),2)

    def test_different_row_ids_keep_adjacent_rows_separate_despite_drift(self):
        a=observation("a",(100,100,900,120),category="room_schedule_row",label="100 LOBBY")
        b=observation("b",(100,109,900,129),category="room",label="101",region="other")
        result=reconcile_candidates([a,b],source_sha256=SOURCE_SHA,source_width=1000,source_height=1000,target_kind="schedule_row")
        self.assertEqual(len(result.candidates),2)

    def test_label_spacing_normalizes_only_comparison_and_preserves_literals(self):
        a=observation("a",(100,100,200,200),label="LO 10")
        b=observation("b",(101,101,201,201),label="lo10",region="detail")
        result=reconcile([a,b])
        self.assertEqual(len(result.candidates),1)
        self.assertEqual(result.candidates[0].candidate.source_label,"LO 10")
        third=observation("c",(101,101,201,201),label="L010",region="other")
        self.assertEqual(len(reconcile([a,third]).candidates),2)

    def test_wc_room_and_toilet_fixture_are_not_untyped_synonyms(self):
        a=observation("a",(100,100,200,200),category="wc")
        b=observation("b",(101,101,201,201),category="toilet",region="detail")
        self.assertEqual(len(reconcile([a,b]).candidates),2)
        result=reconcile_candidates([a,b],source_sha256=SOURCE_SHA,source_width=1000,source_height=1000,target_kind="toilet")
        self.assertEqual(len(result.candidates),1)

    def test_unknown_target_kind_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"target kind"):
            reconcile_candidates([],source_sha256=SOURCE_SHA,source_width=1000,source_height=1000,target_kind="made-up")

    def test_ambiguous_assignment_does_not_create_an_extra_instance(self):
        a=observation("a",(100,100,200,200),label="121.A",region="a")
        b=observation("b",(125,100,225,200),label="121.B",region="b")
        c=observation("c",(110,100,210,200),region="c")
        result=reconcile([a,b,c])
        self.assertEqual(len(result.candidates),2)
        self.assertEqual(sum(len(item.observation_ids) for item in result.candidates),3)
        self.assertTrue(all(item.uncertain for item in result.candidates))
        self.assertTrue(any("ambiguous membership" in issue for issue in result.issues))

    def test_near_identical_ocr_label_variants_are_one_uncertain_door_hypothesis(self):
        first=observation("first",(100,100,200,250),label="O9",region="first")
        second=observation("second",(101,101,201,251),label="09",region="second")
        result=reconcile_candidates([first,second],source_sha256=SOURCE_SHA,source_width=1000,
                                    source_height=1000,target_kind="door")
        self.assertEqual(len(result.candidates),1)
        self.assertTrue(result.candidates[0].uncertain)
        self.assertEqual(result.status,"partial")
        self.assertIn("O/0 ambiguity",result.candidates[0].uncertainty_reason)
        self.assertIn("'O9'",result.candidates[0].uncertainty_reason)
        self.assertIn("'09'",result.candidates[0].uncertainty_reason)
        self.assertEqual(set(result.candidates[0].observation_ids),{"first","second"})
        self.assertEqual(result.candidates[0].candidate.source_label,"O9")
        self.assertEqual(result.candidates[0].candidate.box,first.box)

    def test_ocr_label_hypothesis_requires_typed_compact_object_and_strong_geometry(self):
        first=observation("first",(100,100,200,250),label="O9",region="first")
        shifted=observation("shifted",(115,100,215,250),label="09",region="second")
        self.assertEqual(len(reconcile([first,shifted]).candidates),2)
        typed=reconcile_candidates([first,shifted],source_sha256=SOURCE_SHA,source_width=1000,
                                   source_height=1000,target_kind="door")
        self.assertEqual(len(typed.candidates),2)
        room1=observation("room1",(100,100,200,250),label="O9",category="room",region="first")
        room2=observation("room2",(101,101,201,251),label="09",category="room",region="second")
        rooms=reconcile_candidates([room1,room2],source_sha256=SOURCE_SHA,source_width=1000,
                                   source_height=1000,target_kind="room")
        self.assertEqual(len(rooms.candidates),2)

    def test_real_conflicting_ids_are_not_ocr_variants_even_at_identical_geometry(self):
        first=observation("first",(100,100,200,250),label="121.A",region="first")
        second=observation("second",(101,101,201,251),label="121.B",region="second")
        result=reconcile_candidates([first,second],source_sha256=SOURCE_SHA,source_width=1000,
                                    source_height=1000,target_kind="door")
        self.assertEqual(len(result.candidates),2)

    def test_labeled_clipped_extent_is_one_uncertain_instance_with_complete_geometry(self):
        whole=observation("whole",(400,400,520,550),label="08",region="whole")
        fragment=observation("fragment",(390,380,520,477),label="08",region="fragment",region_box=(300,380,700,700))
        result=reconcile_candidates([fragment,whole],source_sha256=SOURCE_SHA,source_width=1000,
                                    source_height=1000,target_kind="door")
        self.assertEqual(len(result.candidates),1)
        self.assertEqual(result.candidates[0].candidate.box,whole.box)
        self.assertTrue(result.candidates[0].uncertain)
        self.assertIn("Clipped and complete",result.candidates[0].uncertainty_reason)
        self.assertEqual(set(result.candidates[0].observation_ids),{"whole","fragment"})

    def test_clipped_hypothesis_does_not_merge_different_ids_or_far_repeated_type_labels(self):
        whole=observation("whole",(400,400,520,550),label="08",region="whole")
        conflict=observation("fragment",(390,380,520,477),label="09",region="fragment",region_box=(300,380,700,700))
        far=observation("far",(600,380,700,477),label="08",region="far",region_box=(500,380,800,700))
        for other in (conflict,far):
            result=reconcile_candidates([whole,other],source_sha256=SOURCE_SHA,source_width=1000,
                                        source_height=1000,target_kind="door")
            self.assertEqual(len(result.candidates),2)

    def test_unlabeled_or_unclipped_jitter_does_not_gain_labeled_fragment_rule(self):
        whole=observation("whole",(400,400,520,550),region="whole")
        fragment=observation("fragment",(390,380,520,477),region="fragment",region_box=(300,380,700,700))
        result=reconcile_candidates([whole,fragment],source_sha256=SOURCE_SHA,source_width=1000,
                                    source_height=1000,target_kind="door")
        self.assertEqual(len(result.candidates),2)

    def test_input_order_does_not_change_result(self):
        items = [observation("a", (100, 100, 200, 200), region="a"),
                 observation("b", (103, 100, 203, 200), region="b"),
                 observation("c", (400, 400, 500, 500), region="c")]
        self.assertEqual(reconcile(items), reconcile(list(reversed(items))))

    def test_uncertainty_is_not_discarded_from_selected_observation(self):
        result = reconcile([observation("uncertain", (100, 100, 200, 200), uncertain=True)])
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.candidates[0].uncertainty_reason, "Membership unclear")

    def test_empty_observations_are_unverified_not_proven_zero(self):
        result = reconcile([])
        self.assertEqual(result.candidates, ())
        self.assertEqual(result.inventory_completeness, "unverified")

    def test_invalid_source_frames_ids_and_coordinates_are_rejected(self):
        item = observation("same", (100, 100, 200, 200))
        with self.assertRaisesRegex(ValueError, "unique"):
            reconcile([item, item])
        with self.assertRaisesRegex(ValueError, "outside"):
            reconcile([observation("outside", (100, 100, 200, 200), region_box=(0, 0, 1500, 1500))])
        with self.assertRaisesRegex(ValueError, "within"):
            observation("wrong", (0, 0, 200, 200), region_box=(50, 50, 300, 300))
        with self.assertRaisesRegex(ValueError, "finite"):
            observation("nan", (0, 0, float("nan"), 200))
        with self.assertRaisesRegex(ValueError, "SHA256"):
            reconcile_candidates([item], source_sha256="bad", source_width=1000, source_height=1000)
        with self.assertRaisesRegex(ValueError, "positive"):
            reconcile_candidates([item], source_sha256=SOURCE_SHA, source_width=0, source_height=1000)

    def test_iou_has_known_values(self):
        self.assertEqual(box_iou((0, 0, 100, 100), (0, 0, 100, 100)), 1)
        self.assertEqual(box_iou((0, 0, 100, 100), (100, 100, 200, 200)), 0)
        self.assertAlmostEqual(box_iou((0, 0, 100, 100), (50, 0, 150, 100)), 1/3)

    def test_wrong_revision_hash_and_region_id_collisions_are_rejected(self):
        wrong = SourceCandidate("wrong", "a", "door", (100,100,200,200), (0,0,1000,1000), source_sha256="b"*64)
        with self.assertRaisesRegex(ValueError, "different source"):
            reconcile([wrong])
        with self.assertRaisesRegex(ValueError, "region ID"):
            reconcile([observation("a", (100,100,200,200)),
                       observation("b", (100,100,200,200), region_box=(50,50,300,300))])

    def test_reinspection_recenters_clipping_and_combines_disputed_pair(self):
        full = observation("full", (400,400,500,500))
        partial = observation("partial", (400,370,470,450), region="edge", region_box=(300,370,470,600))
        result = reconcile([full, partial])
        plan = propose_reinspection_regions(result)
        self.assertEqual(len(plan.regions), 1)
        crop = plan.regions[0].source_box
        self.assertLess(crop[0], 400)
        self.assertLess(crop[1], 370)
        self.assertGreater(crop[2], 500)
        self.assertGreater(crop[3], 500)
        self.assertEqual(set(plan.regions[0].observation_ids), {"full", "partial"})
        self.assertEqual(plan.deferred_observation_ids, ())

    def test_reinspection_budget_reports_deferred_and_clamps_to_source(self):
        result = reconcile([observation("left", (0,100,20,120)),
                            observation("right", (950,950,1000,1000))])
        plan = propose_reinspection_regions(result, max_regions=1)
        self.assertEqual(len(plan.regions), 1)
        self.assertEqual(plan.regions[0].source_box[0], 0)
        self.assertEqual(plan.deferred_observation_ids, ("right",))
        all_regions = propose_reinspection_regions(result).regions
        self.assertTrue(all(0 <= r.source_box[0] < r.source_box[2] <= 1000 for r in all_regions))
        self.assertTrue(all(0 <= r.source_box[1] < r.source_box[3] <= 1000 for r in all_regions))
        self.assertEqual(propose_reinspection_regions(reconcile([])).regions, ())

    def test_fresh_inspection_supersedes_only_corroborated_clipped_old_observation(self):
        full = observation("full", (400,400,500,500), region="wide")
        fragment = observation("fragment", (400,380,470,465), region="edge", region_box=(300,380,470,600))
        context = (250,250,650,650)
        fresh = observation("fresh", (400,395,495,495), region="review", region_box=context)
        applied = apply_reinspection([full,fragment], [fresh], source_sha256=SOURCE_SHA,
                                    source_width=1000, source_height=1000, reviewed_box=context)
        self.assertEqual(applied.superseded_ids, ("fragment",))
        self.assertEqual({c.observation_id for c in applied.observations}, {"full", "fresh"})
        self.assertEqual(applied.replacements[0].fresh_observation_id, "fresh")
        self.assertEqual(len(applied.result.candidates), 1)
        self.assertEqual(set(applied.result.candidates[0].observation_ids), {"full", "fresh"})

    def test_empty_contradictory_or_uncertain_fresh_inspection_never_deletes_old(self):
        fragment = observation("fragment", (400,380,470,465), region="edge", region_box=(300,380,470,600), label="121.A")
        context = (250,250,650,650)
        options = [[],
                   [observation("other-label", (400,395,495,495), region="review", region_box=context, label="121.B")],
                   [observation("other-category", (400,395,495,495), region="review", region_box=context, category="window")],
                   [observation("uncertain", (400,395,495,495), region="review", region_box=context, uncertain=True)]]
        for fresh in options:
            applied = apply_reinspection([fragment], fresh, source_sha256=SOURCE_SHA,
                                        source_width=1000, source_height=1000, reviewed_box=context)
            self.assertFalse(applied.superseded_ids)
            self.assertIn(fragment, applied.observations)

    def test_nearby_separate_door_from_fresh_inspection_does_not_remove_fragment(self):
        fragment = observation("fragment", (400,380,470,465), region="edge", region_box=(300,380,470,600))
        context = (250,250,750,650)
        other = observation("separate", (500,395,595,495), region="review", region_box=context)
        applied = apply_reinspection([fragment], [other], source_sha256=SOURCE_SHA,
                                    source_width=1000, source_height=1000, reviewed_box=context)
        self.assertFalse(applied.superseded_ids)
        self.assertEqual(len(applied.observations), 2)

    def test_fresh_inspection_must_belong_to_reviewed_context(self):
        fresh = observation("wrong-frame", (400,395,495,495), region="review")
        with self.assertRaisesRegex(ValueError, "reviewed crop"):
            apply_reinspection([], [fresh], source_sha256=SOURCE_SHA, source_width=1000,
                               source_height=1000, reviewed_box=(250,250,650,650))

    def test_tile_ownership_defers_clipped_fragment_to_deeper_successful_tile(self):
        left, right = (0,0,600,800), (400,0,1000,800)
        clipped_right_edge = observation("left-edge", (550,300,600,400), region="left", region_box=left)
        clipped_left_edge = observation("right-edge", (400,300,450,400), region="right", region_box=right)
        kept, deferred = partition_tile_observations([clipped_right_edge,clipped_left_edge], {"left":left,"right":right})
        self.assertEqual(kept, ())
        self.assertEqual(set(deferred), {clipped_right_edge,clipped_left_edge})

    def test_tile_ownership_keeps_nonclipped_adjacent_doors_even_outside_core(self):
        left, right = (0,0,600,800), (400,0,1000,800)
        first = observation("first", (530,300,590,400), region="left", region_box=left)
        second = observation("second", (610,300,670,400), region="right", region_box=right)
        kept, deferred = partition_tile_observations([first,second], {"left":left,"right":right})
        self.assertEqual(kept, (first,second))
        self.assertEqual(deferred, ())

    def test_tile_ownership_keeps_fragment_when_neighbor_failed_or_missing(self):
        left = (0,0,600,800)
        fragment = observation("fragment", (550,300,600,400), region="left", region_box=left)
        self.assertEqual(partition_tile_observations([fragment], {"left":left}), ((fragment,), ()))
        self.assertEqual(partition_tile_observations([fragment], {}), ((fragment,), ()))

    def test_tile_ownership_keeps_source_edge_and_ties(self):
        left, right = (0,0,600,800), (400,0,1000,800)
        source_edge = observation("source-edge", (0,300,50,400), region="left", region_box=left)
        tied = observation("tie", (490,0,510,30), region="left", region_box=left)
        # Both containing tiles are equally close to the source top edge.
        kept, deferred = partition_tile_observations([source_edge,tied], {"right":right,"left":left})
        self.assertEqual(kept, (source_edge,tied))
        self.assertFalse(deferred)

    def test_tile_ownership_rejects_region_id_frame_mismatch(self):
        item = observation("x", (550,300,600,400), region="left", region_box=(0,0,600,800))
        with self.assertRaisesRegex(ValueError, "source frame"):
            partition_tile_observations([item], {"left":(0,0,650,800)})


if __name__ == "__main__":
    unittest.main()
