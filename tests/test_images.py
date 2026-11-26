import tempfile
from pathlib import Path
import shutil
import unittest
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from sea.images import compare_pixels,compare_stills,template_match,find_template,parse_ocr,read_text

class ImageTests(unittest.TestCase):
    def test_difference(self):
        a=np.zeros((64,64,3),dtype=np.uint8);b=a.copy();b[16:32,32:48]=255
        r,overlay=compare_pixels(a,b)
        self.assertEqual(r['changed_pixel_fraction'],.0625)
        self.assertEqual(r['change_box'],[.5,.25,.75,.5])
        self.assertEqual(overlay.shape,a.shape)

    def test_template(self):
        rng=np.random.default_rng(42)
        a=rng.integers(0,256,(48,64,3),dtype=np.uint8)
        b=a[12:24,20:34].copy()
        r=template_match(a,b,.99)
        self.assertEqual(len(r['matches']),1)
        self.assertEqual(r['matches'][0]['box'],[20/64,12/48,34/64,24/48])
        with self.assertRaises(ValueError):template_match(a,np.zeros((8,8,3),dtype=np.uint8))

    def test_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'a.png';b=Path(tmp)/'b.png';q=Path(tmp)/'q.png'
            x=np.random.default_rng(2).integers(0,256,(40,60,3),dtype=np.uint8)
            Image.fromarray(x).save(a);Image.fromarray(x).save(b)
            Image.fromarray(x[5:15,10:20]).save(q)
            self.assertEqual(compare_stills(a,b)[0]['changed_pixel_fraction'],0)
            self.assertEqual(len(find_template(a,q,.99)['matches']),1)

    def test_ocr_parser(self):
        raw=b'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t1\t1\t10\t20\t30\t10\t92.4\tSEA\n'
        r=parse_ocr(raw,100,100)
        self.assertEqual(r['text'],'SEA')
        self.assertEqual(r['words'][0]['box'],[.1,.2,.4,.3])

    @unittest.skipUnless(shutil.which('tesseract'),'Optional OCR provider not installed')
    def test_real_ocr(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'text.png'
            im=Image.new('RGB',(700,120),'white')
            ImageDraw.Draw(im).text((20,20),'SEA TEST 123',fill='black',font=ImageFont.load_default(size=50))
            im.save(p)
            r=read_text(p,'eng','line')
            self.assertIn('123',r['text'])
