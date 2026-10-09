const ASSET_URL = 'assets/Arterial_System.svg';
const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => [...r.querySelectorAll(s)];

$$('[data-artery]').forEach(img => { img.src = ASSET_URL; });

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const header = $('#siteHeader');
const navToggle = $('.nav-toggle');
const navCompact = $('.nav-compact');

function fontPx(el){ return parseFloat(getComputedStyle(el).fontSize) || 16; }
function clampNum(v,a,b){ return Math.max(a,Math.min(b,v)); }
function textMeasure(text, el){
  const c=textMeasure.canvas || (textMeasure.canvas=document.createElement('canvas'));
  const ctx=c.getContext('2d'); const cs=getComputedStyle(el);
  ctx.font=`${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
  return ctx.measureText(text).width;
}
function setHeaderMode(){
  const w=header.getBoundingClientRect().width;
  const brandName=$('.brand-name'), brandSub=$('.brand-sub'), cta=$('.header-cta');
  const navLinks=$$('.nav-full a');
  const brandFull=textMeasure(brandName.textContent,brandName)+textMeasure(brandSub.textContent,brandSub)+34;
  const brandCompact=textMeasure(brandName.textContent,brandName)+10;
  const navNeed=navLinks.reduce((a,l)=>a+textMeasure(l.textContent,l),0)+Math.max(54,navLinks.length*24);
  const ctaNeed=textMeasure(cta.textContent,cta)+52;
  const chrome=clampNum(w*.07,44,112);
  if(w >= brandFull+navNeed+ctaNeed+chrome){ header.dataset.navMode='full'; navCompact.hidden=true; navToggle.setAttribute('aria-expanded','false'); }
  else if(w >= brandCompact+navNeed+ctaNeed+chrome*.7){ header.dataset.navMode='compact'; navCompact.hidden=true; navToggle.setAttribute('aria-expanded','false'); }
  else { header.dataset.navMode='menu'; }
}
navToggle?.addEventListener('click',()=>{ const open=navToggle.getAttribute('aria-expanded')==='true'; navToggle.setAttribute('aria-expanded',String(!open)); navCompact.hidden=open; });
$$('.nav-compact a').forEach(a=>a.addEventListener('click',()=>{navCompact.hidden=true;navToggle.setAttribute('aria-expanded','false')}));

function sceneFit(el, copyEl, opts={}){
  const r=el.getBoundingClientRect();
  const copyFont=fontPx(copyEl);
  const copyNeed=clampNum(copyFont*(opts.copyChars||7.5), opts.copyMin||280, opts.copyMax||900);
  const visualNeed=clampNum(r.height*(opts.visualWidthFromHeight||.42), opts.visualMin||260, opts.visualMax||760);
  const gap=clampNum(copyFont*(opts.gapEm||.75),24,110);
  const need=copyNeed+visualNeed+gap;
  const ratio=r.width/Math.max(r.height,1);
  if(r.width >= need*1.13 && ratio >= (opts.expandedRatio||1.12)) return 'expanded';
  if(r.width >= need*.92 && ratio >= (opts.compactRatio||.88)) return 'compact';
  return 'flow';
}
function applicationMode(){
  const el=$('.applications'), r=el.getBoundingClientRect();
  const titles=$$('.application-zone h3');
  const minZone=Math.max(...titles.map(t=>clampNum(fontPx(t)*6.8,260,390)));
  const gaps=clampNum(r.width*.045,36,110);
  return r.width >= minZone*3+gaps ? 'expanded' : 'flow';
}
function drawFlowPath(){
  const map=$('#workflowMap'), svg=$('#flowchartLines'), base=$('#flowPathBase'), active=$('#flowPathActive');
  if(!map||!svg||!base||!active)return;
  const mr=map.getBoundingClientRect();
  const points=$$('[data-flow-point]',map).map(el=>{
    const target=el.classList.contains('flow-step')?$('.flow-symbol',el):$('.gate-mark',el);
    const r=(target||el).getBoundingClientRect();
    return {x:r.left-mr.left+r.width/2,y:r.top-mr.top+r.height/2};
  });
  if(points.length<2)return;
  svg.setAttribute('viewBox',`0 0 ${Math.max(1,mr.width)} ${Math.max(1,mr.height)}`);
  let d=`M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;
  const vertical=map.dataset.flowMode==='vertical';
  for(let i=1;i<points.length;i++){
    const a=points[i-1],b=points[i];
    if(vertical){
      const my=(a.y+b.y)/2;
      d+=` C ${a.x.toFixed(2)} ${my.toFixed(2)}, ${b.x.toFixed(2)} ${my.toFixed(2)}, ${b.x.toFixed(2)} ${b.y.toFixed(2)}`;
    }else{
      const mx=(a.x+b.x)/2;
      d+=` C ${mx.toFixed(2)} ${a.y.toFixed(2)}, ${mx.toFixed(2)} ${b.y.toFixed(2)}, ${b.x.toFixed(2)} ${b.y.toFixed(2)}`;
    }
  }
  base.setAttribute('d',d);active.setAttribute('d',d);
}
function workflowMode(){
  const map=$('#workflowMap'); if(!map) return;
  const r=map.getBoundingClientRect();
  const steps=$$('.flow-step',map);
  const widest=Math.max(...steps.map(s=>Math.max(textMeasure($('.flow-copy strong',s).textContent,$('.flow-copy strong',s)),92)));
  const gate=clampNum(r.width*.038,44,70);
  const gap=clampNum(r.width*.018,18,46);
  const horizontalNeed=steps.length*Math.max(118,widest*.78)+gate+gap*steps.length;
  map.dataset.flowMode=r.width>=horizontalNeed?'horizontal':'vertical';
  requestAnimationFrame(drawFlowPath);
}
function footerMode(){
  const footer=$('.mega-footer'), grid=$('.footer-grid');
  const w=grid.getBoundingClientRect().width;
  const buttons=$$('.doc-link',grid);
  const longest=Math.max(...buttons.map(b=>textMeasure(b.textContent,b)))+clampNum(w*.035,34,70);
  if(w/4 >= longest) footer.dataset.footerMode='four';
  else if(w/2 >= longest) footer.dataset.footerMode='two';
  else footer.dataset.footerMode='one';
}
function solveLayout(){
  const hero=$('.hero'); hero.dataset.mode=sceneFit(hero,$('.hero h1'),{copyChars:7.2,copyMin:360,copyMax:880,visualWidthFromHeight:.43,visualMin:300,visualMax:620,expandedRatio:1.05});
  const hr=hero.getBoundingClientRect();
  const extra=Math.max(0,hr.width-hr.height*1.72); const heroRight=clampNum(5.2+(extra/Math.max(hr.width,1))*26,3.2,13.5); hero.style.setProperty('--hero-right',`${heroRight}vi`);

  const pop=$('.population'); pop.dataset.mode=sceneFit(pop,$('.population h2'),{copyChars:7,copyMin:300,copyMax:650,visualWidthFromHeight:.47,visualMin:360,visualMax:780,expandedRatio:.94});
  const diff=$('.difference'); diff.dataset.mode=sceneFit(diff,$('.difference-message:not([hidden]) h2')||$('.difference-message h2'),{copyChars:6.2,copyMin:310,copyMax:620,visualWidthFromHeight:.48,visualMin:330,visualMax:700,expandedRatio:.93});
  const apps=$('.applications'); apps.dataset.mode=applicationMode();
  const pipe=$('.pipeline'); pipe.dataset.mode=sceneFit(pipe,$('.workflow-heading h2'),{copyChars:7.5,copyMin:350,copyMax:760,visualWidthFromHeight:.30,visualMin:280,visualMax:580,expandedRatio:.88});
  workflowMode();
  const science=$('.science'); science.dataset.mode=sceneFit(science,$('.science-copy h2'),{copyChars:6.4,copyMin:320,copyMax:650,visualWidthFromHeight:.32,visualMin:240,visualMax:470,expandedRatio:.9});
  const final=$('.final-cta'); final.dataset.mode=sceneFit(final,$('.final-copy h2'),{copyChars:7.8,copyMin:360,copyMax:900,visualWidthFromHeight:.40,visualMin:280,visualMax:560,expandedRatio:.92});
  footerMode(); setHeaderMode();
}
let solveRAF=0;
const scheduleSolve=()=>{cancelAnimationFrame(solveRAF);solveRAF=requestAnimationFrame(solveLayout)};
new ResizeObserver(scheduleSolve).observe(document.body);
window.visualViewport?.addEventListener('resize', scheduleSolve);
window.addEventListener('resize', scheduleSolve,{passive:true});
solveLayout();

window.addEventListener('scroll',()=>header.classList.toggle('scrolled',scrollY>24),{passive:true});

// Physiological pulse: a warm radial front originates near the heart and travels outward at 72 bpm.
const pulseStages = $$('[data-pulse="true"]');
function pulseFrame(t){
  if(!reducedMotion){
    const phase=(t%833)/833;
    let p,alpha;
    if(phase<.67){ p=phase/.67; alpha=1; }
    else { p=1; alpha=Math.max(0,1-(phase-.67)/.33); }
    const radius = 7 + p*128;
    const width = 7 + p*5;
    const inner = Math.max(0,radius-width);
    const outer = Math.min(145,radius+width);
    const mask=`radial-gradient(ellipse 88% 58% at 50% 31%, transparent 0 ${inner}%, rgba(0,0,0,${Math.min(1,alpha*1.2)}) ${radius}%, transparent ${outer}%)`;
    pulseStages.forEach(stage=>{
      const layer=$('.artery-pulse',stage); if(!layer)return;
      layer.style.webkitMaskImage=mask; layer.style.maskImage=mask; layer.style.opacity=String(.18+.78*alpha);
      const heart=$('.heart-origin',stage); if(heart) heart.style.opacity=String(.12+.72*Math.max(0,1-phase*3.8));
    });
  }
  requestAnimationFrame(pulseFrame);
}
requestAnimationFrame(pulseFrame);

// Population fields — structural multiplicity only; no quantitative distribution implied.
const popLayout=[
  [69,5,.57,.20,.55],[84,10,.48,.16,.5],[52,8,.66,.25,.62],[37,16,.78,.32,.68],[72,22,.74,.28,.66],[91,29,.55,.18,.55],
  [58,34,.88,.45,.78],[42,42,.9,.45,.78],[77,43,.82,.36,.7],[25,48,.72,.30,.66],[91,54,.66,.23,.6],[61,58,1.0,.64,.9],
  [43,66,.9,.43,.76],[78,69,.82,.35,.7],[24,73,.68,.27,.62],[89,78,.56,.19,.55],[57,82,.8,.34,.69],[38,86,.63,.22,.58],
  [72,89,.62,.22,.57],[14,88,.53,.17,.52],[96,88,.45,.14,.48]
];
function buildPopulation(container, layout=popLayout, caseMode=false){
  if(!container)return;
  container.innerHTML='';
  layout.forEach((v,i)=>{
    const d=document.createElement('div'); d.className=caseMode?'case-subject':'pop-subject';
    if(caseMode && [4,7,10].includes(i)) d.classList.add('selected');
    d.style.setProperty('--x',`${v[0]}%`);d.style.setProperty('--y',`${v[1]}%`);d.style.setProperty('--s',v[2]);d.style.setProperty('--o',v[3]);d.style.setProperty(caseMode?'--br':'--b',v[4]);
    const img=document.createElement('img');img.src=ASSET_URL;img.alt='';d.appendChild(img);container.appendChild(d);
  });
}
buildPopulation($('#populationField'));
const caseLayout=[[8,3,.72,.24,.58],[33,0,.88,.3,.65],[60,2,.72,.24,.58],[79,9,.66,.22,.56],[18,30,.85,.32,.7],[44,26,.98,.4,.8],[69,31,.83,.3,.68],[5,57,.7,.24,.58],[30,55,.92,.38,.72],[56,57,.9,.34,.7],[78,57,.8,.3,.66],[20,78,.72,.23,.58],[49,78,.78,.26,.6],[73,80,.67,.21,.55]];
buildPopulation($('#caseField'),caseLayout,true);

// Differentiation state machine.
const diffVisual=$('#differenceVisual');
const diffTabs=$$('.difference-tabs [data-state]');
const diffPanels=$$('.difference-message');
const focus=$('.subject-focus',diffVisual);
let territory='carotid';
const territoryMap={carotid:['49%','13%'],aorta:['50%','43%'],iliac:['50%','61%']};
function applyTerritory(name){ territory=name; const [x,y]=territoryMap[name]; focus.style.setProperty('--fx',x);focus.style.setProperty('--fy',y); $$('.territory-control button').forEach(b=>b.classList.toggle('is-active',b.dataset.territory===name)); }
function setDiffState(state){
  diffTabs.forEach(b=>b.setAttribute('aria-selected',String(b.dataset.state===state)));
  diffPanels.forEach(p=>p.hidden=p.dataset.panel!==state);
  diffVisual.className='difference-visual';
  if(state==='paired' && $('.binary-control [data-disease="disease"]').classList.contains('is-active')) diffVisual.classList.add('is-disease');
  if(state==='system'){diffVisual.classList.add('is-system');applyTerritory(territory)}
  if(state==='priority')diffVisual.classList.add('is-priority');
  if(state==='scale')diffVisual.classList.add('is-scale');
}
diffTabs.forEach(b=>b.addEventListener('click',()=>setDiffState(b.dataset.state)));
$$('.binary-control [data-disease]').forEach(b=>b.addEventListener('click',()=>{
  $$('.binary-control [data-disease]').forEach(x=>x.classList.toggle('is-active',x===b));
  diffVisual.classList.toggle('is-disease',b.dataset.disease==='disease');
  if(b.dataset.disease==='disease'){focus.style.setProperty('--fx','50%');focus.style.setProperty('--fy','43%')}
}));
$$('.territory-control [data-territory]').forEach(b=>b.addEventListener('click',()=>applyTerritory(b.dataset.territory)));

// Applications: simultaneous on wide screens, one active state when fit requires flow.
const appButtons=$$('.application-selector [data-app]');
const appPanels=$$('[data-app-panel]');
function setApp(name){appButtons.forEach(b=>b.setAttribute('aria-selected',String(b.dataset.app===name)));appPanels.forEach(p=>p.classList.toggle('is-active',p.dataset.appPanel===name));}
appButtons.forEach(b=>b.addEventListener('click',()=>setApp(b.dataset.app)));



// In-site Markdown documentation tray. Footer links never navigate away from VascuQuest.
const DOC_BASE='./';
const DOC_NAMES={
  'README.md':'Platform Overview',
  'docs/V1_RESEARCH_PLATFORM.md':'Research Workflows',
  'docs/SCIENTIFIC_MODEL.md':'Scientific Model',
  'docs/VASCULAR_MECHANICS.md':'Vascular Mechanics',
  'docs/VIRTUAL_DISEASE.md':'Virtual Disease Models',
  'docs/HEMOSPACE.md':'HEMOSPACE Records',
  'docs/ANALYSIS.md':'Analysis Framework',
  'docs/ARCHITECTURE.md':'Platform Architecture'
};
const docDrawer=$('#docDrawer'), docTitle=$('#docTitle'), docMeta=$('#docMeta'), docContent=$('#docContent'), docClose=$('#docClose');
const docCache=new Map(); let currentDoc='';
function esc(s){return String(s).replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function resolveDocLink(href,base){
  if(/^https?:/i.test(href)||href.startsWith('#')) return href;
  if(!href.endsWith('.md')) return href;
  const root=base.includes('/')?base.slice(0,base.lastIndexOf('/')+1):'';
  const parts=(root+href).split('/'); const out=[];
  for(const p of parts){if(p==='..')out.pop();else if(p!=='.'&&p)out.push(p)}
  return out.join('/');
}
function inlineMD(t,base){
  let x=esc(t);
  x=x.replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/\*([^*]+)\*/g,'<em>$1</em>');
  x=x.replace(/\[([^\]]+)\]\(([^)]+)\)/g,(m,label,href)=>{const resolved=resolveDocLink(href,base);if(resolved.endsWith('.md')&&!/^https?:/i.test(resolved))return `<a href="#documentation" data-doc-inline="${esc(resolved)}">${label}</a>`;return `<a href="${esc(resolved)}" target="_blank" rel="noreferrer">${label}</a>`});
  return x;
}
function renderMarkdown(md,base){
  const lines=md.replace(/\r/g,'').split('\n'); let html='',inCode=false,code=[],list=null;
  const closeList=()=>{if(list){html+=`</${list}>`;list=null}};
  for(const raw of lines){
    if(raw.startsWith('```')){closeList();if(!inCode){inCode=true;code=[]}else{html+=`<pre><code>${esc(code.join('\n'))}</code></pre>`;inCode=false}continue}
    if(inCode){code.push(raw);continue}
    if(!raw.trim()){closeList();continue}
    const h=raw.match(/^(#{1,3})\s+(.*)$/);if(h){closeList();const n=h[1].length;html+=`<h${n}>${inlineMD(h[2],base)}</h${n}>`;continue}
    if(raw.startsWith('> ')){closeList();html+=`<blockquote>${inlineMD(raw.slice(2),base)}</blockquote>`;continue}
    const ul=raw.match(/^[-*]\s+(.*)$/);if(ul){if(list!=='ul'){closeList();html+='<ul>';list='ul'}html+=`<li>${inlineMD(ul[1],base)}</li>`;continue}
    const ol=raw.match(/^\d+\.\s+(.*)$/);if(ol){if(list!=='ol'){closeList();html+='<ol>';list='ol'}html+=`<li>${inlineMD(ol[1],base)}</li>`;continue}
    closeList();html+=`<p>${inlineMD(raw,base)}</p>`;
  }
  closeList(); if(inCode) html+=`<pre><code>${esc(code.join('\n'))}</code></pre>`; return html;
}
async function openDoc(path){
  currentDoc=path; docDrawer.classList.add('is-open'); docDrawer.setAttribute('aria-hidden','false');
  docTitle.textContent=DOC_NAMES[path]||path.split('/').pop().replace('.md','').replaceAll('_',' ');
  docMeta.textContent=path+' · rendered inside VascuQuest'; docContent.innerHTML='<p>Loading documentation…</p>';
  requestAnimationFrame(()=>docDrawer.scrollIntoView({behavior:reducedMotion?'auto':'smooth',block:'start'}));
  try{
    let md=docCache.get(path); if(!md){const r=await fetch(DOC_BASE+path,{cache:'force-cache'});if(!r.ok)throw new Error('HTTP '+r.status);md=await r.text();docCache.set(path,md)}
    if(currentDoc!==path)return; docContent.innerHTML=renderMarkdown(md,path); docContent.scrollTop=0; docContent.focus({preventScroll:true});
  }catch(err){
    docContent.innerHTML=`<h2>${esc(DOC_NAMES[path]||path)}</h2><p>This preview could not retrieve the Markdown source. The production build will serve the same repository Markdown inside this container rather than navigating to GitHub.</p><p><code>${esc(path)}</code></p>`;
  }
}
function closeDoc(){docDrawer.classList.remove('is-open');docDrawer.setAttribute('aria-hidden','true');currentDoc='';}
$$('[data-doc]').forEach(b=>b.addEventListener('click',()=>openDoc(b.dataset.doc)));
docClose?.addEventListener('click',closeDoc);
docContent?.addEventListener('click',e=>{const a=e.target.closest('[data-doc-inline]');if(a){e.preventDefault();openDoc(a.dataset.docInline)}});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&docDrawer.classList.contains('is-open'))closeDoc()});

window.addEventListener('load',()=>requestAnimationFrame(drawFlowPath));
