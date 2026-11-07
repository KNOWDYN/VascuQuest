/* VascuQuest research dashboard: all quantitative traces originate from the
   user-supplied Cardioacoustics_ECs_v1.0.0 archive. The browser renders
   archived cohort summaries and a reconstructed 18-Hz phasor component. */
(() => {
  "use strict";
  const doc = document;
  const root = doc.documentElement;
  const header = doc.querySelector("[data-header]");
  const toggle = doc.querySelector("[data-menu-toggle]");
  const mobile = doc.querySelector("[data-mobile-nav]");
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function closeMenu() {
    if (!toggle || !mobile) return;
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Open navigation");
    mobile.hidden = true;
  }
  if (toggle && mobile) {
    toggle.addEventListener("click", () => {
      const open = toggle.getAttribute("aria-expanded") !== "true";
      toggle.setAttribute("aria-expanded", String(open));
      toggle.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
      mobile.hidden = !open;
    });
    mobile.querySelectorAll("a").forEach(a => a.addEventListener("click", closeMenu));
    window.addEventListener("keydown", e => { if (e.key === "Escape") closeMenu(); });
    window.addEventListener("resize", () => { if (window.innerWidth > 1000) closeMenu(); });
  }
  function updateHeader() { header?.classList.toggle("scrolled", window.scrollY > 12); }
  updateHeader();
  window.addEventListener("scroll", updateHeader, { passive: true });

  const revealed = [...doc.querySelectorAll(".reveal")];
  if (!reduced && "IntersectionObserver" in window) {
    root.classList.add("enhanced");
    const obs = new IntersectionObserver((entries, observer) => {
      for (const entry of entries) if (entry.isIntersecting) {
        entry.target.classList.add("revealed");
        observer.unobserve(entry.target);
      }
    }, {threshold:0.04,rootMargin:"0px 0px -20px 0px"});
    revealed.forEach(el => obs.observe(el));
  } else revealed.forEach(el => el.classList.add("revealed"));

  const copy = doc.querySelector("[data-copy]");
  copy?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(copy.getAttribute("data-copy"));
      copy.textContent = "COPIED";
    } catch {
      copy.textContent = "SELECT TEXT";
    }
  });

  const host = doc.querySelector("[data-research-console]");
  if (!host) return;
  const NS = "http://www.w3.org/2000/svg";
  const state = {site:"left_common_carotid",wall:"healthy",channel:"gain"};
  const colors = {healthy:"#80c7b8",partial:"#8caac8",stiff:"#e6a08f"};
  const names = {healthy:"Healthy elastic",partial:"Partially stiffened",stiff:"Stiffened arterial wall"};
  const metrics = {
    gain:{title:"Median pressure transfer gain",unit:"GAIN / dB",suffix:"dB",decimals:1},
    traction:{title:"Median endothelial traction transfer",unit:"TRACTION / mPa per Pa",suffix:"mPa/Pa",decimals:2},
    motion:{title:"Median wall displacement transfer",unit:"DISPLACEMENT / nm per Pa",suffix:"nm/Pa",decimals:1}
  };
  let archive = null;
  const byId = id => doc.getElementById(id);
  const setText = (id,val) => { const el=byId(id); if(el) el.textContent=String(val); };
  const fmt = (v,n=1) => Number(v).toLocaleString("en-GB",{minimumFractionDigits:n,maximumFractionDigits:n});

  function svgNode(name,attrs={},text) {
    const n=doc.createElementNS(NS,name);
    for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));
    if(text!==undefined)n.textContent=String(text);
    return n;
  }
  function append(parent,name,attrs={},text) { const el=svgNode(name,attrs,text); parent.appendChild(el); return el; }
  function pathFrom(values,x,y) { return values.map((v,i)=>(i?"L":"M")+x(i).toFixed(1)+" "+y(v).toFixed(1)).join(" "); }

  function selectedSite() { return archive.sites.find(s=>s.id===state.site)||archive.sites[0]; }
  function selectedIndex() { return archive.states.indexOf(state.wall); }

  function drawSpectrum() {
    const site=selectedSite(),cfg=metrics[state.channel];
    const grid=byId("rc-spectrum-grid"),series=byId("rc-spectrum-series"),
          axes=byId("rc-spectrum-axes"),markers=byId("rc-spectrum-markers");
    grid.replaceChildren();series.replaceChildren();axes.replaceChildren();markers.replaceChildren();
    const xs=archive.sampleFrequencyHz;
    const vals=site.states.flatMap(s=>s[state.channel]);
    let lo=Math.min(...vals),hi=Math.max(...vals);
    const range=Math.max(hi-lo,1);
    lo-=range*.12;hi+=range*.12;
    const X=f=>55+((f-10)/30)*681;
    const Y=v=>266-((v-lo)/(hi-lo))*227;
    for(let k=0;k<=4;k++) {
      const val=lo+(hi-lo)*k/4,y=Y(val);
      append(grid,"line",{x1:55,y1:y,x2:736,y2:y,stroke:"#324b55","stroke-width":1});
      append(axes,"text",{x:47,y:y+4,"text-anchor":"end",fill:"#8ca7b1","font-size":11,"font-family":"monospace"},Math.abs(val)>100?fmt(val,0):fmt(val,1));
    }
    for(const f of [10,15,20,25,30,35,40]) {
      const x=X(f);
      append(grid,"line",{x1:x,y1:39,x2:x,y2:266,stroke:"#2d4650","stroke-width":1});
      append(axes,"text",{x,y:294,"text-anchor":"middle",fill:"#8ca7b1","font-size":11,"font-family":"monospace"},String(f));
    }
    append(axes,"text",{x:395,y:308,"text-anchor":"middle",fill:"#9bb5bd","font-size":11,"font-family":"monospace"},"FREQUENCY / Hz");
    const x18=X(18);
    append(markers,"line",{x1:x18,y1:39,x2:x18,y2:266,stroke:"#e1b5a7","stroke-width":1.5,"stroke-dasharray":"4 6",opacity:.65});
    append(markers,"text",{x:x18+5,y:36,fill:"#e1b5a7","font-size":10,"font-family":"monospace"},"WP2 / 18 Hz");
    const order=archive.states.filter(k=>k!==state.wall).concat(state.wall);
    for(const name of order) {
      const v=site.states[archive.states.indexOf(name)][state.channel];
      append(series,"path",{d:pathFrom(v,i=>X(xs[i]),Y),fill:"none",stroke:colors[name],"stroke-width":name===state.wall?3.4:1.7,opacity:name===state.wall?1:.48,"stroke-linecap":"round","stroke-linejoin":"round","vector-effect":"non-scaling-stroke"});
    }
    setText("rc-chart-heading",cfg.title);
    setText("rc-chart-unit",cfg.unit);
    const svg=byId("rc-spectrum"),tip=byId("rc-plot-tooltip");
    svg.setAttribute("aria-label",cfg.title+" for "+site.label+", model states healthy, partially stiffened and stiffened, 10 to 40 Hz.");
    svg.onpointermove=event=>{
      const rect=svg.getBoundingClientRect();
      const local=(event.clientX-rect.left)/rect.width*760;
      const f=Math.min(40,Math.max(10,10+(local-55)/681*30));
      const idx=xs.reduce((best,x,i)=>Math.abs(x-f)<Math.abs(xs[best]-f)?i:best,0);
      tip.replaceChildren();
      const heading=doc.createElement("strong");
      heading.textContent=fmt(xs[idx],1)+" Hz";
      tip.appendChild(heading);
      archive.states.forEach((s,si)=>{
        const line=doc.createElement("div");
        line.style.color=colors[s];
        line.textContent=s.toUpperCase()+": "+fmt(site.states[si][state.channel][idx],cfg.decimals)+" "+cfg.suffix;
        tip.appendChild(line);
      });
      tip.setAttribute("aria-hidden","false");
    };
    svg.onpointerleave=()=>tip.setAttribute("aria-hidden","true");
  }

  function drawPhasor() {
    const svg=byId("rc-phasor-series"),labels=byId("rc-phasor-labels");
    svg.replaceChildren();labels.replaceChildren();
    const site=selectedSite(),n=145;
    const values=site.states.map(st=>Array.from({length:n},(_,i)=>{
      const t=i/(n-1)*.18;
      return st.refP[0]*Math.cos(2*Math.PI*18*t)-st.refP[1]*Math.sin(2*Math.PI*18*t);
    }));
    const all=values.flat(),max=Math.max(...all.map(Math.abs))*1.12;
    const X=i=>44+i/(n-1)*380;
    const Y=v=>81-v/max*60;
    append(labels,"line",{x1:44,x2:424,y1:81,y2:81,stroke:"#76949c","stroke-dasharray":"3 5",opacity:.5});
    for(const [i,t] of [[0,"0"],[1,"45"],[2,"90"],[3,"135"],[4,"180 ms"]])
      append(labels,"text",{x:44+i*95,y:158,"text-anchor":i===4?"end":"middle","font-family":"monospace","font-size":9,fill:"#91aab1"},t);
    const order=archive.states.filter(s=>s!==state.wall).concat(state.wall);
    for(const s of order){
      const idx=archive.states.indexOf(s);
      append(svg,"path",{d:pathFrom(values[idx],X,Y),fill:"none",stroke:colors[s],"stroke-width":s===state.wall?2.7:1.4,opacity:s===state.wall?1:.52,"stroke-linecap":"round","vector-effect":"non-scaling-stroke"});
    }
    byId("rc-phasor").setAttribute("aria-label","Complex 18 Hz WP2/A2 pressure phasor reconstruction for virtual subject 1048 at "+site.label+".");
  }

  function drawPWV() {
    const parent=byId("rc-pwv-bars");parent.replaceChildren();
    const ages=archive.age,min=4.5,max=14.5;
    const x=i=>48+i*71,y=v=>133-(v-min)/(max-min)*113;
    for(const tick of [6,8,10,12,14]){
      const v=y(tick);
      append(parent,"line",{x1:41,y1:v,x2:422,y2:v,stroke:"#334d56","stroke-width":1});
      append(parent,"text",{x:34,y:v+3,"text-anchor":"end","font-family":"monospace","font-size":9,fill:"#819da8"},String(tick));
    }
    for(let i=0;i<ages.length;i++){
      append(parent,"text",{x:x(i),y:156,"text-anchor":"middle","font-family":"monospace","font-size":9,fill:"#8cabb2"},String(ages[i]));
    }
    for(const s of archive.states){
      const arr=archive.pwv[s];
      append(parent,"path",{d:pathFrom(arr,i=>x(i),y),fill:"none",stroke:colors[s],"stroke-width":s===state.wall?2.7:1.4,opacity:s===state.wall?1:.48});
      arr.forEach((v,i)=>append(parent,"circle",{cx:x(i),cy:y(v),r:s===state.wall?3.2:2,fill:colors[s],opacity:s===state.wall?1:.65}));
    }
  }

  function drawMatrix() {
    const table=byId("rc-matrix-body");table.replaceChildren();
    const values=archive.sites.flatMap(site=>site.states.map(s=>s.p50));
    const min=Math.min(...values),max=Math.max(...values);
    for(const site of archive.sites){
      const tr=doc.createElement("tr");
      if(site.id===state.site)tr.className="is-selected";
      const first=doc.createElement("td");
      const siteBtn=doc.createElement("button");siteBtn.type="button";siteBtn.textContent=site.label;
      siteBtn.setAttribute("aria-label","Select "+site.label);
      siteBtn.onclick=()=>{state.site=site.id;refresh();};
      first.appendChild(siteBtn);tr.appendChild(first);
      for(let si=0;si<3;si++){
        const td=doc.createElement("td"),b=doc.createElement("button");
        const val=site.states[si].p50,norm=(val-min)/Math.max(max-min,1);
        b.type="button";b.textContent=fmt(val,1);
        b.style.background="rgba(230,160,143,"+(0.07+norm*.28).toFixed(2)+")";
        b.className=norm>.7?"rc-cell-hot":"";
        b.setAttribute("aria-label",site.label+", "+names[archive.states[si]]+": "+val+" pascals; select");
        b.onclick=()=>{state.site=site.id;state.wall=archive.states[si];refresh();};
        td.appendChild(b);tr.appendChild(td);
      }
      table.appendChild(tr);
    }
  }

  function updateInspector() {
    const site=selectedSite(),v=site.states[selectedIndex()];
    setText("rc-location",site.label);
    setText("rc-location-detail","PWDB segment "+String(site.segment).padStart(2,"0")+" · 102 virtual subjects");
    setText("rc-selected-location",site.label.toUpperCase());
    setText("rc-selected-state",names[state.wall].toUpperCase());
    const readings=[["rc-pressure",v.p50,"Pa",1],["rc-traction",v.t50,"Pa",3],["rc-displacement",v.m50,"µm",2],["rc-acceleration",v.acc50,"m/s²",3],["rc-gradient",v.grad50,"Pa/s",1]];
    for(const [id,value,unit,precision] of readings) {
      const el=byId(id);
      el.replaceChildren(doc.createTextNode(fmt(value,precision)+" "));
      appendUnit(el,unit);
    }
    doc.querySelectorAll("[data-site]").forEach(b=>{
      const yes=b.dataset.site===state.site;b.classList.toggle("active",yes);b.setAttribute("aria-pressed",String(yes));
    });
    doc.querySelectorAll("[data-state]").forEach(b=>{
      const yes=b.dataset.state===state.wall;b.classList.toggle("active",yes);b.setAttribute("aria-pressed",String(yes));
    });
    doc.querySelectorAll("[data-channel]").forEach(b=>{
      const yes=b.dataset.channel===state.channel;b.classList.toggle("active",yes);b.setAttribute("aria-pressed",String(yes));
    });
  }
  function appendUnit(parent,unit) {
    const small=doc.createElement("small");small.textContent=unit;parent.appendChild(small);
  }
  function refresh() { if(!archive)return;updateInspector();drawSpectrum();drawPhasor();drawPWV();drawMatrix(); }

  host.addEventListener("click",e=>{
    const site=e.target.closest("[data-site]"),wall=e.target.closest("[data-state]"),channel=e.target.closest("[data-channel]");
    if(site)state.site=site.dataset.site;
    if(wall)state.wall=wall.dataset.state;
    if(channel)state.channel=channel.dataset.channel;
    if(site||wall||channel)refresh();
  });

  (async function loadData(){
    const status=byId("rc-status");
    try{
      const url=new URL(host.getAttribute("data-source"),doc.baseURI);
      const resp=await fetch(url.href,{cache:"no-cache"});
      if(!resp.ok)throw new Error("HTTP "+resp.status);
      archive=await resp.json();
      if(archive.subjects!==102||archive.sites.length!==5||archive.states.length!==3||archive.sampleFrequencyHz.length!==21)
        throw new Error("Archive summary has an unexpected structure");
      if(archive.sites.some(site=>site.states.length!==3||site.states.some(s=>s.gain.length!==21||s.traction.length!==21||s.motion.length!==21)))
        throw new Error("Signal lengths do not match the frequency grid");
      status.textContent="DATASET READY";
      refresh();
    }catch(error){
      status.textContent="DATASET UNAVAILABLE";
      status.setAttribute("title",String(error));
      const plot=byId("rc-chart-heading");
      if(plot)plot.textContent="Unable to load archived research data";
    }
  })();
})();
