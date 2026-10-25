import hashlib, json, tempfile, unittest
from pathlib import Path
from preview_site import assemble

class PreviewTests(unittest.TestCase):
    def test_preview_is_isolated_and_copies_real_runtime(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as d:
            root=Path(d);prod=root/'formal';draft=root/'draft';prod.mkdir();draft.mkdir()
            (prod/'index.html').write_text('FORMAL',encoding='utf-8')
            (draft/'index.html').write_text('<html><head><title>Draft</title></head><body>NEW</body></html>',encoding='utf-8')
            (draft/'assets').mkdir();(draft/'assets/site.js').write_text('LIVE CODE',encoding='utf-8')
            template=root/'preview.html';template.write_text('VIEWER',encoding='utf-8')
            before=hashlib.sha256((prod/'index.html').read_bytes()).hexdigest()
            assemble(prod,draft,template,'draft-sha','main-sha')
            self.assertEqual(hashlib.sha256((prod/'index.html').read_bytes()).hexdigest(),before)
            self.assertEqual((prod/'preview/site/assets/site.js').read_text(),'LIVE CODE')
            self.assertIn('noindex,nofollow',(prod/'preview/site/index.html').read_text(encoding='utf-8'))
            self.assertEqual(json.loads((prod/'preview/manifest.json').read_text())['draftSha'],'draft-sha')
            assemble(prod,draft,template,'next-draft','main-sha')
            self.assertFalse((prod/'preview/site/preview').exists())
    def test_refuses_overlapping_paths(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as d:
            root=Path(d);(root/'index.html').write_text('x')
            with self.assertRaises(ValueError):assemble(root,root,root/'index.html','x','y')

if __name__=='__main__':unittest.main()
