'use strict';
(()=>{
 if(window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;
 const layer=document.createElement('div');layer.className='autumn-leaves';layer.setAttribute('aria-hidden','true');
 const leaves=[
  ['7%','6vw','-2vw','10vw','13vw','22s','-7s','145deg','285deg','420deg','520deg','#6fa34a'],
  ['22%','-4vw','3vw','-7vw','-9vw','27s','-19s','-170deg','-325deg','-480deg','-610deg','#c49d32'],
  ['39%','8vw','-3vw','13vw','17vw','19s','-3s','190deg','375deg','540deg','690deg','#dc7d2f'],
  ['57%','-6vw','2vw','-10vw','-13vw','25s','-14s','-155deg','-305deg','-440deg','-560deg','#a94c36'],
  ['73%','5vw','-2vw','8vw','10vw','21s','-10s','175deg','350deg','510deg','640deg','#d6b23c'],
  ['89%','-7vw','3vw','-12vw','-16vw','29s','-23s','-195deg','-390deg','-570deg','-720deg','#779c42'],
  ['48%','4vw','-2vw','6vw','8vw','31s','-27s','160deg','320deg','455deg','580deg','#bd5b32']
 ];
 for(const [left,d1,d2,d3,d4,duration,delay,s1,s2,s3,s4,color] of leaves){
  const leaf=document.createElement('i');leaf.className='autumn-leaf';leaf.style.setProperty('--left',left);leaf.style.setProperty('--drift-1',d1);leaf.style.setProperty('--drift-2',d2);leaf.style.setProperty('--drift-3',d3);leaf.style.setProperty('--drift-4',d4);leaf.style.setProperty('--duration',duration);leaf.style.setProperty('--delay',delay);leaf.style.setProperty('--spin-1',s1);leaf.style.setProperty('--spin-2',s2);leaf.style.setProperty('--spin-3',s3);leaf.style.setProperty('--spin-4',s4);leaf.style.setProperty('--leaf-color',color);layer.append(leaf);
 }
 const snow=[['13%','25s','-9s','7vw'],['29%','31s','-23s','-6vw'],['45%','27s','-16s','9vw'],['62%','34s','-28s','-8vw'],['78%','23s','-5s','6vw'],['94%','30s','-20s','-7vw']];
 for(const [left,duration,delay,drift] of snow){const crystal=document.createElement('i');crystal.className='frost-crystal';crystal.textContent='❄';crystal.style.setProperty('--left',left);crystal.style.setProperty('--duration',duration);crystal.style.setProperty('--delay',delay);crystal.style.setProperty('--snow-drift',drift);layer.append(crystal);}
 let threshold=0,temperature=null,weatherValid=false;
 const update=()=>layer.classList.toggle('frost-active',weatherValid&&Number.isFinite(temperature)&&temperature<=threshold);
 async function settings(){try{const response=await fetch('/api/preferences',{cache:'no-store',signal:AbortSignal.timeout(5000)});if(!response.ok)throw Error();const value=Number((await response.json()).values?.frost_temperature_c);if(Number.isFinite(value))threshold=value;update();}catch(_){}}
 window.addEventListener('energypi-settings',settings);
 window.addEventListener('energypi-weather',event=>{temperature=Number(event.detail?.temperature);weatherValid=Boolean(event.detail?.valid);update();});
 document.body.append(layer);settings();
})();
