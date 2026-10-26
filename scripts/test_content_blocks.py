import sys,unittest,tempfile,json,shutil
from pathlib import Path
from bs4 import BeautifulSoup
from content_blocks import compile_blocks,rich_html

class ContentTests(unittest.TestCase):
    def asset(self,value,image=False):
        if value.startswith(('javascript:','data:','//','../')): raise ValueError('Unsafe URL')
        return value.lstrip('/')
    def test_mixed_order_and_named_multiple_attachments(self):
        html,_=compile_blocks([
            {'type':'text','text':'<p>Before</p>'},
            {'type':'image','image':'media/a.png','caption':'Photo'},
            {'type':'text','text':'<p>Between</p>'},
            {'type':'video','video':'media/a.webm'},
            {'type':'file','file':'media/a.pdf','label':'First file'},
            {'type':'file','file':'media/b.pdf','label':'Second file'},
        ],self.asset)
        doc=BeautifulSoup(html,'html.parser')
        self.assertEqual([n['data-block-type'] for n in doc.select('.content-block')],['text','image','text','video','file','file'])
        self.assertIn('First file',doc.get_text());self.assertIn('Second file',doc.get_text())
        self.assertEqual(doc.select_one('video')['preload'],'none')
    def test_attachment_description_is_optional_plain_text(self):
        html,_=compile_blocks([{'type':'file','file':'media/a.pdf','label':'Guide','description':'Read this first\\n<script>alert(1)</script>'}],self.asset)
        doc=BeautifulSoup(html,'html.parser')
        self.assertEqual(doc.select_one('.content-attachment a')['href'],'media/a.pdf')
        self.assertIn('Read this first',doc.select_one('.attachment-description').get_text())
        self.assertIsNone(doc.find('script'))
        self.assertIsNotNone(doc.select_one('.attachment-description br'))
        self.assertEqual(doc.select_one('.attachment-description').find_previous('a').get_text(strip=True),'Guide↗')
        old,_=compile_blocks([{'type':'file','file':'media/a.pdf'}],self.asset)
        self.assertNotIn('attachment-description',old)
        blank,_=compile_blocks([{'type':'file','file':'media/a.pdf','description':'  '}],self.asset)
        self.assertNotIn('attachment-description',blank)
        with self.assertRaises(ValueError):
            compile_blocks([{'type':'file','file':'media/a.pdf','description':{'invalid':True}}],self.asset)
    def test_script_events_and_arbitrary_styles_are_removed(self):
        html=rich_html('<script>alert(1)</script><p onclick="x()" style="font-size:99px">Safe<img src="/media/a.png" onerror="x()"></p>',self.asset)
        self.assertNotIn('<script',html);self.assertNotIn('onclick',html);self.assertNotIn('onerror',html);self.assertNotIn('99px',html)
        self.assertEqual(BeautifulSoup(html,'html.parser').img['src'],'media/a.png')
    def test_unsafe_links_fail_before_publication(self):
        with self.assertRaises(ValueError):rich_html('<a href="javascript:alert(1)">Bad</a>',self.asset)
    def test_plain_text_and_line_breaks_stay_readable(self):
        html=rich_html('First\nline\n\nNext',self.asset)
        self.assertEqual(len(BeautifulSoup(html,'html.parser').select('p')),2)
        self.assertIn('<br>',html)
    def test_empty_blocks_do_not_create_empty_chapters(self):
        from content_blocks import compile_record
        value={'sections':[{'title':'Education','content':[{'type':'text','text':'<p></p>'}]}]}
        compile_record(value,self.asset)
        self.assertEqual(value['renderedSections'],[])
    def test_unknown_block_and_incorrect_content_fail(self):
        with self.assertRaises(ValueError):compile_blocks([{'type':'arbitrary'}],self.asset)
        with self.assertRaises(ValueError):compile_blocks('bad',self.asset)

if __name__=='__main__':unittest.main()
