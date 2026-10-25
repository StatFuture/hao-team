(() => {
 const data=JSON.parse(document.getElementById('cms-page-data').textContent),maximum=Number(data.pageSize)||10,refreshers=[];
 for(const list of document.querySelectorAll('[data-cms-list]')){
  const key=list.dataset.cmsList,items=data.groups[key]||[];if(!items.length)continue;
  let current=1,capacity=0,counts=[],starts=[];
  const nav=document.createElement('nav');nav.className='cms-pager';nav.setAttribute('aria-label',({members:'成员',papers:'论文',projects:'项目',patents:'专利',books:'教材',awards:'荣誉',resources:'资料'})[key]+'分页');
  const prev=document.createElement('button'),next=document.createElement('button'),label=document.createElement('span'),jump=document.createElement('input'),go=document.createElement('button');prev.textContent='上一页';next.textContent='下一页';go.textContent='跳转';label.setAttribute('aria-live','polite');jump.type='number';jump.min=1;jump.setAttribute('aria-label','跳到第几页');nav.append(prev,label,next,jump,go);list.after(nav);
  function suggestedCapacity(){let limit=Math.min(maximum,innerWidth<600?6:innerWidth<1000?8:maximum);limit=Math.max(3,Math.round(limit*Math.min(1,Math.max(.65,innerHeight/850))));
   if(key==='papers'&&list.getClientRects().length&&list.clientWidth){const probe=list.cloneNode(false);probe.removeAttribute('data-cms-list');probe.setAttribute('aria-hidden','true');Object.assign(probe.style,{position:'absolute',visibility:'hidden',pointerEvents:'none',width:list.clientWidth+'px',height:'auto',left:'0',top:'0'});const sample=items.slice(0,Math.min(20,items.length));probe.innerHTML=sample.join('');list.parentNode.append(probe);const average=probe.getBoundingClientRect().height/sample.length;probe.remove();if(average>0)limit=Math.min(limit,Math.max(3,Math.floor(Math.min(950,Math.max(500,innerHeight*1.1))/average)));}
   return Math.max(1,limit);}
  function distribute(size){const pages=Math.max(1,Math.ceil(items.length/size)),base=Math.floor(items.length/pages),extra=items.length%pages;counts=Array.from({length:pages},(_,i)=>base+(i<extra?1:0));let offset=0;starts=counts.map(n=>{const start=offset;offset+=n;return start});jump.max=pages;nav.hidden=pages===1;}
  function paint(page,focus=false){current=Math.min(counts.length,Math.max(1,Math.trunc(Number(page))||1));list.querySelectorAll('video').forEach(v=>v.pause());const start=starts[current-1];list.innerHTML=items.slice(start,start+counts[current-1]).join('');list.dataset.page=current;list.dataset.pageCounts=counts.join(',');label.textContent=`第 ${current} / ${counts.length} 页，本页 ${counts[current-1]} 条，共 ${items.length} 条`;prev.disabled=current===1;next.disabled=current===counts.length;jump.value=current;if(focus){list.tabIndex=-1;list.focus({preventScroll:true});if(list.getBoundingClientRect().top<0)list.scrollIntoView({block:'start'});}}
  function adapt(){const size=suggestedCapacity();if(size===capacity)return;const anchor=starts[current-1]||0;capacity=size;distribute(size);const target=starts.findIndex((n,i)=>anchor>=n&&anchor<n+counts[i]);paint(target+1);}
  prev.onclick=()=>paint(current-1,true);next.onclick=()=>paint(current+1,true);go.onclick=()=>paint(jump.value,true);jump.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();go.click()}};refreshers.push(adapt);adapt();
 }
 let resizeTimer;function refresh(){clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>refreshers.forEach(f=>f()),100)}
 addEventListener('resize',refresh);document.addEventListener('faculty-tab-selected',refresh);document.querySelectorAll('[role=tab]').forEach(t=>t.addEventListener('click',refresh));if(document.fonts)document.fonts.ready.then(refresh);
 document.querySelectorAll('[role=tab]').forEach(t=>t.addEventListener('click',()=>{document.querySelectorAll('[role=tabpanel][hidden] video').forEach(v=>v.pause())}));
 const toggle=document.querySelector('.menu-toggle'),tabs=document.getElementById('tabs');if(toggle&&tabs)toggle.onclick=()=>{const open=tabs.classList.toggle('open');toggle.setAttribute('aria-expanded',String(open))};
 document.documentElement.dataset.cmsReady='true';
})();
