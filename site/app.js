(function(){
  const diseaseData = {
    carotid:{
      title:'Carotid stenosis',
      text:'Controlled carotid narrowing studied across matched virtual cardiovascular subjects.'
    },
    iliac:{
      title:'Iliac stenosis',
      text:'Controlled iliac narrowing with downstream pressure, flow and pulsatile-wave consequences.'
    },
    aaa:{
      title:'Fusiform abdominal aortic aneurysm',
      text:'Controlled aortic dilation for examining pressure–area mechanics and pulse-wave behaviour.'
    },
    stiffness:{
      title:'Large-artery stiffening',
      text:'Controlled stiffness change for studying pulse-wave propagation, pressure and arterial mechanics.'
    }
  };
  const title = document.getElementById('dpTitle');
  const text = document.getElementById('dpText');
  document.querySelectorAll('.hotspot').forEach(btn=>{
    btn.addEventListener('click',()=>{
      document.querySelectorAll('.hotspot').forEach(x=>x.classList.remove('active'));
      btn.classList.add('active');
      const d=diseaseData[btn.dataset.key];
      title.textContent=d.title;
      text.textContent=d.text;
    });
  });

  document.querySelectorAll('.signalCanvas').forEach(cv=>{
    const c=cv.getContext('2d'), W=cv.width,H=cv.height, mode=cv.dataset.mode;
    c.clearRect(0,0,W,H);
    c.strokeStyle='rgba(170,200,228,.09)';
    for(let g=1;g<6;g++){c.beginPath();c.moveTo(g*W/6,0);c.lineTo(g*W/6,H);c.stroke()}
    function f(t,variant){
      if(mode==='pressure') return .45+.23*Math.sin(t*6.283-.35)+.075*Math.sin(t*12.566+.55)+(variant?.035*Math.sin(t*6.283+.9):0);
      if(mode==='flow') return .43+.28*Math.sin(t*6.283-.6)+.10*Math.sin(t*12.566+.25)+(variant?.055*Math.sin(t*18.849+1.0):0);
      return .47+.13*Math.sin(t*6.283-.15)+.035*Math.sin(t*12.566+.42)+(variant?-.024*Math.sin(t*6.283+.8):0);
    }
    function draw(variant,color){
      c.beginPath();
      for(let i=0;i<W;i++){
        const t=i/(W-1), y=H*(.92-f(t,variant));
        i?c.lineTo(i,y):c.moveTo(i,y);
      }
      c.strokeStyle=color;c.lineWidth=2.2;c.stroke();
    }
    draw(false,'rgba(85,220,236,.95)');
    draw(true,'rgba(255,103,93,.96)');
  });

  const cv=document.getElementById('populationCanvas'), c=cv.getContext('2d'), W=cv.width,H=cv.height;
  function frac(x){return x-Math.floor(x)}
  function h(i,k){return frac(Math.sin(i*12.9898+k*78.233)*43758.5453)}
  c.clearRect(0,0,W,H);
  for(let i=1;i<=4374;i++){
    const x=.07 + .86*((h(i,1)+h(i+11,2)+h(i+31,3))/3);
    const y=.08 + .83*((h(i,4)+h(i+17,5)+h(i+47,6))/3);
    const edge=(i%31<5);
    c.beginPath();c.arc(x*W,y*H,edge?1.8:1.15,0,Math.PI*2);
    c.fillStyle=edge?'rgba(196,50,36,.58)':'rgba(62,117,187,.34)';c.fill();
  }
})();
