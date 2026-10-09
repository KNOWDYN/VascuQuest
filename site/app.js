(() => {
  const stage = document.getElementById('vascularStage');
  const canvas = document.getElementById('vascularGL');
  const gl = canvas.getContext('webgl2', {antialias:true, alpha:true});
  const VIEW = {x:-136.862,y:-576.555,w:1000,h:2000};
  const TEX_ASPECT = VIEW.w / VIEW.h;
  const hotspots = [...document.querySelectorAll('.anatomy-hotspot')];
  const readout = document.getElementById('diseaseReadout');
  const diseases = {
    carotid:{title:'Carotid stenosis',desc:'Controlled carotid narrowing examined across matched virtual cardiovascular systems.',uv:[.455,.108]},
    stiffness:{title:'Large-artery stiffening',desc:'Controlled stiffness change for studying pulse-wave propagation, pressure and arterial mechanics.',uv:[.502,.283]},
    aaa:{title:'Fusiform abdominal aortic aneurysm',desc:'Controlled aortic dilation for examining pressure–area mechanics, impedance and wave behaviour.',uv:[.502,.461]},
    iliac:{title:'Iliac stenosis',desc:'Controlled iliac narrowing with downstream pressure, flow and pulsatile-wave consequences.',uv:[.502,.606]}
  };
  let selected='carotid', mx=0, my=0, targetMx=0, targetMy=0, start=performance.now();
  let scaleX=1, scaleY=1;

  const root = document.documentElement;
  const topbar = document.querySelector('.topbar');
  const hero = document.querySelector('.hero');
  const heroCopy = document.querySelector('.hero-copy');

  function clamp(n,a,b){ return Math.max(a,Math.min(b,n)); }

  // Continuous layout engine: derives geometry from actual rendered containers, not device classes.
  function solvePageGeometry(){
    const headerH = topbar.getBoundingClientRect().height;
    root.style.setProperty('--header-h', `${headerH}px`);

    const sr = stage.getBoundingClientRect();
    if(sr.width > 0){
      // Scene height is a continuous function of its own width and available viewport height.
      const desired = sr.width / .76;
      const available = Math.max(1, innerHeight - headerH);
      const h = Math.min(desired, available * .86);
      stage.style.setProperty('--stage-h', `${h}px`);
    }

    // Content-fit solver: if the headline is being squeezed while the scene sits beside it,
    // recompose vertically. This uses rendered content geometry, not a viewport-width preset.
    const h1 = heroCopy.querySelector('h1');
    const hs = getComputedStyle(h1);
    const fontSize = parseFloat(hs.fontSize) || 1;
    const heroStyle=getComputedStyle(hero);
    const innerW=hero.clientWidth-parseFloat(heroStyle.paddingLeft)-parseFloat(heroStyle.paddingRight);
    const gap=parseFloat(heroStyle.columnGap||heroStyle.gap)||0;
    // Required widths scale from the current fluid headline typography, so the decision
    // follows content density rather than any named device/viewport size.
    const copyNeed=fontSize*6.35;
    const sceneNeed=fontSize*5.95;
    const shouldRecompose=innerW < copyNeed + sceneNeed + gap;
    if(hero.classList.contains('hero-recompose') !== shouldRecompose){
      hero.classList.toggle('hero-recompose',shouldRecompose);
      requestAnimationFrame(solvePageGeometry);
    }

    document.querySelectorAll('.section,.hero,.boundary,body > footer').forEach(el=>{
      const r=el.getBoundingClientRect();
      el.style.setProperty('--cw', `${r.width}px`);
      el.style.setProperty('--ch', `${r.height}px`);
      el.style.setProperty('--car', String(r.width / Math.max(r.height,1)));
    });
  }

  function currentAssetRect(){
    const r=stage.getBoundingClientRect();
    const boxAspect=r.width/Math.max(r.height,1);
    if(boxAspect > TEX_ASPECT){ scaleX=TEX_ASPECT/boxAspect*.94; scaleY=.94; }
    else{ scaleX=.94; scaleY=boxAspect/TEX_ASPECT*.94; }
    const w=r.width*scaleX, h=r.height*scaleY;
    const shiftX=mx*.018*r.width*.5, shiftY=-my*.012*r.height*.5;
    return {x:(r.width-w)/2+shiftX,y:(r.height-h)/2+shiftY,w,h,stageW:r.width,stageH:r.height};
  }

  function boxesOverlap(a,b){return !(a.right<b.left||a.left>b.right||a.bottom<b.top||a.top>b.bottom)}

  function placeHotspots(){
    const a=currentAssetRect();
    hotspots.forEach(h=>{
      h.classList.remove('flip','compact');
      const sx=+h.dataset.x, sy=+h.dataset.y;
      const u=(sx-VIEW.x)/VIEW.w, v=(sy-VIEW.y)/VIEW.h;
      const left=a.x+u*a.w, top=a.y+v*a.h;
      h.style.left=`${left}px`; h.style.top=`${top}px`;
      if(left > a.stageW*.63) h.classList.add('flip');
    });

    // Collision decisions use actual rendered boxes, never viewport-size presets.
    const sr=stage.getBoundingClientRect();
    const rr=readout.getBoundingClientRect();
    hotspots.forEach(h=>{
      let br=h.getBoundingClientRect();
      if(br.right>sr.right-6 || br.left<sr.left+6){ h.classList.toggle('flip',!h.classList.contains('flip')); br=h.getBoundingClientRect(); }
      if(boxesOverlap(br,rr) || br.right>sr.right-6 || br.left<sr.left+6) h.classList.add('compact');
    });
  }

  function positionReadout(){
    // Keep the selected anatomical focus and the readout in opposite vertical zones.
    readout.classList.toggle('readout-top', diseases[selected].uv[1] > .48);
  }

  const pageObserver = new ResizeObserver(()=>{solvePageGeometry();placeHotspots()});
  [document.body,topbar,hero,heroCopy,stage].forEach(el=>pageObserver.observe(el));
  solvePageGeometry();positionReadout();

  if(gl){
    const vs=`#version 300 es
      in vec2 a_position; out vec2 v_uv;
      uniform vec2 u_parallax; uniform vec2 u_scale;
      void main(){
        vec2 p=a_position*u_scale + u_parallax;
        v_uv=vec2(a_position.x*.5+.5, 1.0-(a_position.y*.5+.5));
        gl_Position=vec4(p,0.,1.);
      }`;
    const fs=`#version 300 es
      precision highp float; in vec2 v_uv; out vec4 outColor;
      uniform sampler2D u_tex; uniform float u_time; uniform vec2 u_focus;
      void main(){
        vec4 t=texture(u_tex,v_uv);
        float red=max(t.r-t.g*.55-t.b*.45,0.);
        float pulse=pow(max(0.,sin((v_uv.y*9.0-u_time*.75)*6.283)),18.0)*red;
        float d=distance(v_uv,u_focus);
        float focus=exp(-d*d*180.0);
        vec3 arterial=t.rgb*(1.0+red*.42)+vec3(1.0,.23,.12)*pulse*1.7+vec3(.95,.18,.10)*focus*red*2.0;
        float vignette=smoothstep(.78,.22,distance(v_uv,vec2(.5,.48)));
        vec3 bg=vec3(.018,.055,.10)+vec3(.015,.05,.10)*vignette;
        float a=max(t.a*.96,red*.9);
        outColor=vec4(mix(bg,arterial,a),1.0);
      }`;
    const compile=(type,src)=>{const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);return s};
    const prog=gl.createProgram();gl.attachShader(prog,compile(gl.VERTEX_SHADER,vs));gl.attachShader(prog,compile(gl.FRAGMENT_SHADER,fs));gl.linkProgram(prog);gl.useProgram(prog);
    const buf=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buf);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
    const pos=gl.getAttribLocation(prog,'a_position');gl.enableVertexAttribArray(pos);gl.vertexAttribPointer(pos,2,gl.FLOAT,false,0,0);
    const uTime=gl.getUniformLocation(prog,'u_time'),uFocus=gl.getUniformLocation(prog,'u_focus'),uParallax=gl.getUniformLocation(prog,'u_parallax'),uScale=gl.getUniformLocation(prog,'u_scale');
    const tex=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,tex);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
    const img=new Image();
    img.onload=()=>{gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,true);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,img);stage.classList.add('webgl-ready');requestAnimationFrame(draw)};
    img.src='assets/Arterial_System.svg';

    function resizeGL(){
      const dpr=Math.min(devicePixelRatio||1,2),r=stage.getBoundingClientRect();
      const w=Math.max(1,Math.round(r.width*dpr)),h=Math.max(1,Math.round(r.height*dpr));
      if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h)}
      currentAssetRect();
    }
    new ResizeObserver(()=>{resizeGL();placeHotspots()}).observe(stage);resizeGL();
    stage.addEventListener('pointermove',e=>{const r=stage.getBoundingClientRect();targetMx=(e.clientX-r.left)/r.width-.5;targetMy=(e.clientY-r.top)/r.height-.5});
    stage.addEventListener('pointerleave',()=>{targetMx=0;targetMy=0});
    function draw(now){
      resizeGL();mx+=(targetMx-mx)*.035;my+=(targetMy-my)*.035;currentAssetRect();placeHotspots();
      gl.uniform1f(uTime,(now-start)/1000);gl.uniform2fv(uFocus,diseases[selected].uv);gl.uniform2f(uParallax,mx*.018,-my*.012);gl.uniform2f(uScale,scaleX,scaleY);
      gl.drawArrays(gl.TRIANGLES,0,6);requestAnimationFrame(draw);
    }
  }

  hotspots.forEach(h=>h.addEventListener('click',()=>{
    selected=h.dataset.disease;
    hotspots.forEach(x=>x.classList.toggle('active',x===h));
    document.getElementById('diseaseTitle').textContent=diseases[selected].title;
    document.getElementById('diseaseDescription').textContent=diseases[selected].desc;
    document.getElementById('monitorDisease').textContent=diseases[selected].title;
    positionReadout();placeHotspots();
  }));

  document.querySelectorAll('.signal canvas').forEach(c=>{
    const wrap=c.parentElement,kind=wrap.dataset.signal,ctx=c.getContext('2d');
    function f(t,disease=false){
      if(kind==='pressure')return .47+.22*Math.sin(t*6.283-.35)+.07*Math.sin(t*12.566+.55)+(disease?.035*Math.sin(t*6.283+.9):0);
      if(kind==='flow')return .45+.28*Math.sin(t*6.283-.6)+.09*Math.sin(t*12.566+.25)+(disease?.055*Math.sin(t*18.849+1):0);
      return .48+.12*Math.sin(t*6.283-.15)+.03*Math.sin(t*12.566+.42)+(disease?-.025*Math.sin(t*6.283+.8):0)
    }
    function render(){
      const r=wrap.getBoundingClientRect(),d=Math.min(devicePixelRatio||1,2);c.width=Math.max(1,r.width*d);c.height=Math.max(1,r.height*d);const W=c.width,H=c.height;ctx.clearRect(0,0,W,H);
      ctx.strokeStyle='rgba(160,195,225,.10)';ctx.lineWidth=1;for(let i=1;i<6;i++){ctx.beginPath();ctx.moveTo(W*i/6,0);ctx.lineTo(W*i/6,H);ctx.stroke()}
      [[false,'rgba(92,226,241,.95)'],[true,'rgba(255,117,104,.95)']].forEach(([disease,col])=>{ctx.beginPath();for(let x=0;x<W;x++){const t=x/(W-1),y=H*(.88-f(t,disease));x?ctx.lineTo(x,y):ctx.moveTo(x,y)}ctx.strokeStyle=col;ctx.lineWidth=Math.max(2,(devicePixelRatio||1)*1.3);ctx.stroke()});
    }
    new ResizeObserver(render).observe(wrap);render();
  });

  const pc=document.getElementById('populationCanvas'),pctx=pc.getContext('2d'),pf=pc.parentElement;
  const frac=x=>x-Math.floor(x),hash=(i,k)=>frac(Math.sin(i*12.9898+k*78.233)*43758.5453);
  function drawPop(){const r=pf.getBoundingClientRect(),d=Math.min(devicePixelRatio||1,2);pc.width=Math.max(1,r.width*d);pc.height=Math.max(1,r.height*d);const W=pc.width,H=pc.height;pctx.clearRect(0,0,W,H);for(let i=1;i<=4374;i++){const x=.06+.88*((hash(i,1)+hash(i+11,2)+hash(i+31,3))/3),y=.07+.86*((hash(i,4)+hash(i+17,5)+hash(i+47,6))/3),hot=i%31<5;pctx.beginPath();pctx.arc(x*W,y*H,(hot?1.55:1.0)*d,0,Math.PI*2);pctx.fillStyle=hot?'rgba(210,72,59,.55)':'rgba(45,101,146,.28)';pctx.fill()}}
  new ResizeObserver(drawPop).observe(pf);drawPop();
})();
