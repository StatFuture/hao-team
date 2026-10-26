import copy, hashlib, json, shutil, tempfile, unittest
from pathlib import Path
from build import ROOT, build
from build_v2 import build_v2

class VersionTwoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hao-v2-test-', dir=ROOT.parent)
        self.root = Path(self.temp.name) / 'project'
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns('_site', '__pycache__', '.git'))
        self.v2 = self.root / 'versions/v2'
        for name in ('lab.json','admissions.json'):
            (self.v2/'data'/name).unlink(missing_ok=True)
        # Tests operate on controlled fixtures, never assume the editor's lists are empty.
        for folder in [self.root / 'content', self.v2 / 'content']:
            for record in folder.rglob('*.json'):
                assert record.resolve().is_relative_to(self.root.resolve())
                record.unlink()
        self.write('content/projects/projects-001.json',
                   {'title':'Baseline project','fields':[],'order':1,'published':True})
        self.write('versions/v2/data/settings.json', {'pageSize':'10','slides':[]})
    def tearDown(self):
        self.temp.cleanup()
    def write(self, path, obj):
        path = self.root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
    def data(self):
        build_v2(self.root)
        text = (self.root / '_site/v2/assets/data.js').read_text(encoding='utf-8')
        return json.loads(text.removeprefix('window.SITE_DATA = ').rstrip(';\n'))
    def test_first_version_output_is_unchanged(self):
        build(self.root)
        before = {str(p.relative_to(self.root / '_site')): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (self.root / '_site').rglob('*') if p.is_file()}
        build_v2(self.root)
        for name, digest in before.items():
            self.assertEqual(hashlib.sha256((self.root / '_site' / name).read_bytes()).hexdigest(), digest)
    def test_carousel_first_frame_does_not_wait_for_scripts(self):
        from PIL import Image
        from bs4 import BeautifulSoup
        image = self.root / 'media/images/first-frame.png'
        image.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (1800, 900), 'navy').save(image)
        self.write('versions/v2/data/settings.json', {'slides':[
            {'image':'media/images/first-frame.png','published':True,'order':10},
            {'image':'media/images/missing.png','published':False}]})
        data = self.data()
        slide = data['settings']['slides'][0]
        self.assertTrue(slide['preview'].startswith('data:image/webp;base64,'))
        self.assertLess(len(slide['preview']), 16000)
        for key, width in [('image',1440),('imageSmall',768)]:
            with Image.open(self.root / '_site/v2' / slide[key]) as img:
                self.assertEqual(img.width, width)
        document = BeautifulSoup((self.root / '_site/v2/index.html').read_text(encoding='utf-8'),'html.parser')
        self.assertEqual(document.select_one('main .hero img')['src'], slide['image'])
        self.assertEqual(document.select_one('main .hero img')['fetchpriority'], 'high')
        self.assertEqual(document.select_one('link[as=image]')['href'], slide['image'])
        self.assertIn(slide['preview'], document.select_one('main .hero')['style'])
    def test_version_specific_isolation_and_hidden_drafts(self):
        self.write('content/news/only-v1.json', {'title':'V1 ONLY', 'published':True})
        self.write('versions/v2/content/news/only-v2.json', {'title':'V2 ONLY', 'published':True})
        self.write('versions/v2/content/news/draft.json', {'title':'SECRET DRAFT', 'published':False})
        data = self.data()
        self.assertEqual([x['title'] for x in data['collections']['news']], ['V2 ONLY'])
    def test_shared_profile_is_live_not_a_frozen_copy(self):
        path = self.root / 'data/profile.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['directions'] = ['Changed shared direction']
        self.write('data/profile.json', data)
        self.assertEqual(self.data()['profile']['directions'], ['Changed shared direction'])
    def test_override_does_not_change_shared_record(self):
        original = (self.root / 'content/projects/projects-001.json').read_bytes()
        self.write('versions/v2/content/overrides/test.json', {'title':'override','collection':'projects',
                   'recordId':'projects-001','body':'V2 extra','order':0,'published':True})
        self.assertEqual(self.data()['collections']['projects'][0]['body'], 'V2 extra')
        self.assertEqual((self.root / 'content/projects/projects-001.json').read_bytes(), original)
    def test_duplicate_or_missing_override_fails(self):
        self.write('versions/v2/content/overrides/test.json', {'title':'override','collection':'projects',
                   'recordId':'missing','published':True})
        with self.assertRaises(ValueError): self.data()
    def test_media_optimized_and_missing_media_rejected(self):
        from PIL import Image
        path = self.root / 'media/images/v2-test.png'
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB',(2400,1600),'navy').save(path)
        record = {'title':'media','published':True,'images':['media/images/v2-test.png']}
        self.write('versions/v2/content/news/media.json', record)
        image = self.data()['collections']['news'][0]['images'][0]
        with Image.open(self.root / '_site/v2' / image) as im: self.assertLessEqual(im.width, 1600)
        record['images'] = ['media/images/missing.png']
        self.write('versions/v2/content/news/media.json', record)
        with self.assertRaises(ValueError): self.data()
    def test_dangerous_url_and_oversize_rejected(self):
        record = {'title':'bad link','published':True,'link':'javascript:alert(1)'}
        self.write('versions/v2/content/resources/bad.json', record)
        with self.assertRaises(ValueError): self.data()
        record.pop('link'); record['video']='media/videos/large.webm'
        path=self.root/record['video'];path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('wb') as f: f.truncate(20*1024*1024+1)
        self.write('versions/v2/content/resources/bad.json', record)
        with self.assertRaises(ValueError): self.data()
    def test_large_records_order_and_no_draft_leak(self):
        for i in range(1001):
            self.write(f'versions/v2/content/news/news-{i:04}.json',
                       {'title':f'News {i}', 'order':i,'published':True,'pinned':i==1000})
        records = self.data()['collections']['news']
        self.assertEqual(len(records), 1001)
        self.assertEqual(records[0]['title'], 'News 1000')
        self.assertEqual(records[1]['title'], 'News 0')
    def test_invalid_page_size_rejected(self):
        path=self.v2/'data/settings.json';data=json.loads(path.read_text(encoding='utf-8'))
        data['pageSize']=0;self.write('versions/v2/data/settings.json',data)
        with self.assertRaises(ValueError): self.data()
    def test_release_data_has_a_new_cache_key_after_edits(self):
        self.data()
        from bs4 import BeautifulSoup
        page = self.root/'_site/v2/index.html'
        before = BeautifulSoup(page.read_text(encoding='utf-8'),'html.parser').select_one('script[src*=data]')['src']
        self.write('versions/v2/content/news/new.json',{'title':'New release','published':True})
        self.data()
        after = BeautifulSoup(page.read_text(encoding='utf-8'),'html.parser').select_one('script[src*=data]')['src']
        self.assertNotEqual(before, after)

    def test_independent_team_research_works_with_shared_records_disabled(self):
        self.write('versions/v2/data/settings.json', {'pageSize':10, 'slides':[],
                   'showSharedResearch':False, 'showPersonalProfile':False})
        shared_before = (self.root/'content/projects/projects-001.json').read_bytes()
        self.write('versions/v2/content/projects/team-example.json',
                   {'title':'Team project','published':True,'researchArea':'Optics','contributors':'Member A'})
        self.write('versions/v2/content/projects/draft.json', {'title':'PRIVATE','published':False})
        data = self.data()
        self.assertEqual([x['title'] for x in data['collections']['projects']], ['Team project'])
        self.assertEqual(data['collections']['projects'][0]['id'], 'team-team-example')
        self.assertNotIn('overview', data['profile'])
        self.assertEqual((self.root/'content/projects/projects-001.json').read_bytes(), shared_before)

    def test_team_and_shared_slugs_do_not_collide(self):
        self.write('versions/v2/content/projects/projects-001.json',
                   {'title':'Independent','published':True})
        records = self.data()['collections']['projects']
        self.assertEqual(len(records),2)
        self.assertEqual(len({x['id'] for x in records}),2)

    def test_layout_demo_switch_preserves_real_content(self):
        self.write('versions/v2/data/settings.json', {'pageSize':10,'slides':[],
                   'showSharedResearch':False,'showPersonalProfile':False,'labIntro':'Real introduction'})
        self.write('versions/v2/data/layout-demo.json', {'labIntro':'DEMO introduction'})
        self.write('versions/v2/content/news/real.json', {'title':'Real news','published':True})
        self.write('versions/v2/content/news/demo.json', {'title':'DEMO news','published':True,'layoutDemo':True})
        data = self.data()
        self.assertEqual([x['title'] for x in data['collections']['news']], ['Real news'])
        self.assertEqual(data['settings']['labIntro'], 'Real introduction')
        settings = json.loads((self.v2/'data/settings.json').read_text(encoding='utf-8'))
        settings['demoMode'] = True
        self.write('versions/v2/data/settings.json', settings)
        data = self.data()
        self.assertEqual(len(data['collections']['news']), 2)
        self.assertEqual(data['settings']['labIntro'], 'DEMO introduction')
        self.assertEqual(json.loads((self.v2/'data/settings.json').read_text(encoding='utf-8'))['labIntro'], 'Real introduction')

    def test_demo_slides_follow_demo_switch(self):
        from PIL import Image
        path = self.root/'media/images/carousel-test.png'
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB',(200,100),'navy').save(path)
        settings = {'pageSize':10,'demoMode':False,'slides':[
                    {'image':'media/images/carousel-test.png','published':True,'layoutDemo':True}]}
        self.write('versions/v2/data/settings.json', settings)
        self.assertEqual(self.data()['settings']['slides'], [])
        settings['demoMode'] = True
        self.write('versions/v2/data/layout-demo.json', {})
        self.write('versions/v2/data/settings.json', settings)
        self.assertEqual(len(self.data()['settings']['slides']),1)

    def test_member_names_and_additional_personal_chapters(self):
        self.write('versions/v2/content/members/member.json', {'name':'Member Name','published':True,
                   'sections':[{'title':'Books','kind':'books'},{'title':'Patents','kind':'patents'}]})
        for kind in ('projects','papers','patents','books','awards'):
            self.write('versions/v2/content/'+kind+'/item.json', {'title':kind,'published':True,
                       'memberRefs':['versions/v2/content/members/member.json']})
        data=self.data()
        for kind in ('projects','papers','patents','books','awards'):
            item=next(x for x in data['collections'][kind] if x['id']=='team-item')
            self.assertEqual(item['contributors'],'Member Name')
        self.assertEqual([x['kind'] for x in data['collections']['members'][0]['renderedSections']],['books','patents'])

    def test_resources_have_independent_location(self):
        self.write('versions/v2/content/resources/guide.json', {'title':'Reading Guide','published':True,
                   'target':'lab','position':'before'})
        record=self.data()['collections']['resources'][0]
        self.assertEqual(record['target'],'resources')
        self.assertNotIn('position',record)

    def test_normal_dates_ignore_manual_sequence_and_unknown_goes_last(self):
        for ident,fields in [('new',{'date':'2026-10-26','order':99}),
                             ('old',{'date':'2025-01-01','order':1}),
                             ('unknown',{'order':0})]:
            self.write('versions/v2/content/resources/'+ident+'.json',dict(title=ident,published=True,**fields))
        self.assertEqual([v['title'] for v in self.data()['collections']['resources']],['new','old','unknown'])

    def test_pins_use_sequence_before_date(self):
        records=[('normal',{'date':'2026-10-26'}),('first',{'date':'2010-01-01','pinned':True,'order':1}),
                 ('second',{'date':'2025-01-01','pinned':True,'order':2}),
                 ('zero',{'date':'2000-01-01','pinned':True,'order':0})]
        for ident,fields in records:self.write('versions/v2/content/projects/'+ident+'.json',dict(title=ident,published=True,**fields))
        rows=[x for x in self.data()['collections']['projects'] if x['id'].startswith('team-')]
        self.assertEqual([x['title'] for x in rows],['zero','first','second','normal'])

    def test_paper_year_and_personal_list_have_same_priority(self):
        for ident,fields in [('new',{'year':2026,'order':99}),('old',{'year':2024,'order':1}),
                             ('pinned',{'year':2010,'pinned':True,'order':2}),('unknown',{})]:
            self.write('versions/v2/content/papers/'+ident+'.json',dict(title=ident,published=True,**fields))
        rows=self.data()['collections']['papers']
        self.assertEqual([x['title'] for x in rows],['pinned','new','old','unknown'])
        self.assertEqual(rows[1]['sortDate'],20260000)

    def test_member_sequence_still_uses_one_two_three(self):
        for ident,order in [('third',3),('first',1),('second',2)]:
            self.write('versions/v2/content/members/'+ident+'.json',{'name':ident,'published':True,'order':order})
        self.assertEqual([x['name'] for x in self.data()['collections']['members']],['first','second','third'])

    def test_invalid_calendar_date_rejected(self):
        self.write('versions/v2/content/resources/invalid.json',{'title':'Invalid','published':True,'date':'2026-02-30'})
        with self.assertRaises(ValueError):self.data()

    def test_draft_save_has_no_automatic_preview_workflow(self):
        import re
        self.assertFalse((self.root/'.github/workflows/draft-preview.yml').exists())
        for p in (self.root/'.github/workflows').glob('*.yml'):
            match=re.search(r'(?ms)^on:\n(.*?)(?=^\S|\Z)',p.read_text(encoding='utf8'))
            trigger=match.group(1) if match else ''
            self.assertNotRegex(trigger,r'branches:\s*\[[^\]]*\bdrafts\b')

if __name__ == '__main__': unittest.main()

