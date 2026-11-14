"""Source/frame and missing-status checks for optional local OCR labels."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from contracts.models import OCRResult,OCRTextSpan
from image_api.config import ApiSettings
from image_api.images import prepare_image
from image_api.source_labels import read_source_labels,SourceLabels


class SourceLabelsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        with Image.new('RGB',(80,60),'white') as image, BytesIO() as stream:
            image.save(stream,format='PNG')
            self.image=prepare_image(stream.getvalue(),ApiSettings(),self.root)

    def word(self, text='08', box=(10,10,20,20), confidence=.95):
        return OCRTextSpan(id='word-1',text=text,frame_id='display:sha256:'+self.image.sha256,
                          bbox=box,confidence=confidence,engine='tesseract')

    def test_native_source_and_literal_word_are_preserved_without_paths(self):
        result=OCRResult(status='complete',engine='tesseract',spans=[self.word('121.A')])
        with patch('image_api.source_labels.tesseract_version',return_value='synthetic'), \
             patch('image_api.source_labels.recognize',return_value=result) as recognize:
            labels=read_source_labels(self.image)
        self.assertEqual(recognize.call_args.kwargs['frame_id'],'display:sha256:'+self.image.sha256)
        self.assertEqual(labels.ocr.spans[0].text,'121.A')
        self.assertNotIn(str(self.root),json.dumps(labels.to_metadata()))
        self.assertEqual(labels.source_sha256,self.image.sha256)

    def test_optional_engine_status_is_not_converted_to_complete_empty(self):
        for status in ('unavailable','failed','complete'):
            result=OCRResult(status=status,engine='tesseract',spans=[])
            with patch('image_api.source_labels.tesseract_version',return_value=None), \
                 patch('image_api.source_labels.recognize',return_value=result):
                self.assertEqual(read_source_labels(self.image).ocr.status,status)

    def test_source_mutation_is_rejected_before_ocr(self):
        self.image.path.write_bytes(b'changed')
        with patch('image_api.source_labels.recognize') as recognize:
            with self.assertRaisesRegex(ValueError,'hash'):
                read_source_labels(self.image)
            recognize.assert_not_called()

    def test_spatial_filter_keeps_original_ids_text_boxes_and_unknown_confidence(self):
        word=self.word(' 08 ',confidence=None)
        labels=SourceLabels(self.image.sha256,word.frame_id,80,60,
            OCRResult(status='complete',engine='tesseract',spans=[word]),0)
        self.assertEqual(labels.near((20,10,30,20)),())
        self.assertEqual(labels.near((20,10,30,20),padding=1),(word,))
        self.assertEqual(labels.near((0,0,80,60),min_confidence=.1),())
        self.assertEqual(labels.near((0,0,80,60))[0].text,' 08 ')

    def test_invalid_lookup_bounds_and_ocr_timeouts_reject(self):
        labels=SourceLabels(self.image.sha256,'frame',80,60,
            OCRResult(status='complete',engine='tesseract'),0)
        for box in ((-1,0,10,10),(0,0,81,60),(0,0,0,10),(float('nan'),0,10,10)):
            with self.assertRaises(ValueError):labels.near(box)
        for timeout in (0,-1,True,float('nan'),601):
            with self.assertRaises(ValueError):read_source_labels(self.image,timeout_seconds=timeout)


if __name__=='__main__':unittest.main()
