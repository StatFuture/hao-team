"""Build version two without changing the version-one output or its source data."""
from pathlib import Path
import base64, copy, hashlib, io, json, math, shutil
from PIL import Image, ImageOps
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from build import Builder, read, ROOT
from content_blocks import compile_record

SHARED = ('projects', 'papers', 'patents', 'books', 'awards')
PRIVATE = ('news', 'members', 'resources')

def load_records(folder):
    values = []
    for path in sorted(folder.glob('*.json')):
        value = read(path)
        if not isinstance(value, dict):
            raise ValueError(f'{path}: record must be an object')
        if value.get('published') is not True:
            continue
        value = copy.deepcopy(value)
        value['id'] = path.stem
        order = value.get('order') if value.get('order') is not None else 9999
        if isinstance(order, bool) or not isinstance(order, (int, float)) or not math.isfinite(order):
            raise ValueError(f'{path}: order must be a finite number')
        if not str(value.get('title', value.get('name', ''))).strip():
            raise ValueError(f'{path}: missing title/name')
        value['order'] = order
        values.append(value)
    return values

def build_v2(root=ROOT, dest=None):
    root = Path(root).resolve()
    source = root / 'versions/v2'
    dest = Path(dest or root / '_site/v2').resolve()
    if not dest.is_relative_to(root) or dest in (root, source) or source.is_relative_to(dest):
        raise ValueError('Unsafe version-two output directory')
    if dest.exists():
        shutil.rmtree(dest)
    (dest / 'assets').mkdir(parents=True)
    for name in ('site.css', 'reading.css', 'site.js', 'reading.js', 'school-logo.png', 'avatar-default.png'):
        shutil.copy2(source / 'assets' / name, dest / 'assets' / name)
    # Reuse the approved first-version watercolor asset, without changing version one.
    shutil.copy2(root / 'assets/image-08af15a9b38d928b.webp', dest / 'assets/campus-header.webp')
    shutil.copy2(source / 'index.html', dest / 'index.html')
    data = {'profile': read(root / 'data/profile.json'),
            'settings': read(source / 'data/settings.json'), 'collections': {}}
    settings = data['settings']
    if settings.get('demoMode') is True:
        demo_settings = read(source / 'data/layout-demo.json')
        allowed_demo_settings = ('teamName', 'labIntro', 'researchAreas', 'admissionsIntro',
                                 'admissionContacts', 'contactAddress', 'contactPhone', 'contactEmail')
        settings.update({k: demo_settings[k] for k in allowed_demo_settings if k in demo_settings})
    # Dedicated editor entries replace the former long, mixed-purpose settings form.
    for filename, mapping in (
        ('lab.json', {'intro':'labIntro','content':'labContent'}),
        ('admissions.json', {'intro':'admissionsIntro','contacts':'admissionContacts',
                             'links':'admissionLinks','note':'admissionNote','content':'admissionsContent'})):
        path = source / 'data' / filename
        if path.exists():
            page = read(path)
            if not page.get('layoutDemo') or settings.get('demoMode') is True:
                settings.update({target:page.get(key, [] if key in ('content','contacts','links') else '') for key,target in mapping.items()})
    direction_folder = source / 'content/directions'
    if direction_folder.exists():
        areas = load_records(direction_folder)
        settings['researchAreas'] = [x for x in sorted(areas,key=lambda x:x['order'])
                                    if not x.get('layoutDemo') or settings.get('demoMode') is True]
    try:
        page_size = int(settings.get('pageSize', 10))
    except (ValueError, TypeError):
        raise ValueError('Version-two pageSize must be 10, 20 or 50')
    if page_size not in (10, 20, 50):
        raise ValueError('Version-two pageSize must be 10, 20 or 50')
    settings['pageSize'] = page_size
    overrides = {}
    for path in sorted((source / 'content/overrides').glob('*.json')):
        value = read(path)
        if value.get('published') is not True:
            continue
        key = (value.get('collection'), value.get('recordId'))
        if key in overrides:
            raise ValueError(f'Duplicate version-two override: {key}')
        if key[0] not in SHARED:
            raise ValueError('Overrides may only target shared academic records')
        overrides[key] = value
    used = set()
    allowed = ('body', 'summary', 'images', 'cover', 'video', 'videoUrl', 'poster',
               'attachment', 'showOnHome', 'order')
    for kind in SHARED + PRIVATE:
        folder = root / 'content' / kind if kind in SHARED else source / 'content' / kind
        records = load_records(folder)
        result = []
        for value in records:
            key = (kind, value['id'])
            override = overrides.get(key)
            if override:
                used.add(key)
                if override.get('hidden') is True:
                    continue
                for field in allowed:
                    if field in override and override[field] is not None:
                        value[field] = override[field]
            if kind == 'resources' and value.get('target') not in (None, '', 'resources', 'home', 'lab', 'news', 'team', 'research', 'admissions'):
                raise ValueError('Invalid version-two resource target')
            result.append(value)
        for value in result:
            order = value.get('order') if value.get('order') is not None else 9999
            if isinstance(order, bool) or not isinstance(order, (int, float)) or not math.isfinite(order):
                raise ValueError('Override order must be a finite number')
        result.sort(key=lambda v: str(v.get('date', '')), reverse=True)
        if kind == 'news':
            # Normal news follows date; ordering numbers only arrange pinned news.
            result.sort(key=lambda v: str(v.get('date','')), reverse=True)
            result.sort(key=lambda v: (not bool(v.get('pinned')), v.get('order',9999) if v.get('pinned') else 0))
        else:
            result.sort(key=lambda v: (v.get('order',9999), v['id'] if not v.get('date') else ''))
        data['collections'][kind] = result
    if set(overrides) - used:
        raise ValueError('Override points to a missing or unpublished shared record: ' + str(set(overrides) - used))
    # Team records have their own editable source; shared records are opt-in.
    for kind in SHARED:
        if settings.get('showSharedResearch') is False:
            data['collections'][kind] = []
        team_records = load_records(source / 'content' / kind)
        for value in team_records:
            value['id'] = 'team-' + value['id']
        data['collections'][kind].extend(team_records)
        data['collections'][kind].sort(key=lambda v: str(v.get('date', '')), reverse=True)
        data['collections'][kind].sort(key=lambda v: v.get('order', 9999))
        if kind == 'papers':
            data['collections'][kind].sort(key=lambda v: int(v.get('year') or 0),reverse=True)
    settings.pop('recordOverrides', None)
    if settings.get('demoMode') is not True:
        for kind in data['collections']:
            data['collections'][kind] = [v for v in data['collections'][kind] if not v.get('layoutDemo')]
    assets = Builder(root, dest)
    def asset(value, image=False):
        if not value:
            return ''
        if not isinstance(value, str):
            raise ValueError('Asset/link must be a string')
        if value.startswith(('/media/','/assets/')):
            value = value[1:]
        value = assets.source(value)
        if image:
            markup = assets.image(value)
            return BeautifulSoup(markup, 'html.parser').img['src']
        if value and not urlsplit(value).scheme:
            target = dest / value
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / value, target)
        return value
    def media(record):
        images = record.get('images', []) or []
        if not isinstance(images, list):
            raise ValueError('images must be a list')
        record['images'] = [asset(i, True) if isinstance(i, str) else
                            {'url': asset(i.get('url'), True), 'caption': str(i.get('caption', ''))}
                            for i in images]
        for key in ('photo', 'portrait', 'poster', 'cover'):
            if record.get(key):
                if key == 'cover' and isinstance(record[key], dict):
                    record[key] = {'url': asset(record[key].get('url'), True),
                                   'caption': str(record[key].get('caption', ''))}
                else:
                    record[key] = asset(record[key], True)
        for key in ('video', 'videoUrl', 'attachment', 'link', 'source', 'homepage'):
            if record.get(key):
                record[key] = asset(record[key])
    if settings.get('showPersonalProfile') is False:
        data['profile'] = {}
    media(data['profile'])
    for admission in data['profile'].get('admissions', []):
        admission['url'] = asset(admission.get('url'))
    if settings.get('teacherHomepage'):
        settings['teacherHomepage'] = asset(settings['teacherHomepage'])
    slides = []
    for slide in settings.get('slides', []):
        if slide.get('layoutDemo') and settings.get('demoMode') is not True:
            continue
        if slide.get('published') is True and slide.get('image'):
            slide = copy.deepcopy(slide)
            original = assets.source(slide['image'])
            # Carousel assets have their own smaller responsive encodings. Originals stay intact.
            for generated in ('preview', 'imageSmall', 'imageWidth', 'imageHeight'):
                slide.pop(generated, None)
            if not urlsplit(original).scheme:
                with Image.open(root / original) as im:
                    if im.format not in ('PNG', 'JPEG', 'WEBP'):
                        raise ValueError('Only PNG/JPEG/WebP carousel images are accepted')
                    im = ImageOps.exif_transpose(im).convert('RGB')
                    for field, width in (('image', 1440), ('imageSmall', 768)):
                        resized = im.copy()
                        resized.thumbnail((width, width))
                        buf = io.BytesIO()
                        resized.save(buf, 'WEBP', quality=75, method=6)
                        encoded = buf.getvalue()
                        name = 'assets/carousel-' + hashlib.sha256(encoded).hexdigest()[:16] + '.webp'
                        (dest / name).write_bytes(encoded)
                        slide[field] = name
                        if field == 'image':
                            slide['imageWidth'], slide['imageHeight'] = resized.size
                    tiny = im.copy()
                    tiny.thumbnail((240, 240))
                    buf = io.BytesIO()
                    tiny.save(buf, 'WEBP', quality=50)
                    slide['preview'] = 'data:image/webp;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
            else:
                slide['image'] = original
            slides.append(slide)
    slides.sort(key=lambda s: (float(s.get('order') or 0), str(s.get('id', ''))))
    settings['slides'] = slides
    for records in data['collections'].values():
        for record in records:
            media(record)
            compile_record(record, asset)
            if not record.get('cover') and record.get('contentMedia'):
                record['cover'] = record['contentMedia'][0]['url']
    for area in settings.get('researchAreas',[]):
        compile_record(area,asset)
    for name in ('lab','admissions'):
        fragment = {'content':settings.get(name+'Content',[])}
        compile_record(fragment,asset)
        settings[name+'Html'] = fragment.get('contentHtml','')
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    (dest / 'assets/data.js').write_text('window.SITE_DATA = ' + payload + ';\n', encoding='utf-8')
    # A newly published HTML page must not reuse a previous release's cached data/runtime.
    document = BeautifulSoup((dest / 'index.html').read_text(encoding='utf-8'), 'html.parser')
    # The first frame is visible even before the deferred data/runtime scripts execute.
    if slides:
        first = slides[0]
        preload = document.new_tag('link', rel='preload', **{'as': 'image', 'href': first['image'], 'fetchpriority': 'high'})
        image = document.new_tag('img', src=first['image'], alt=first.get('caption') or '团队风采照片', loading='eager', decoding='async', fetchpriority='high')
        if first.get('imageSmall'):
            srcset = first['imageSmall'] + ' 768w, ' + first['image'] + ' ' + str(first['imageWidth']) + 'w'
            # Avoid duplicate width descriptors for source images narrower than 768px.
            if first['imageWidth'] > 768:
                image['srcset'], image['sizes'] = srcset, '100vw'
                preload['imagesrcset'], preload['imagesizes'] = srcset, '100vw'
        def axis(value):
            try: return max(0, min(100, float(value)))
            except (TypeError, ValueError): return 50
        image['style'] = 'object-fit:' + ('cover' if first.get('imageFit') == 'cover' else 'contain') + ';object-position:' + str(axis(first.get('focusX', 50))) + '% ' + str(axis(first.get('focusY', 50))) + '%'
        hero = document.new_tag('section', **{'class': 'hero', 'aria-label': '团队风采'})
        if first.get('preview'):
            hero['style'] = 'background-image:url(' + first['preview'] + ');background-size:' + ('cover' if first.get('imageFit') == 'cover' else 'contain') + ';background-position:' + str(axis(first.get('focusX', 50))) + '% ' + str(axis(first.get('focusY', 50))) + '%;background-repeat:no-repeat'
        hero.append(image)
        document.main.clear()
        document.main.append(hero)
        document.head.append(preload)
    for node in document.select('script[src], link[rel=stylesheet][href]'):
        attr = 'src' if node.name == 'script' else 'href'
        name = node[attr]
        if name in ('assets/data.js', 'assets/site.js', 'assets/reading.js', 'assets/site.css', 'assets/reading.css'):
            digest = hashlib.sha256((dest / name).read_bytes()).hexdigest()[:16]
            node[attr] = name + '?v=' + digest
    (dest / 'index.html').write_text(str(document), encoding='utf-8')
    return {'published': {k: len(v) for k, v in data['collections'].items()},
            'dataBytes': len(payload.encode('utf-8')), 'path': 'v2/'}

if __name__ == '__main__':
    print(json.dumps(build_v2(), ensure_ascii=False))
