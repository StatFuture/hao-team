"""Publish the exact draft revision currently available for visual review."""
import json, os, subprocess, time
from urllib.request import Request, urlopen

def git(*args):
    return subprocess.check_output(['git',*args],text=True).strip()

def run():
    payload=json.loads(os.environ['CMS_PAYLOAD'])
    if payload.get('repository',{}).get('ref')!='drafts':
        raise ValueError('请从 drafts 草稿后台发布；main 是正式网站，请勿在 main 编辑。')
    git('fetch','origin','main','drafts')
    target=git('rev-parse','origin/drafts')
    request=Request('https://statfuture.github.io/hao-team/preview/manifest.json?t='+str(time.time_ns()),headers={'Cache-Control':'no-cache'})
    with urlopen(request,timeout=30) as response: manifest=json.load(response)
    if manifest.get('draftSha')!=target:
        raise ValueError('最新草稿预览尚未生成。请先等待预览更新并查看效果，再点击发布。')
    git('config','user.name','github-actions[bot]')
    git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    git('checkout','-B','publish-reviewed','origin/main')
    git('merge','--no-ff','--no-edit',target)
    # Standard fast-forward push refuses to overwrite concurrent main updates.
    git('push','origin','HEAD:main')
    # Pushes using GITHUB_TOKEN do not trigger other workflows: dispatch explicitly.
    data=json.dumps({'ref':'main'}).encode()
    request=Request('https://api.github.com/repos/StatFuture/hao-team/actions/workflows/pages.yml/dispatches',data=data,
                    headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json'},method='POST')
    with urlopen(request,timeout=30) as response:
        if response.status!=204:raise ValueError('发布已合并，但网站构建未启动，请点“重新生成预览”启动构建。')
    with open(os.environ.get('GITHUB_STEP_SUMMARY',os.devnull),'a',encoding='utf-8') as out:
        out.write('## 已提交正式发布\n\n[打开正式网站](https://statfuture.github.io/hao-team/)\n\n网站构建完成后生效；本次草稿版本：`'+target+'`。\n')

if __name__=='__main__':run()
