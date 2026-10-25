"""Generate the static public site from CMS JSON. No runtime database or browser fetch."""
from pathlib import Path
from html import escape
from urllib.parse import urlsplit
import argparse,json,shutil,hashlib
from bs4 import BeautifulSoup
from PIL import Image,ImageOps
ROOT=Path(__file__).resolve().parents[1]
PAGE=10
E=lambda s:escape(str(s or ''),quote=True)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def records(root,key):
 items=[]
 for p in sorted((root/'content'/key).glob('*.json')):
  v=read(p)
  if not isinstance(v,dict):raise ValueError(f'{p.name}: record must be an object')
  if v.get('published') is True:
   v=dict(v);v['_id']=p.stem
   if not str(v.get('title',v.get('name',''))).strip():raise ValueError(f'{p.name}: missing title/name')
   items.append(v)
 def order(v):
  n=v.get('order',99999)
  if isinstance(n,bool) or not isinstance(n,(int,float)):raise ValueError('order must be a number')
  return n
 items.sort(key=lambda v:str(v.get('date','')),reverse=True)
 items.sort(key=lambda v:(not bool(v.get('pinned')),order(v)))
 return items
class Builder:
 def __init__(self,root,dest):self.root=root;self.dest=dest;self.payload={};self.image_cache={}
 def source(self,value):
  value=str(value or '').strip()
  if not value:return ''
  parts=urlsplit(value)
  if parts.scheme:
   if parts.scheme not in ['http','https'] or not parts.netloc or parts.username:raise ValueError('Only http(s) links are allowed')
   return value
  if parts.netloc or value.startswith(('/', '\\')) or '\\' in value or parts.query or parts.fragment:raise ValueError('Invalid local asset path')
  if not value.startswith(('media/','assets/')):raise ValueError('Assets must live under media/ or assets/')
  p=(self.root/value).resolve()
  if not p.is_relative_to(self.root.resolve()) or not p.is_file():raise ValueError(f'Missing asset: {value}')
  limit=20 if p.suffix.lower() in ['.mp4','.webm'] else 10
  if p.stat().st_size>limit*1024*1024:raise ValueError(f'{value}: file exceeds {limit} MB trial limit')
  return value
 def image(self,path,alt='',portrait=False):
  value=self.source(path)
  if not value:return ''
  attrs=''
  if not urlsplit(value).scheme:
   if value not in self.image_cache:
    with Image.open(self.root/value) as im:
     if im.format not in ['PNG','JPEG','WEBP']:raise ValueError('Only PNG/JPEG/WebP images are accepted')
     im=ImageOps.exif_transpose(im);im.thumbnail((1600,1600));w,h=im.size
     filename='assets/image-'+hashlib.sha256((self.root/value).read_bytes()).hexdigest()[:16]+'.webp'
     im.save(self.dest/filename,'WEBP',quality=88,method=4)
     self.image_cache[value]=(filename,w,h)
   value,w,h=self.image_cache[value];attrs=f' width="{w}" height="{h}"'
  return f'<img src="{E(value)}" alt="{E(alt)}" loading="lazy" decoding="async"{attrs}>'
 def link(self,url,label):
  value=self.source(url)
  return f'<a href="{E(value)}" target="_blank" rel="noopener noreferrer">{E(label)}</a>' if value else ''
 def media(self,v):
  html=''
  images=v.get('images') or []
  if not isinstance(images,list):raise ValueError('images must be a list')
  for im in images:html+='<figure class="cms-figure">'+self.image(im,v.get('title',''))+'</figure>'
  video=self.source(v.get('video') or v.get('videoUrl',''))
  if video:
   if urlsplit(video).path.lower().endswith(('.mp4','.webm')):
    poster=self.source(v.get('poster'))
    if poster and not urlsplit(poster).scheme:self.image(poster);poster=self.image_cache[poster][0]
    html+=f'<video class="cms-video" controls playsinline preload="none"'+(f' poster="{E(poster)}"' if poster else '')+f' src="{E(video)}">'+self.link(video,'打开视频')+'</video>'
   else:html+='<p>'+self.link(video,'打开视频播放页面')+'</p>'
  if v.get('attachment'):html+='<p class="cms-attachment">'+self.link(v['attachment'],'下载资料附件')+'</p>'
  return html
 def paragraphs(self,text):return ''.join('<p class="prose cms-text">'+E(t)+'</p>' for t in str(text or '').split('\n\n') if t.strip())
 def fields(self,rows):
  def display(v):
   text=E(v['value'])
   return '<a href="mailto:'+text+'">'+text+'</a>' if '邮箱' in v['label'] and text else text
  return '<dl class="fields">'+''.join('<div><dt>'+E(v['label'])+'</dt><dd>'+display(v)+'</dd></div>' for v in rows)+'</dl>'
 def item(self,key,v,i):
  text=self.paragraphs
  if key=='papers':
   citation=E(v['citation']).replace('Zhiqiang Hao','<strong>Zhiqiang Hao</strong>').replace('郝志强','<strong>郝志强</strong>')
   link=self.link(v.get('link'),v.get('doi') or '论文页面')
   return f'<li value="{i+1}"><p class="citation">{citation}</p>'+('<span>'+link+'</span>' if link else '')+'</li>'
  if key=='projects':return '<section class="block"><h2>'+E(v['title'])+'</h2>'+self.fields(v.get('fields',[]))+'</section>'
  if key=='books':return '<div class="book-record">'+self.fields(v.get('fields',[]))+'</div>'
  if key=='patents':return '<section class="entry"><h3>'+E(v['title'])+'</h3>'+''.join('<p>'+E(t)+'</p>' for t in v.get('lines',[]))+'</section>'
  if key=='awards':return text(v['text'])
  if key=='members':
   return '<section class="cms-member">'+(self.image(v['photo'],v['name'],True) if v.get('photo') else '')+'<h3>'+E(v['name'])+'</h3><p>'+E(v.get('role'))+'</p>'+text(v.get('bio'))+('<p><a href="mailto:'+E(v['email'])+'">'+E(v['email'])+'</a></p>' if v.get('email') else '')+('<p>'+self.link(v['link'],'个人主页')+'</p>' if v.get('link') else '')+'</section>'
  if key in ['news','resources']:
   return '<section class="cms-record"><h3>'+E(v['title'])+'</h3>'+('<p class="cms-date">'+E(v.get('date'))+'</p>' if key=='news' else '')+text(v.get('summary'))+text(v.get('body'))+self.media(v)+'</section>'
  raise ValueError(key)
 def paged(self,key,items,tag='div'):
  rendered=[self.item(key,v,i) for i,v in enumerate(items)];self.payload[key]=rendered
  first=''.join(rendered[:PAGE]) or '<p class="prose">暂无公开内容。</p>'
  klass='publications' if tag=='ol' else ('cms-members' if key=='members' else 'cms-list')
  return f'<{tag} class="{klass}" data-cms-list="{key}">{first}</{tag}>'
 def build(self):
  global PAGE
  profile=read(self.root/'data/profile.json');PAGE=int(profile.get('pageSize',10))
  if PAGE not in [10,20,50]:raise ValueError('pageSize must be 10, 20 or 50')
  doc=BeautifulSoup((self.root/'templates/v16.html').read_text(encoding='utf-8'),'html.parser')
  def sethtml(n,html):
   n.clear();f=BeautifulSoup(html,'html.parser')
   for c in list(f.contents):n.append(c)
  def block(panel,title):return next(n for n in doc.select('#'+panel+' .block') if n.h2 and n.h2.get_text(strip=True)==title)
  def body(n,html):
   for c in list(n.children):
    if getattr(c,'name',None)!='h2':c.extract()
   f=BeautifulSoup(html,'html.parser')
   for c in list(f.contents):n.append(c)
  body(block('profile','个人资料'),self.fields(profile['profile']));body(block('profile','指导研究生专业'),self.fields(profile['programs']));body(block('overview','个人简介'),self.paragraphs(profile['overview']))
  body(block('research','研究领域'),'<ul class="plain-list">'+''.join('<li>'+E(x)+'</li>' for x in profile['directions'])+'</ul>')
  body(block('profile','研究领域'),'<ul class="plain-list">'+''.join('<li>'+E(x)+'</li>' for x in profile['directions'])+'</ul>')
  email=next((r['value'] for r in profile['profile'] if r['label'].strip('：: ')=='电子邮箱'),'')
  admission_rows=list(profile['programs'])
  if email and not any('邮箱' in r['label'] for r in admission_rows):admission_rows.append({'label':'联系邮箱：','value':email})
  body(block('admission','招生专业'),self.fields(admission_rows));body(block('admission','研究方向'),'<ul class="plain-list">'+''.join('<li>'+E(x)+'</li>' for x in profile['directions'])+'</ul>');body(block('admission','报考信息'),'<ul class="plain-list">'+''.join('<li>'+self.link(a['url'],a['label'])+'</li>' for a in profile['admissions'])+'</ul>')
  name=next((r['value'] for r in profile['profile'] if r['label'].strip('：: ')=='姓名'),'郝志强')
  if doc.title:doc.title.string=name+' · 教师个人主页'
  identity=doc.select_one('aside .identity');intro='<h1>'+E(name)+'</h1>'
  for label,short in [('专业技术职称','职称'),('工作单位','单位'),('学历','学历'),('电子邮箱','电子邮箱')]:
   value=next((r['value'] for r in profile['profile'] if r['label'].strip('：: ')==label),'');intro+='<p>'+short+'：'+('<a href="mailto:'+E(value)+'">'+E(value)+'</a>' if label=='电子邮箱' and value else E(value))+'</p>'
  sethtml(identity,intro);sethtml(doc.select_one('aside .aside-bottom'),'<p>研究领域</p><p>'+'<br>'.join(E(x) for x in profile['directions'])+'</p>')
  portrait=doc.select_one('aside .portrait');sethtml(portrait,self.image(profile.get('portrait'),name));portrait['aria-hidden']='false' if profile.get('portrait') else 'true'
  sethtml(doc.select_one('#projects'),self.paged('projects',records(self.root,'projects')))
  for key,title in [('papers','论文成果'),('patents','专利成果'),('books','出版教材'),('awards','获奖情况')]:body(block('results',title),self.paged(key,records(self.root,key),'ol' if key=='papers' else 'div'))
  members=records(self.root,'members')
  body(doc.select_one('#team .block'),self.paragraphs(profile.get('team'))+(self.paged('members',members) if members else ''))
  # First version follows the user's v18 navigation exactly.
  # News and standalone resources stay in CMS storage; they add no public tabs.
  for resource in records(self.root,'resources'):
   target=resource.get('target','resources')
   if target=='resources':continue
   if target not in ['profile','overview','research','projects','results','admission','team']:raise ValueError('Invalid resource target')
   content=BeautifulSoup(self.item('resources',resource,0),'html.parser');node=doc.select_one('#'+target)
   if resource.get('position')=='before':node.insert(0,content)
   else:node.append(content)
  # Externalize and optimize the existing header illustration without changing its composition.
  for img in doc.select('img[src]'):
   if img['src'].startswith('assets/original-'):
    new=BeautifulSoup(self.image(img['src'],img.get('alt','')),'html.parser').img;img['src']=new['src'];img['width']=new['width'];img['height']=new['height'];img['decoding']='async'
  for style in doc.select('style'):
   value=style.string or style.get_text()
   import re
   for asset in set(re.findall(r'assets/original-[a-z0-9]+\.png',value)):
    self.image(asset);value=value.replace(asset,self.image_cache[asset][0])
   style.string=value
  # Replace old behavior with the previously tested click/keyboard navigation.
  for script in list(doc.select('script')):script.decompose()
  css=doc.new_tag('link',rel='stylesheet',href='assets/cms.css');doc.head.append(css)
  data=doc.new_tag('script',id='cms-page-data',type='application/json');data.string=json.dumps({'pageSize':PAGE,'groups':self.payload},ensure_ascii=False,separators=(',',':')).replace('<','\\u003c');doc.body.append(data)
  for src in ['assets/navigation.js','assets/pagination.js']:
   script=doc.new_tag('script',src=src);script['defer']='';doc.head.append(script)
  for node in doc.select('script[src], link[href]'):
   attr='src' if node.name=='script' else 'href';asset=node.get(attr,'')
   if asset in ['assets/navigation.js','assets/pagination.js','assets/cms.css']:node[attr]=asset+'?v='+hashlib.sha256((self.dest/asset).read_bytes()).hexdigest()[:16]
  (self.dest/'index.html').write_text(str(doc),encoding='utf-8');(self.dest/'.nojekyll').write_text('')
  summary={'published':{k:len(v) for k,v in self.payload.items()},'indexBytes':(self.dest/'index.html').stat().st_size,'imageBytes':sum(p.stat().st_size for p in (self.dest/'assets').glob('image-*'))}
  (self.dest/'build-info.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');return summary

def build(root=ROOT,dest=None):
 root=Path(root).resolve();dest=Path(dest or root/'_site').resolve()
 if dest==root or dest in root.parents or not dest.is_relative_to(root):raise ValueError('Output must be a child directory of the project')
 dest.mkdir(parents=True,exist_ok=True)
 for child in dest.iterdir():
  if child.is_dir():shutil.rmtree(child)
  else:child.unlink()
 for folder in ['assets','media']:shutil.copytree(root/folder,dest/folder,dirs_exist_ok=True)
 b=Builder(root,dest);result=b.build()
 # Do not publish raw content files, CMS settings, source templates or draft JSON.
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out');args=p.parse_args();print(json.dumps(build(dest=args.out),ensure_ascii=False))
