"""Offline pixel/frame/coverage checks; no inference calls or accuracy claims."""
from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageChops

from image_api.config import ApiSettings
from image_api.images import prepare_image
from image_api.region_tools import (RegionToolError, crop_region, tile_boxes, tile_regions,
                                    validate_source_box, optimized_tile_boxes, optimized_tile_regions)


class RegionToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = Image.new("RGB", (80, 60))
        source.putdata([(x*3, y*4, (x+y)*1) for y in range(60) for x in range(80)])
        buffer = BytesIO()
        source.save(buffer, format="PNG")
        self.source = source
        self.addCleanup(source.close)
        self.image = prepare_image(buffer.getvalue(), ApiSettings(), self.root)

    def test_crop_preserves_native_pixels_and_exact_source_transform(self):
        region = crop_region(self.image, [11, 7, 48, 32], self.root/"crops")
        self.assertEqual((region.image.width, region.image.height), (37, 25))
        with Image.open(region.image.path) as actual, self.source.crop((11,7,48,32)) as expected:
            self.assertIsNone(ImageChops.difference(actual, expected).getbbox())
        self.assertEqual(region.map_box([0, 0], [37, 25]), ((11, 7), (48, 32)))
        self.assertEqual(region.map_box([1.5, 2.25], [5.5, 9.75]), ((12.5, 9.25), (16.5, 16.75)))
        self.assertEqual(region.to_source, ((1.,0.,11.),(0.,1.,7.),(0.,0.,1.)))
        self.assertEqual(region.source_sha256, self.image.sha256)
        self.assertEqual(region.canonical_source_sha256, self.image.inference_sha256)

    def test_metadata_is_json_serializable_without_private_paths(self):
        region = crop_region(self.image, (0,0,80,60), self.root/"crops")
        metadata = region.to_metadata()
        encoded = json.dumps(metadata)
        self.assertNotIn(str(self.root), encoded)
        self.assertNotIn("path", metadata)
        self.assertEqual(metadata["source_box"], [0,0,80,60])
        self.assertEqual(metadata["source_frame_id"], "display:sha256:"+self.image.sha256)

    def test_region_identity_is_stable_across_directories_and_reuse(self):
        first = crop_region(self.image, (1,2,30,40), self.root/"a")
        second = crop_region(self.image, (1,2,30,40), self.root/"b")
        again = crop_region(self.image, (1,2,30,40), self.root/"a")
        other = crop_region(self.image, (2,2,30,40), self.root/"a")
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.image.sha256, again.image.sha256)
        self.assertNotEqual(first.id, other.id)

    def test_invalid_regions_are_rejected_without_clamping_or_output(self):
        for box in ([0,0,81,60], [-1,0,10,10], [0,0,0,2], [0,10,20,2],
                    [0.,0,10,10], [False,0,10,10], [0,0,10], "0000"):
            with self.subTest(box=box), self.assertRaises(RegionToolError):
                crop_region(self.image, box, self.root/"invalid")
        self.assertFalse((self.root/"invalid").exists())

    def test_candidate_bounds_do_not_escape_crop_or_accept_nan(self):
        region = crop_region(self.image, (10,10,30,30), self.root/"crops")
        for low, high in (([0,0], [21,20]), ([-1,0],[2,2]), ([1,1],[1,2]),
                          ([float("nan"),0],[2,2]), ([True,0],[2,2]), ([0],[2,2])):
            with self.subTest(low=low, high=high), self.assertRaises(RegionToolError):
                region.map_box(low, high)

    def test_overview_and_mismatched_pixels_are_rejected(self):
        for image in (replace(self.image, preprocessing_mode="overview"),
                      replace(self.image, inference_width=40),
                      replace(self.image, width=79),
                      replace(self.image, inference_sha256="0"*64)):
            with self.subTest(image=image), self.assertRaises(RegionToolError):
                crop_region(image, (0,0,10,10), self.root/"invalid")

    def test_source_mutation_is_detected_before_cropping(self):
        self.image.path.write_bytes(b"not-the-source")
        with self.assertRaisesRegex(RegionToolError, "hash"):
            crop_region(self.image, (0,0,10,10), self.root/"invalid")

    def test_tiling_covers_every_selected_pixel_with_overlap_and_no_scope_growth(self):
        roi = (7,5,74,53)
        boxes = tile_boxes(roi, 80,60, tile_size=(30,22), overlap=6, max_tiles=16)
        self.assertEqual(boxes, tile_boxes(roi,80,60,tile_size=(30,22),overlap=6,max_tiles=16))
        self.assertEqual(boxes[0], (7,5,37,27))
        self.assertEqual(boxes[-1], (44,31,74,53))
        counts = {}
        for x0,y0,x1,y1 in boxes:
            self.assertLessEqual(x1-x0,30)
            self.assertLessEqual(y1-y0,22)
            self.assertTrue(roi[0]<=x0<x1<=roi[2] and roi[1]<=y0<y1<=roi[3])
            for y in range(y0,y1):
                for x in range(x0,x1):
                    counts[x,y] = counts.get((x,y),0)+1
        self.assertEqual(len(counts), (roi[2]-roi[0])*(roi[3]-roi[1]))
        self.assertGreater(max(counts.values()),1)

    def test_small_region_is_one_unchanged_tile(self):
        regions = tile_regions(self.image,(20,10,35,25),self.root/"tiles",tile_size=(40,40),overlap=10)
        self.assertEqual(len(regions),1)
        self.assertEqual(regions[0].source_box,(20,10,35,25))
        self.assertEqual(regions[0].map_box((0,0),(15,15)),((20,10),(35,25)))

    def test_tile_limit_is_enforced_before_any_artifact_is_written(self):
        with self.assertRaisesRegex(RegionToolError,"more tiles"):
            tile_regions(self.image,(0,0,80,60),self.root/"tiles",tile_size=(20,20),overlap=5,max_tiles=2)
        self.assertFalse((self.root/"tiles").exists())
        with self.assertRaisesRegex(RegionToolError,"more tiles"):
            tile_boxes((0,0,1_000_000_000,1),1_000_000_000,1,tile_size=(1,1),overlap=0)

    def test_invalid_tile_parameters_are_rejected(self):
        for kwargs in ({"tile_size":(0,20)}, {"tile_size":(9000,20)}, {"tile_size":(True,20)},
                       {"overlap":-1}, {"overlap":1280}, {"overlap":1.5},
                       {"max_tiles":0}, {"max_tiles":65}, {"max_tiles":True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(RegionToolError):
                tile_boxes((0,0,80,60),80,60,**kwargs)

    def test_every_tile_contains_its_original_source_pixels(self):
        regions = tile_regions(self.image,(3,7,77,58),self.root/"tiles",tile_size=(32,24),overlap=8)
        for region in regions:
            with Image.open(region.image.path) as actual, self.source.crop(region.source_box) as expected:
                self.assertIsNone(ImageChops.difference(actual,expected).getbbox())

    def test_optimized_slightly_oversize_region_is_one_native_tile(self):
        self.assertEqual(optimized_tile_boxes((89,786,1517,1558),1600,1800),
                         [(89,786,1517,1558)])
        self.assertEqual(optimized_tile_boxes((0,0,955,1475),955,1475), [(0,0,955,1475)])
        # The original strict tool still enforces the exact preferred edge.
        self.assertEqual(len(tile_boxes((0,0,1428,772),1428,772,tile_size=(1400,1400),overlap=200)),2)

    def test_optimized_minimal_grid_enlarges_only_as_needed(self):
        boxes=optimized_tile_boxes((0,0,3000,1200),3000,1200)
        self.assertEqual(boxes, [(0,0,1600,1200),(1400,0,3000,1200)])
        # Evenly spaced seams avoid appending a nearly identical final tile.
        boxes=optimized_tile_boxes((0,0,3748,1000),3748,1000,slack_fraction=0)
        self.assertEqual([b[0] for b in boxes],[0,1174,2348])
        self.assertEqual([b[2]-b[0] for b in boxes],[1400]*3)

    def test_optimized_tiles_cover_roi_with_bounded_edges_and_minimum_overlap(self):
        roi=(7,5,74,53)
        boxes=optimized_tile_boxes(roi,80,60,tile_size=(30,22),overlap=6)
        self.assertEqual(boxes,optimized_tile_boxes(roi,80,60,tile_size=(30,22),overlap=6))
        covered=set()
        for a,b,c,d in boxes:
            self.assertTrue(roi[0]<=a<c<=roi[2] and roi[1]<=b<d<=roi[3])
            self.assertLessEqual(c-a,36)
            self.assertLessEqual(d-b,26)
            covered.update((x,y) for x in range(a,c) for y in range(b,d))
        self.assertEqual(len(covered),(roi[2]-roi[0])*(roi[3]-roi[1]))
        horizontal=sorted({(a,c) for a,_,c,_ in boxes})
        vertical=sorted({(b,d) for _,b,_,d in boxes})
        self.assertTrue(all(a[1]-b[0]>=6 for a,b in zip(horizontal,horizontal[1:])))
        self.assertTrue(all(a[1]-b[0]>=6 for a,b in zip(vertical,vertical[1:])))

    def test_optimized_extraction_retains_exact_pixels_and_limits_before_io(self):
        regions=optimized_tile_regions(self.image,(3,7,77,58),self.root/"optimized",
            tile_size=(32,24),overlap=8)
        for region in regions:
            with Image.open(region.image.path) as actual, self.source.crop(region.source_box) as expected:
                self.assertIsNone(ImageChops.difference(actual,expected).getbbox())
            self.assertEqual(region.map_box((0,0),(region.image.width,region.image.height)),
                             (region.source_box[:2],region.source_box[2:]))
        with self.assertRaisesRegex(RegionToolError,"more tiles"):
            optimized_tile_regions(self.image,(0,0,80,60),self.root/"too-many",
                tile_size=(20,20),overlap=5,max_tiles=2)
        self.assertFalse((self.root/"too-many").exists())
        with self.assertRaisesRegex(RegionToolError,"more tiles"):
            optimized_tile_boxes((0,0,1_000_000_000,1),1_000_000_000,1,
                tile_size=(1,1),overlap=0)

    def test_optimized_invalid_parameters_are_rejected(self):
        for kwargs in ({"slack_fraction":True},{"slack_fraction":-.1},{"slack_fraction":.6},
                       {"slack_fraction":float('nan')},{"slack_fraction":float('inf')},
                       {"max_tile_edge":1300},{"max_tile_edge":True},{"max_tile_edge":9000},
                       {"tile_size":(0,1400)},{"overlap":1400},{"max_tiles":0}):
            with self.subTest(kwargs=kwargs),self.assertRaises(RegionToolError):
                optimized_tile_boxes((0,0,80,60),80,60,**kwargs)


if __name__ == "__main__":
    unittest.main()
