/* Article and member layouts. Formatted HTML is sanitized during the static build. */
function createReadingRenderer(context){
const {esc,media,get,kinds,labels,shell,currentQuery,returnQuery,title,members,pageNumber,pageSize,isStudent,P,S,memberPhoto,emailLink,ext,demoBadge,list,fields,empty}=context;
function plainParagraphs(value){return String(value||'').trim().split(/\n\s*\n/).filter(Boolean).map(p=>`<p>${esc(p).replaceAll('\n','<br>')}</p>`).join('');}
function recordBody(x){return typeof x.contentHtml==='string'?`<div class="content-flow">${x.contentHtml}</div>`:`<div class="content-flow legacy-body">${plainParagraphs(x.body)}<div class="legacy-media">${media(x)}</div></div>`;}
function renderRecordDetail(section,kind,id){
 if(section==='research'?!kinds[kind]:section!==kind)return shell(section,empty('该内容不存在'));
 const x=get(kind).find(x=>x.id===id);if(!x)return shell(section,empty('该内容未发布或不存在'));
 const query=currentQuery(),area=query.get('area'),originMember=query.get('member');
 const validMember=originMember&&members().some(m=>m.id===originMember);
 const back=validMember?`#/team/member/${encodeURIComponent(originMember)}?${new URLSearchParams([...query].filter(([k])=>k!=='member'))}`:section==='research'&&area?`#/research/area/${encodeURIComponent(area)}?${returnQuery()}`:`#/${section}?${returnQuery()}`;
 const news=kind==='news';
 return shell(section,`<article class="article reading-article ${news?'news-article':''}"><header class="article-heading"><h1>${esc(x.title||title(x,kind))}</h1><p class="article-meta">${esc(kinds[kind]||labels[section])}${x.date?' · '+esc(x.date):''}</p></header>${x.contributors?`<p class="meta">参与成员：${esc(x.contributors)}</p>`:''}${x.researchArea?`<p class="meta">研究方向：${esc(x.researchArea)}</p>`:''}${!news&&x.summary?`<p class="article-lead">${esc(x.summary)}</p>`:''}${fields(x.fields)}${(x.lines||[]).map(s=>`<p>${esc(s)}</p>`).join('')}${x.text?plainParagraphs(x.text):''}${kind==='papers'&&x.citation?`<p class="citation">${esc(x.citation)}</p>`:''}${recordBody(x)}${x.doi?`<p class="meta">DOI：${esc(x.doi)}</p>`:''}${ext(x.link,'查看原文')}${x.source?`<p class="source">${ext(x.source,'资料来源')}</p>`:''}<p class="article-return"><a class="back" href="${back}">← 返回${validMember?'教师介绍':section==='research'&&area?'研究方向':labels[section]}</a></p></article>`,true);
}
function memberAssociated(kind,member){return get(kind).filter(x=>(x.memberRefs||[]).some(ref=>String(ref).split('/').pop().replace(/\.json$/,'')===member.id));}
function renderMemberDetail(id,q){
 const x=members().find(x=>x.id===id),tab=q.get('from')==='students'?'students':'teachers';
 const back='#/team/'+tab+'?page='+pageNumber(q.get('page'))+'&size='+([10,20,50].includes(Number(q.get('size')))?Number(q.get('size')):pageSize);
 if(!x)return shell('team',`<p class="empty">该成员未发布或不存在。</p><a class="back" href="${back}">← 返回成员名录</a>`,true);
 document.title=x.name+' · 学术团队 · '+(S.school||'天津商业大学');
 let chapters=[];
 if(Array.isArray(x.renderedSections)){
  chapters=x.renderedSections.map(s=>{let html=s.html;if(s.kind!=='content'){const rows=memberAssociated(s.kind,x),param=s.kind+'Page';html=rows.length?list(s.kind,'research',pageNumber(q.get(param)),[10,20,50].includes(Number(q.get('size')))?Number(q.get('size')):pageSize,rows,param):'';if(html){const wrapper=document.createElement('div');wrapper.innerHTML=html;wrapper.querySelectorAll('a[href^="#/research/"]').forEach(a=>{const [route,query='']=a.getAttribute('href').split('?'),params=new URLSearchParams(query);params.set('member',x.id);for(const key of ['from','page','size'])if(q.has(key))params.set(key,q.get(key));a.setAttribute('href',route+'?'+params);});html=wrapper.innerHTML;}}return {...s,html};}).filter(s=>s.html);
 }else{
  if(x.bio)chapters.push({title:'个人简介',html:plainParagraphs(x.bio)});
  if(x.body||x.contentHtml||x.images?.length||x.video||x.attachment)chapters.push({title:'个人介绍',html:recordBody(x)});
 }
 chapters=chapters.map((s,i)=>({...s,anchor:'member-section-'+(i+1)}));
 const research=x.researchFocus||(x.lead?(P.directions||[]).join('、'):'');
 const facts=[['职称',x.role==='student'?'学生':x.role],['导师身份',x.mentor],['研究方向',research],['办公地点',x.office]];
 const closed=matchMedia('(max-width:760px)').matches;
 return shell('team',`<div class="member-layout"><aside class="member-sidebar" aria-label="学术团队栏目与教师章节"><details ${closed?'':'open'}><summary>学术团队与本页目录</summary><div class="member-sidebar-body"><h2>学术团队</h2><nav class="member-category-nav" aria-label="成员分类"><a href="#/team/teachers" ${!isStudent(x)?'aria-current="page"':''}>教师</a><a href="#/team/students" ${isStudent(x)?'aria-current="page"':''}>学生</a></nav>${chapters.length?`<p class="chapter-label">本页内容</p><div class="member-chapters">${chapters.map(s=>`<button type="button" data-section-jump="${s.anchor}">${esc(s.title)}</button>`).join('')}</div>`:''}</div></details></aside><article class="member-detail teacher-article"><header class="member-detail-heading">${memberPhoto(x)}<div><h1>${esc(x.name)}</h1>${demoBadge(x)}<dl class="member-facts">${facts.filter(a=>a[1]).map(([label,value])=>`<div><dt>${label}</dt><dd>${esc(value)}</dd></div>`).join('')}${x.email?`<div><dt>电子邮箱</dt><dd>${emailLink(x.email)}</dd></div>`:''}${x.link||x.homepage||x.lead&&S.teacherHomepage?`<div><dt>个人主页</dt><dd>${ext(x.link||x.homepage||S.teacherHomepage,'访问个人主页')}</dd></div>`:''}</dl></div></header>${chapters.map(s=>`<section class="member-chapter" id="${s.anchor}"><h2 tabindex="-1">${esc(s.title)}</h2><div class="content-flow">${s.html}</div></section>`).join('')}<p class="article-return"><a class="back" href="${back}">← 返回成员名录</a></p></article></div>`,true);
}
document.addEventListener('click',e=>{const button=e.target.closest('[data-section-jump]');if(!button)return;const chapter=document.getElementById(button.dataset.sectionJump);if(!chapter)return;chapter.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});chapter.querySelector('h2')?.focus({preventScroll:true});});
return {plainParagraphs,recordBody,renderMemberDetail,renderRecordDetail};
}
