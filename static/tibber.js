'use strict';
(() => {
 const el=id=>document.getElementById(id),fmt=new Intl.NumberFormat('de-DE',{minimumFractionDigits:1,maximumFractionDigits:2});
 const today=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Berlin'}).format(new Date());
 const time=t=>new Date(t*1000).toLocaleTimeString('de-DE',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit',timeZoneName:'short'});
 window.addEventListener('energypi-settings',()=>refresh());
 let selected='today',payload=null,todayPayload=null,scale=null,generation=0,hoveredStart=null;
 function day(offset){const d=new Date(today()+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+offset);return d.toISOString().slice(0,10);}
 function shiftSelectedDay(offset){const input=el('tibber-date'),d=new Date(input.value+'T12:00:00Z');if(Number.isNaN(d.getTime()))return;d.setUTCDate(d.getUTCDate()+offset);input.value=d.toISOString().slice(0,10);change('custom');}
 el('tibber-date').value=today();
 function number(v){return v===null||v===undefined?'—':fmt.format(v);}
 function renderLivePrice(p){if(!p)return;el('tibber-current').textContent=number(p.current_ct);el('tibber-live-min').textContent=p.min_ct==null?'—':number(p.min_ct)+' ct/kWh';el('tibber-live-max').textContent=p.max_ct==null?'—':number(p.max_ct)+' ct/kWh';el('tibber-live-range-status').textContent=p.points?.length?(p.complete?'Heutige Tagespreise vollständig':'Heute noch nicht vollständig veröffentlicht'):'';}
 function resetHover(){hoveredStart=null;el('tibber-tooltip').textContent='Balken oder PV-Band berühren, um Preis, PV-Überschuss und Akku-Grenzen zu sehen.';}
 async function refresh(){const id=++generation;
  if(selected!=='custom')el('tibber-date').value=day(selected==='tomorrow'?1:0);
  try{const r=await fetch('/api/tibber?date='+encodeURIComponent(el('tibber-date').value),{signal:AbortSignal.timeout(8000),cache:'no-store'});if(!r.ok)throw Error();const p=await r.json();if(id!==generation)return;payload=p;if(el('tibber-date').value===today()){todayPayload=p;renderLivePrice(todayPayload);}el('pv-threshold-note').textContent='PV ab ca. '+number(p.pv_threshold_w/1000)+' kW: '+number(p.base_load_w)+' W Grundlast plus '+number(p.ev_power_w/1000)+' kW Laden mit '+number(p.ev_current_a)+' A dreiphasig.';
   el('tibber-min').textContent=number(p.min_ct);el('tibber-max').textContent=number(p.max_ct);
   el('tibber-state').textContent=p.fetched_at?'Abgerufen: '+new Date(p.fetched_at*1000).toLocaleString('de-DE',{timeZone:'Europe/Berlin'})+(p.complete?' · Tagespreise vollständig':' · Tagespreise unvollständig'):(p.pending?'Für diesen Tag noch keine veröffentlichten Preise gespeichert.':'Noch nicht eingerichtet oder noch keine Preise gespeichert.');
   if(p.error)el('tibber-state').textContent+=' · '+p.error;
   el('tibber-average').textContent=p.average_ct!==null?(p.complete?'Tagesmittel: ':'Mittel der vorhandenen Intervalle: ')+number(p.average_ct)+' ct/kWh · '+p.points.length+' Viertelstunden':'';
   const pvNote={available:'PV-Prognose verfügbar',archive:'Archivierte PV-Prognose',stale:'PV-Prognose veraltet; gelbe Markierung ausgesetzt',missing:'PV-Prognose fehlt'};
   const gridLimit=p.battery_grid_threshold_ct==null?'Netzlade-Grenze nicht bestimmbar':'Netzladung zu aktuell '+number(p.battery_grid_reference_ct)+' ct: Entladung ab '+number(p.battery_grid_threshold_ct)+' ct/kWh';
   el('tibber-opportunities').textContent=(pvNote[p.pv_state]||'PV-Prognose fehlt')+(p.pv_issued_at?' · Abruf '+new Date(p.pv_issued_at*1000).toLocaleString('de-DE',{timeZone:'Europe/Berlin'}):'')+'. '+(p.cheap_threshold_ct!==null?'Günstiges Viertel bis '+number(p.cheap_threshold_ct)+' ct/kWh'+(p.complete?'':' (nur vorhandene Preise)')+'. Preisgleichstände werden mitmarkiert.':'Keine relative Preismarkierung bei fehlenden oder identischen Preisen.')+' Akku-Modell: PV-Entladung ab '+number(p.battery_pv_threshold_ct)+' ct/kWh · '+gridLimit+'.';
   draw();drawMini();
  }catch(e){if(id!==generation)return;payload=null;resetHover();el('tibber-state').textContent='Anzeige nicht erreichbar. Preise möglicherweise veraltet.';for(const id of ['tibber-min','tibber-max'])el(id).textContent='—';if(!todayPayload){for(const id of ['tibber-current','tibber-live-min','tibber-live-max'])el(id).textContent='—';el('tibber-live-range-status').textContent='Heutige Preise nicht erreichbar.';}el('tibber-average').textContent='';el('tibber-opportunities').textContent='';draw();drawMini();}
 }
 function drawMini(){const c=el('tibber-mini-chart');if(!c)return;const r=c.getBoundingClientRect(),dpr=devicePixelRatio||1;c.width=r.width*dpr;c.height=r.height*dpr;const ctx=c.getContext('2d');ctx.scale(dpr,dpr);ctx.clearRect(0,0,r.width,r.height);
  const points=(todayPayload?.points||[]).filter(p=>Number.isFinite(p.ct));if(points.length<2)return;
  let low=Math.min(...points.map(p=>p.ct)),high=Math.max(...points.map(p=>p.ct));if(high===low){low-=1;high+=1;}const pad=3,x=i=>pad+i/(points.length-1)*(r.width-pad*2),y=v=>pad+(high-v)/(high-low)*(r.height-pad*2);
  const gradient=ctx.createLinearGradient(0,0,r.width,0);gradient.addColorStop(0,'#a78027');gradient.addColorStop(1,'#f0cb5d');ctx.strokeStyle=gradient;ctx.lineWidth=2;ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(x(i),y(p.ct)):ctx.moveTo(x(i),y(p.ct)));ctx.stroke();
  const now=Date.now()/1000,index=points.findIndex(p=>p.start<=now&&now<p.end);if(index>=0){ctx.fillStyle='#fff1a6';ctx.beginPath();ctx.arc(x(index),y(points[index].ct),3,0,Math.PI*2);ctx.fill();}
 }
 function draw(){const c=el('tibber-chart'),r=c.getBoundingClientRect(),dpr=devicePixelRatio||1;c.width=r.width*dpr;c.height=r.height*dpr;const ctx=c.getContext('2d');ctx.scale(dpr,dpr);
  if(!payload){
   scale=null;el('tibber-empty').hidden=false;
   el('tibber-empty').textContent='Keine Diagrammdaten geladen.';
   return;
  }
  const W=r.width,H=r.height,L=42,R=12,T=58,B=34,points=payload?.points||[],slots=payload?.slots||[];
  let low=0,high=10;for(const p of points){low=Math.min(low,p.ct);high=Math.max(high,p.ct);}for(const v of [payload.feed_in_ct,payload.battery_pv_threshold_ct,payload.battery_grid_threshold_ct])if(Number.isFinite(v)){low=Math.min(low,v);high=Math.max(high,v);}low=Math.floor(low/5)*5;high=Math.ceil(high/5)*5;
  const start=payload?.start||0,end=payload?.end||86400,x=t=>L+(t-start)/(end-start)*(W-L-R),y=v=>T+(high-v)/(high-low)*(H-T-B);scale={W,H,L,R,T,B,start,end};
  // Ein gemeinsamer Zeitmaßstab für Preise und das unabhängige PV-Band.
  ctx.fillStyle='#f5f2e8';ctx.fillRect(L,23,W-L-R,14);
  for(const slot of slots){
   if(slot.cheap){ctx.fillStyle='#e0eef8';ctx.fillRect(x(slot.start),T,x(slot.end)-x(slot.start),H-B-T);}
   if(slot.pv_good){ctx.fillStyle=slot.start===hoveredStart?'#b77e13':'#edc653';ctx.fillRect(x(slot.start),23,x(slot.end)-x(slot.start),14);}
  }
  ctx.font='11px system-ui';ctx.fillStyle='#68776b';ctx.textAlign='left';ctx.fillText('PV potenziell ausreichend',L,14);ctx.fillText('ct/kWh',L,T-7);
  ctx.textAlign='right';for(let i=0;i<=4;i++){const v=low+(high-low)*i/4;ctx.strokeStyle='#dce5e7';ctx.beginPath();ctx.moveTo(L,y(v));ctx.lineTo(W-R,y(v));ctx.stroke();ctx.fillText(number(v),L-5,y(v)+4);}
  ctx.strokeStyle='#a3b2a8';ctx.beginPath();ctx.moveTo(L,y(0));ctx.lineTo(W-R,y(0));ctx.stroke();
  const now=Date.now()/1000;for(const p of points){const current=p.start<=now&&now<p.end;ctx.fillStyle=current?'#faf264':p.start===hoveredStart?(p.ct<0?'#205d3b':'#24546f'):(p.ct<0?'#4b8a69':'#799aaf');const a=y(Math.max(0,p.ct)),b=y(Math.min(0,p.ct));ctx.fillRect(x(p.start)+.3,a,Math.max(.4,x(p.end)-x(p.start)-.6),Math.max(1,b-a));if(p.start===hoveredStart||current){ctx.strokeStyle='#233f48';ctx.strokeRect(x(p.start),a,Math.max(1,x(p.end)-x(p.start)),Math.max(1,b-a));}
   if(p.ct<payload.feed_in_ct){ctx.fillStyle='#174660';ctx.beginPath();ctx.arc(x((p.start+p.end)/2),y(p.ct),2,0,Math.PI*2);ctx.fill();}}
  ctx.setLineDash([5,4]);ctx.strokeStyle='#ac7722';ctx.beginPath();ctx.moveTo(L,y(payload.feed_in_ct));ctx.lineTo(W-R,y(payload.feed_in_ct));ctx.stroke();ctx.setLineDash([]);
  ctx.fillStyle='#fff8e6';ctx.fillRect(W-R-77,y(payload.feed_in_ct)-15,77,14);ctx.fillStyle='#805611';ctx.textAlign='right';ctx.fillText(number(payload.feed_in_ct)+' ct/kWh',W-R-3,y(payload.feed_in_ct)-4);
  function limitLine(value,color,dash,label,labelOffset){if(!Number.isFinite(value))return;ctx.setLineDash(dash);ctx.strokeStyle=color;ctx.beginPath();ctx.moveTo(L,y(value));ctx.lineTo(W-R,y(value));ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#ffffffeb';const width=Math.min(188,ctx.measureText(label).width+10);ctx.fillRect(W-R-width,y(value)-15+labelOffset,width,14);ctx.fillStyle=color;ctx.textAlign='right';ctx.fillText(label,W-R-3,y(value)-4+labelOffset);}
  limitLine(payload.battery_pv_threshold_ct,'#4f7d3b',[8,4],'PV-Akku ab '+number(payload.battery_pv_threshold_ct)+' ct',0);
  limitLine(payload.battery_grid_threshold_ct,'#76529a',[3,4],'Netz-Akku ab '+number(payload.battery_grid_threshold_ct)+' ct',0);
  for(let i=0;i<=4;i++){ctx.textAlign=i===0?'left':i===4?'right':'center';ctx.fillStyle='#68776b';ctx.fillText(new Date((start+(end-start)*i/4)*1000).toLocaleTimeString('de-DE',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit'}),x(start+(end-start)*i/4),H-8);}
  const hovered=slots.find(p=>p.start===hoveredStart);
  if(hovered){
   const lines=[time(hovered.start)+' – '+time(hovered.end),hovered.ct===null?'Tibber: kein Preis':number(hovered.ct)+' ct/kWh'];
   if(hovered.cheap)lines.push('Günstiges Preisviertel');
   if(hovered.below_feed_in)lines.push('Unter '+number(payload.feed_in_ct)+' ct Einspeisevergütung');
   lines.push('PV-Akku wirtschaftlich ab '+number(payload.battery_pv_threshold_ct)+' ct/kWh');
   if(payload.battery_grid_threshold_ct!==null)lines.push('Netz-Akku bei '+number(payload.battery_grid_reference_ct)+' ct Ladepreis ab '+number(payload.battery_grid_threshold_ct)+' ct/kWh');
   lines.push(hovered.pv_surplus_w===null?'PV: keine aktuelle Prognose':'PV-Überschuss ca. '+number(hovered.pv_surplus_w/1000)+' kW');
   if(hovered.pv_good)lines.push('PV potenziell ausreichend');
   ctx.font='12px system-ui';const width=Math.min(W-12,Math.max(...lines.map(line=>ctx.measureText(line).width))+20),height=lines.length*18+12;
   const left=Math.max(6,Math.min(W-width-6,x((hovered.start+hovered.end)/2)-width/2));const top=Math.max(42,Math.min(H-B-height-6,(hovered.ct===null?T:y(Math.max(0,hovered.ct)))-height-10));
   ctx.fillStyle='#203f4d';ctx.fillRect(left,top,width,height);ctx.fillStyle='#fff';ctx.textAlign='left';lines.forEach((line,i)=>ctx.fillText(line,left+10,top+18+i*18,width-20));el('tibber-tooltip').textContent=lines.join(' · ');
  }else resetHover();
  el('tibber-empty').hidden=points.length>0||slots.some(p=>p.pv_good);el('tibber-empty').textContent=payload?.pending?'Noch keine Preise für diesen Tag.':'Noch keine Preise für diesen Tag gespeichert.';
 }
 function pointAtPointer(e){if(!payload||!scale)return;const s=scale,r=el('tibber-chart').getBoundingClientRect(),px=e.clientX-r.left,py=e.clientY-r.top,inside=px>=s.L&&px<s.W-s.R&&py>=23&&py<=s.H-s.B,t=s.start+(px-s.L)/(s.W-s.L-s.R)*(s.end-s.start);const p=inside?payload.slots?.find(p=>p.start<=t&&t<p.end):null;hoveredStart=p?.start??null;draw();}
 function clearHover(){resetHover();draw();}
 el('tibber-chart').addEventListener('pointermove',pointAtPointer);el('tibber-chart').addEventListener('pointerdown',pointAtPointer);el('tibber-chart').addEventListener('pointerleave',clearHover);el('tibber-chart').addEventListener('pointercancel',clearHover);
 function change(next){selected=next;payload=null;clearHover();el('tibber-state').textContent='Tagespreise werden geladen …';el('tibber-empty').textContent='Tagespreise werden geladen …';refresh();}
 el('tibber-today').onclick=()=>change('today');
 const tibberTomorrow=el('tibber-tomorrow'),tibberPrevious=el('tibber-previous-day'),tibberNext=el('tibber-next-day');
 if(tibberTomorrow)tibberTomorrow.onclick=()=>change('tomorrow');
 if(tibberPrevious)tibberPrevious.onclick=()=>shiftSelectedDay(-1);
 if(tibberNext)tibberNext.onclick=()=>shiftSelectedDay(1);
 el('tibber-date').onchange=()=>change('custom');
 new ResizeObserver(draw).observe(el('tibber-chart'));const mini=el('tibber-mini-chart');if(mini)new ResizeObserver(drawMini).observe(mini);
 async function poll(){await refresh();setTimeout(poll,60000);}poll();
})();
