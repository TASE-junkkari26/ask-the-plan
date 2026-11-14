"""Offline ROI invariants; these do not establish window detection accuracy."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from image_api import window_regions as regions


CV2 = regions._cv2()


class WindowRegionInputTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "source.png"
        with Image.new("RGB", (320,320), "white") as image:
            image.save(self.path)

    def test_missing_optional_dependency_returns_no_proposals(self):
        with patch.object(regions,"_cv2",return_value=None):
            self.assertEqual(regions.propose_window_regions(self.path), ())
            self.assertEqual(regions.find_solid_window_boxes(self.path,[(10,10,20,40)]), ())

    def test_invalid_bounds_and_limits_are_rejected(self):
        for box in ((0,0,0,5),(-1,0,20,20),(0,0,321,20),(0.,0,20,20),(False,0,20,20)):
            with self.subTest(box=box), self.assertRaises(ValueError):
                regions.propose_window_regions(self.path,source_box=box)
        for limit in (-1,3,True,1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                regions.propose_window_regions(self.path,max_regions=limit)
        for boxes in ([(0,0,float("nan"),10)],[(0,0,321,20)],[(False,0,20,20)],[(0,0,20,20)]*101):
            with self.subTest(boxes=boxes[:1]), self.assertRaises(ValueError):
                regions.propose_window_regions(self.path,existing_boxes=boxes)
        self.assertEqual(regions.propose_window_regions(self.path,max_regions=0), ())

    def test_input_byte_and_pixel_limits_precede_decoding_work(self):
        with patch.object(regions,"MAX_SOURCE_BYTES",1), self.assertRaises(ValueError):
            regions.propose_window_regions(self.path)
        with patch.object(regions,"MAX_SOURCE_PIXELS",100), self.assertRaises(ValueError):
            regions.propose_window_regions(self.path)

    def test_rotated_or_multiple_frames_are_not_silently_reframed(self):
        with Image.new("RGB",(100,100),"white") as image:
            exif=Image.Exif(); exif[274]=6
            image.save(self.path,exif=exif)
        with self.assertRaises(ValueError):
            regions.propose_window_regions(self.path)
        with Image.new("RGB",(100,100),"white") as first, Image.new("RGB",(100,100),"black") as second:
            first.save(self.path,format="PNG",save_all=True,append_images=[second])
        with self.assertRaises(ValueError):
            regions.propose_window_regions(self.path)


@unittest.skipIf(CV2 is None,"Optional OpenCV vision extra is not installed")
class WindowRegionVisionTests(unittest.TestCase):
    setUp = WindowRegionInputTests.setUp
    def draw_frame(self, *, size=(320,320), x=140, top=60, bottom=240, colour="black", background="white"):
        with Image.new("RGB",size,background) as image:
            draw=ImageDraw.Draw(image)
            for offset in (0,5,10):
                draw.line((x+offset,top,x+offset,bottom),fill=colour,width=1)
            image.save(self.path)

    def test_parallel_thin_lines_propose_context_but_solid_wall_does_not(self):
        self.draw_frame()
        proposals=regions.propose_window_regions(self.path)
        self.assertTrue(proposals)
        self.assertTrue(any(a<=145<c and b<=150<d for a,b,c,d in proposals))
        with Image.new("RGB",(320,320),"white") as image:
            ImageDraw.Draw(image).rectangle((140,60,157,240),fill="black")
            image.save(self.path)
        self.assertEqual(regions.propose_window_regions(self.path), ())

    def test_existing_window_context_is_excluded(self):
        self.draw_frame()
        self.assertEqual(regions.propose_window_regions(self.path,existing_boxes=[(135.,55.,155.,245.)]), ())

    def test_blank_dark_and_page_frame_do_not_create_an_inventory(self):
        for fill in ("white","black",(55,55,55),(225,235,240)):
            with self.subTest(fill=fill), Image.new("RGB",(320,320),fill) as image:
                image.save(self.path)
                self.assertEqual(regions.propose_window_regions(self.path), ())
        with Image.new("RGB",(320,320),"white") as image:
            ImageDraw.Draw(image).rectangle((8,8,312,312),outline="black",width=2)
            image.save(self.path)
        self.assertEqual(regions.propose_window_regions(self.path), ())

    def test_coloured_lines_over_room_fill_remain_inspectable(self):
        self.draw_frame(colour=(0,0,140),background=(225,235,240))
        self.assertTrue(regions.propose_window_regions(self.path))

    def test_source_crop_offset_bounds_determinism_and_source_preservation(self):
        self.draw_frame(size=(640,480),x=310,top=170,bottom=320)
        original=self.path.read_bytes()
        box=(200,100,500,400)
        first=regions.propose_window_regions(self.path,source_box=box)
        self.assertTrue(first)
        self.assertEqual(first,regions.propose_window_regions(self.path,source_box=box))
        # A known candidate entirely outside this panel must not mask the panel.
        self.assertEqual(first,regions.propose_window_regions(self.path,source_box=box,existing_boxes=[(0,0,80,80)]))
        for a,b,c,d in first:
            self.assertTrue(all(type(v) is int for v in (a,b,c,d)))
            self.assertTrue(200<=a<c<=500 and 100<=b<d<=400)
            self.assertLessEqual(max(c-a,d-b),regions.MAX_REGION_EDGE)
            self.assertLessEqual((c-a)*(d-b),.4*300*300)
        self.assertEqual(self.path.read_bytes(),original)

    def test_analysis_never_exceeds_edge_limit_or_upscales(self):
        for size in ((5000,400),(320,320)):
            with self.subTest(size=size), Image.new("RGB",size,"white") as image:
                image.save(self.path)
                with patch.object(CV2,"GaussianBlur",wraps=CV2.GaussianBlur) as blur:
                    regions.propose_window_regions(self.path)
                    actual=blur.call_args.args[0].shape
                self.assertLessEqual(max(actual),regions.ANALYSIS_EDGE)
                self.assertLessEqual(actual[0],size[1])
                self.assertLessEqual(actual[1],size[0])

    def test_two_region_budget_is_enforced_for_separated_structures(self):
        with Image.new("RGB",(640,480),"white") as image:
            draw=ImageDraw.Draw(image)
            for x,top,bottom in ((120,40,160),(420,280,420)):
                for offset in (0,5,10):
                    draw.line((x+offset,top,x+offset,bottom),fill="black",width=1)
            image.save(self.path)
        self.assertEqual(len(regions.propose_window_regions(self.path,max_regions=2)),2)
        self.assertEqual(len(regions.propose_window_regions(self.path,max_regions=1)),1)

    def test_solid_wall_flags_do_not_flag_bright_frame_channels_or_thin_glazing(self):
        with Image.new("RGB",(500,220),"white") as image:
            draw=ImageDraw.Draw(image)
            draw.rectangle((20,30,32,170),fill="black")
            for x in (120,124,128):
                draw.line((x,30,x,170),fill="black")
            draw.rectangle((220,30,223,170),fill="black")
            draw.rectangle((340,30,380,170),fill="black")
            # A narrow but continuous bright frame channel must survive even
            # though the surrounding box is over92% dark.
            draw.line((360,30,360,170),fill="white")
            image.save(self.path)
        boxes=[(20.,30.,33.,171.),(118,28,132,173),(220,30,224,171),(340,30,381,171)]
        original=list(boxes)
        self.assertEqual(regions.find_solid_window_boxes(self.path,boxes),(0,))
        self.assertEqual(boxes,original)

    def test_quality_check_opens_once_and_preserves_original_indices(self):
        with Image.new("RGB",(320,320),"white") as image:
            ImageDraw.Draw(image).rectangle((140,60,158,240),fill="black")
            image.save(self.path)
        with patch.object(regions.Image,"open",wraps=Image.open) as opened:
            result=regions.find_solid_window_boxes(self.path,[(10,10,30,40),(140,60,159,241)])
        self.assertEqual(result,(1,))
        self.assertEqual(opened.call_count,1)

    def test_quality_check_bounds_and_source_limits(self):
        for boxes in ([(0,0,float("nan"),10)],[(0,0,321,20)],[(False,0,20,20)],[(0,0,20,20)]*101):
            with self.subTest(boxes=boxes[:1]), self.assertRaises(ValueError):
                regions.find_solid_window_boxes(self.path,boxes)
        with patch.object(regions,"MAX_SOURCE_PIXELS",100), self.assertRaises(ValueError):
            regions.find_solid_window_boxes(self.path,[(10,10,30,60)])
        with patch.object(regions,"MAX_SOURCE_BYTES",1), self.assertRaises(ValueError):
            regions.find_solid_window_boxes(self.path,[(10,10,30,60)])
        self.assertEqual(regions.find_solid_window_boxes(self.path,[]),())


if __name__=="__main__":
    unittest.main()
