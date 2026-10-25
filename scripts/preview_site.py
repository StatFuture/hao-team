"""Assemble a draft-only viewing area alongside an unchanged production build."""
from datetime import datetime, timezone
from pathlib import Path
import argparse, json, shutil
from bs4 import BeautifulSoup


def assemble(production, draft, template, draft_sha, main_sha, run_id='local'):
    production, draft = Path(production).resolve(), Path(draft).resolve()
    target = production / 'preview'
    if not (production / 'index.html').is_file() or not (draft / 'index.html').is_file():
        raise ValueError('Both complete builds are required')
    if draft == production or production in draft.parents or draft in production.parents:
        raise ValueError('Draft and production builds must be separate')
    if target.exists():
        shutil.rmtree(target)
    target.mkdir()
    shutil.copytree(draft, target / 'site')
    page = target / 'site/index.html'
    soup = BeautifulSoup(page.read_text(encoding='utf-8'), 'html.parser')
    soup.head.append(soup.new_tag('meta', attrs={'name':'robots','content':'noindex,nofollow,noarchive'}))
    soup.title.string = '草稿预览 · ' + soup.title.get_text()
    page.write_text(str(soup), encoding='utf-8')
    shutil.copy2(template, target / 'index.html')
    manifest = {'draftSha':draft_sha, 'mainSha':main_sha, 'runId':str(run_id),
                'builtAt':datetime.now(timezone.utc).isoformat(), 'branch':'drafts'}
    (target / 'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    (target / 'robots.txt').write_text('User-agent: *\nDisallow: /\n',encoding='utf-8')
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--production',required=True)
    p.add_argument('--draft',required=True)
    p.add_argument('--template',default='templates/preview.html')
    p.add_argument('--draft-sha',required=True)
    p.add_argument('--main-sha',required=True)
    p.add_argument('--run-id',default='local')
    a=p.parse_args()
    print(json.dumps(assemble(a.production,a.draft,a.template,a.draft_sha,a.main_sha,a.run_id)))
