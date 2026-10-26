"""Compile editor content into safe, asset-checked static HTML."""
from html import escape
from pathlib import PurePosixPath
from urllib.parse import urlsplit
from bs4 import BeautifulSoup, Comment
import re

TAGS = {'p','br','strong','b','em','i','u','s','h2','h3','h4','ul','ol','li',
        'blockquote','a','img','figure','figcaption','table','thead','tbody','tr','th','td','hr','sub','sup'}
DROP = {'script','style','iframe','object','embed','form','input','button','svg','math','template'}

def rich_html(value, asset):
    if not isinstance(value, str):
        raise ValueError('Formatted text must be a string')
    if not re.search(r'<[a-zA-Z][^>]*>', value):
        return ''.join('<p>'+escape(p).replace('\n','<br>')+'</p>' for p in re.split(r'\n\s*\n',value.strip()) if p.strip())
    soup = BeautifulSoup(value, 'html.parser')
    for comment in soup.find_all(string=lambda s:isinstance(s,Comment)):
        comment.extract()
    for node in list(soup.find_all(True)):
        if node.name in DROP:
            node.decompose()
        elif node.name and node.name not in TAGS:
            node.unwrap()
    for node in soup.find_all(True):
        original = dict(node.attrs)
        node.attrs = {}
        if node.name == 'a':
            href = str(original.get('href','')).strip()
            if re.fullmatch(r'mailto:[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+',href):
                node['href'] = href
            elif href:
                checked = asset(href)
                if checked:
                    node['href'] = checked
                    node['target'] = '_blank'
                    node['rel'] = 'noopener noreferrer'
        elif node.name == 'img':
            src = str(original.get('src','')).strip()
            if not src:
                node.decompose()
                continue
            node['src'] = asset(src, True)
            node['alt'] = str(original.get('alt',''))
            node['loading'] = 'lazy'
            node['decoding'] = 'async'
        elif node.name in ('td','th'):
            for attr in ('colspan','rowspan'):
                if str(original.get(attr,'')).isdigit():
                    node[attr] = min(20,max(1,int(original[attr])))
    return str(soup)

def compile_blocks(blocks, asset):
    if blocks is None: return '', []
    if not isinstance(blocks,list): raise ValueError('正文内容段必须为列表')
    if len(blocks)>500: raise ValueError('单篇正文内容段最多500段，请拆分长文')
    output, metadata = [], []
    for block in blocks:
        if not isinstance(block,dict): raise ValueError('正文段格式不正确')
        kind = block.get('type', block.get('_block'))
        caption = escape(str(block.get('caption','')))
        html = ''
        if kind == 'text':
            heading = str(block.get('heading','')).strip()
            text = rich_html(block.get('text','') or '', asset)
            if not BeautifulSoup(text,'html.parser').get_text(strip=True) and not '<img ' in text:
                continue
            html = ('<h3>'+escape(heading)+'</h3>' if heading else '') + text
        elif kind == 'image':
            if not block.get('image'): continue
            url = asset(block['image'],True)
            width = 'wide' if block.get('width') == 'wide' else 'standard'
            html = '<figure class="content-image '+width+'"><img loading="lazy" decoding="async" src="'+escape(url,quote=True)+'" alt="'+escape(str(block.get('alt') or block.get('caption') or '文章配图'),quote=True)+'">'+('<figcaption>'+caption+'</figcaption>' if caption else '')+'</figure>'
            metadata.append({'type':'image','url':url})
        elif kind == 'video':
            video = block.get('video') or block.get('url')
            if not video: continue
            url = asset(video)
            if block.get('video') or urlsplit(url).path.lower().endswith(('.mp4','.webm')):
                poster = asset(block['poster'],True) if block.get('poster') else ''
                html = '<figure class="content-video"><video controls playsinline preload="none" '+('poster="'+escape(poster,quote=True)+'" ' if poster else '')+'src="'+escape(url,quote=True)+'">您的浏览器不支持视频播放。</video>'+('<figcaption>'+caption+'</figcaption>' if caption else '')+'</figure>'
            else:
                html = '<p class="content-video-link"><a href="'+escape(url,quote=True)+'" target="_blank" rel="noopener noreferrer">'+escape(str(block.get('label') or '打开视频'))+' ↗</a></p>'
        elif kind == 'file':
            if not block.get('file'): continue
            url=asset(block['file'])
            label=str(block.get('label') or PurePosixPath(urlsplit(url).path).name or '查看资料')
            html='<p class="content-attachment"><a href="'+escape(url,quote=True)+'" target="_blank" rel="noopener noreferrer"><span>'+escape(label)+'</span><span aria-hidden="true">↗</span></a></p>'
            description=block.get('description') or ''
            if not isinstance(description,str):raise ValueError('附件说明必须是文字')
            description=description.strip()
            if description:
                html='<div class="content-attachment-group">'+html+'<p class="attachment-description">'+escape(description).replace('\n','<br>')+'</p></div>'
        else:
            raise ValueError('未知正文段类型：'+str(kind))
        output.append('<div class="content-block" data-block-type="'+kind+'">'+html+'</div>')
    return ''.join(output), metadata

def compile_record(record, asset):
    """Legacy text/media stays available unless a nonempty new body replaces it."""
    if 'content' in record:
        record['contentHtml'], record['contentMedia'] = compile_blocks(record['content'],asset)
    sections = record.get('sections')
    if sections is None: return
    if not isinstance(sections,list): raise ValueError('教师章节必须为列表')
    prepared=[]
    for i,section in enumerate(sections):
        if not isinstance(section,dict): raise ValueError('教师章节格式不正确')
        title=str(section.get('title','')).strip()
        kind=section.get('kind') or 'content'
        if kind not in ('content','projects','papers','awards'): raise ValueError('未知教师章节来源')
        html,_=compile_blocks(section.get('content',[]),asset)
        if kind=='content' and not html: continue
        if not title: raise ValueError('已填写内容的教师章节必须有标题')
        prepared.append({'title':title,'kind':kind,'html':html,'anchor':'section-'+str(i+1)})
    record['renderedSections']=prepared
