"""Build checks use an isolated copy; synthetic records are never published."""
import unittest,tempfile,shutil,json,sys
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).parent));from build import build,ROOT
class BuildTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix="qa-",dir=ROOT);self.root=Path(self.temp.name)/'repo';self.root.mkdir()
  for name in ['assets','media','templates','data','content']:shutil.copytree(ROOT/name,self.root/name)
  profile_path=self.root/'data/profile.json';profile=json.loads(profile_path.read_text(encoding='utf-8'));profile['pageSize']=10;profile_path.write_text(json.dumps(profile,ensure_ascii=False),encoding='utf-8')
  # Tests must not depend on the number of records maintained by real editors.
  for folder in (self.root/'content').iterdir():
   for record in folder.glob('*.json'):
    assert record.resolve().is_relative_to(self.root.resolve())
    record.unlink()
  for i in range(12):self.put('papers',f'baseline-{i:02}',dict(title=f'Test paper {i}',citation=f'Test citation {i}',doi='',link='',published=True,order=i))
 def tearDown(self):
  assert Path(self.temp.name).resolve().is_relative_to(ROOT.resolve())
  self.temp.cleanup()
 def put(self,key,name,record):
  (self.root/'content'/key/(name+'.json')).write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8')
 def page(self):
  build(self.root);return BeautifulSoup((self.root/'_site/index.html').read_text(encoding='utf-8'),'html.parser')
 def test_original_data_and_small_initial_page(self):
  doc=self.page();data=json.loads(doc.select_one('#cms-page-data').string)
  self.assertEqual(len(data['groups']['papers']),12);self.assertEqual(len(doc.select('.publications > li')),10)
  self.assertFalse((self.root/'_site/content').exists());self.assertFalse((self.root/'_site/.pages.yml').exists())
  self.assertLess((self.root/'_site/index.html').stat().st_size,60000)
  self.assertEqual([t.get_text(strip=True) for t in doc.select('#tabs [role=tab]')],['个人资料','个人概况','研究领域','科研项目','成果与荣誉','招生信息','团队展示'])
  self.assertFalse(doc.select('#tab-news, #tab-resources, #news, #resources'))
 def test_many_records_order_and_unpublished_exclusion(self):
  for i in range(1000):self.put('projects',f'n{i:04}',dict(title=f'QA-{i}',fields=[],published=True,order=i+1))
  self.put('projects','draft',dict(title='PRIVATE-DRAFT-MARKER',published=False,order=0))
  self.put('projects','first',dict(title='FIRST',fields=[],published=True,order=0))
  doc=self.page();data=json.loads(doc.select_one('#cms-page-data').string)
  self.assertEqual(len(data['groups']['projects']),1001);self.assertEqual(len(doc.select('#projects .block')),10)
  self.assertEqual(doc.select_one('#projects h2').text,'FIRST');self.assertNotIn('PRIVATE-DRAFT-MARKER',str(doc))
 def test_spare_news_does_not_change_original_navigation(self):
  self.put('news','spare',dict(title='SPARE-NEWS-NOT-IN-V18',body='retained only in CMS',published=True,order=1))
  self.put('resources','spare',dict(title='SPARE-RESOURCE-NOT-IN-V18',target='resources',published=True,order=1))
  doc=self.page();self.assertNotIn('SPARE-NEWS-NOT-IN-V18',str(doc));self.assertNotIn('SPARE-RESOURCE-NOT-IN-V18',str(doc))
  self.assertEqual(len(doc.select('#tabs [role=tab]')),7)
 def test_safe_text_attachment_and_missing_file(self):
  self.put('resources','text',dict(title='<img src=x onerror=alert(1)>',body='<script>BAD()</script>',target='research',published=True,order=1))
  doc=self.page();self.assertFalse(doc.select('#research script'));self.assertIn('<script>BAD()</script>',doc.select_one('#research').text)
  self.put('resources','bad',dict(title='bad',published=True,target='research',attachment='../../outside.pdf'))
  with self.assertRaises(ValueError):self.page()
 def test_dangerous_url_rejected(self):
  self.put('members','bad',dict(name='bad',published=True,link='javascript:alert(1)'))
  with self.assertRaises(ValueError):self.page()
 def test_resource_position_and_media(self):
  (self.root/'media/files/test.pdf').write_bytes(b'%PDF-1.4\n%QA only')
  self.put('resources','r',dict(title='POSITION-MARKER',published=True,target='research',position='before',attachment='media/files/test.pdf'))
  doc=self.page();self.assertEqual(doc.select_one('#research > section h3').text,'POSITION-MARKER');self.assertTrue(doc.select_one('#research a[href="media/files/test.pdf"]'))
 def test_profile_updates_all_repeated_locations(self):
  file=self.root/'data/profile.json';profile=json.loads(file.read_text(encoding='utf-8-sig'));profile['directions']=['UPDATED-DIRECTION-QA']
  for row in profile['profile']:
   if '邮箱' in row['label']:row['value']='qa-update@example.org'
   if row['label'].strip('：: ')=='姓名':row['value']='QA-NAME'
  file.write_text(json.dumps(profile,ensure_ascii=False),encoding='utf-8');doc=self.page()
  for selector in ['#profile .plain-list','#research .plain-list','#admission .plain-list','aside .aside-bottom']:
   self.assertIn('UPDATED-DIRECTION-QA',doc.select_one(selector).get_text())
  for selector in ['#profile','aside','#admission']:
   self.assertTrue(doc.select_one(selector+' a[href="mailto:qa-update@example.org"]'))
  self.assertIn('QA-NAME',doc.title.get_text());self.assertEqual(doc.footer.get_text(strip=True),'版权所有 © 天津商业大学')
if __name__=='__main__':unittest.main()
