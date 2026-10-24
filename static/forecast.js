'use strict';
(() => {
 const el=id=>document.getElementById(id),nf=new Intl.NumberFormat('de-DE',{maximumFractionDigits:1});
 const dateNow=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Berlin'}).format(new Date());
 const stamp=t=>new Date(t*1000).toLocaleString('de-DE',{timeZone:'Europe/Berlin'});
 const kwh=v=>v===null||v===undefined?'—':nf.format(v)+' kWh';
 let payload=null,selected='today',generation=0,scale=null;
 el('forecast-date').value=dateNow();
 function relativeDay(offset){const d=new Date(dateNow()+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+offset);return d.toISOString().slice(0,10);}
 function shiftSelectedDay(offset){const input=el('forecast-date'),d=new Date(input.value+'T12:00:00Z');if(Number.isNaN(d.getTime()))return;d.setUTCDate(d.getUTCDate()+offset);input.value=d.toISOString().slice(0,10);selected='custom';refresh();}
 async function refresh(){
  const id=++generation;if(selected!=='custom')el('forecast-date').value=relativeDay(selected==='tomorrow'?1:0);
  try{const r=await fetch('/api/forecast?date='+encodeURIComponent(el('forecast-date').value),{signal:AbortSignal.timeout(8000),cache:'no-store'});if(!r.ok)throw Error();const p=await r.json();if(id!==generation)return;payload=p;
   if(p.site&&el('forecast-site-label'))el('forecast-site-label').textContent=(p.site.name+' · '+nf.format(p.site.kwp)+' kWp · Ausrichtung '+nf.format(p.site.azimuth)+'° · '+nf.format(p.site.tilt)+'°').toUpperCase();
   el('forecast-today').textContent=kwh(p.today_kwh);el('forecast-remaining').textContent=kwh(p.remaining_kwh);el('forecast-tomorrow').textContent=kwh(p.tomorrow_kwh);
   el('forecast-cards-note').textContent=p.cards_stale?'Karten: Prognose fehlt oder ist älter als vier Stunden.':'Karten beziehen sich auf heute und morgen.';
   el('energy-today-value').textContent=kwh(p.today_energy?.kwh);
   el('energy-today-time').textContent=p.today_energy?'Abgerufen: '+stamp(p.today_energy.fetched_at)+(Date.now()/1000-p.today_energy.fetched_at>7200?' · veraltet':''):'Noch keine SolarEdge-Energiedaten für heute.';
   el('energy-value').hidden=el('energy-time').hidden=p.day===dateNow();
   const archived=p.day<dateNow();
   el('forecast-state').textContent=p.forecast?('Prognosestand: '+stamp(p.forecast.issued_at)+(archived?' · archivierte Prognose':p.stale?' · veraltet':'')):'Für diesen Tag liegt noch keine Prognose vor.';
   if(p.message&&!archived)el('forecast-state').textContent+=' · Letzter Abruf fehlgeschlagen';
   el('energy-value').textContent='SolarEdge-Tagesertrag '+p.day+': '+kwh(p.energy?.kwh)+(p.day===dateNow()&&p.energy?' · bisher':'');
   el('energy-time').textContent=p.energy?'Abgerufen: '+stamp(p.energy.fetched_at)+((p.day===dateNow()&&Date.now()/1000-p.energy.fetched_at>7200)?' · veraltet':''):'Noch keine SolarEdge-Energiedaten für diesen Tag.';
   draw();
  }catch(e){if(id!==generation)return;el('forecast-state').textContent='Anzeige konnte nicht aktualisiert werden. Werte möglicherweise veraltet.';el('energy-today-time').textContent='Aktualisierung fehlgeschlagen · Wert möglicherweise veraltet.';payload=null;draw();}
 }
 function draw(){const c=el('forecast-chart'),r=c.getBoundingClientRect(),dpr=devicePixelRatio||1;c.width=r.width*dpr;c.height=r.height*dpr;const ctx=c.getContext('2d');ctx.scale(dpr,dpr);
  const W=r.width,H=r.height,L=42,R=46,T=18,B=32;
  const pred=payload?.forecast?.points||[],actual=payload?.actual||[],all=[...pred,...actual.flat()];let max=1000;for(const p of all)max=Math.max(max,p.w);max=Math.ceil(max/1000)*1000;
  const socSegments=payload?.battery?.segments||[],socPoints=socSegments.flat();
  const start=payload?.view_start??payload?.start??0,end=payload?.view_end??payload?.end??86400;
  const x=t=>L+(t-start)/(end-start)*(W-L-R),y=w=>H-B-w/max*(H-T-B);scale={start,end,W,L,R,all};
  ctx.font='11px system-ui';ctx.fillStyle='#68776b';ctx.textAlign='right';
  for(let i=0;i<=4;i++){const w=max*i/4;ctx.strokeStyle='#e5eadd';ctx.beginPath();ctx.moveTo(L,y(w));ctx.lineTo(W-R,y(w));ctx.stroke();ctx.fillText(nf.format(w/1000),L-7,y(w)+4);}
  ctx.textAlign='left';ctx.fillText('kW',L,12);
  const sy=v=>H-B-v/100*(H-T-B);ctx.fillStyle='#8958ab';
  for(let i=0;i<=4;i++)ctx.fillText(String(i*25),W-R+7,sy(i*25)+4);
  ctx.fillText('%',W-R+7,12);ctx.fillStyle='#68776b';
  for(let i=0;i<=4;i++){const t=start+(end-start)*i/4;ctx.textAlign=i===0?'left':i===4?'right':'center';ctx.fillText(i===4&&payload?.view_end_hour===24?'24:00':new Date(t*1000).toLocaleTimeString('de-DE',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit'}),x(t),H-8);}
  function line(points,color,dashed){ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=2;ctx.setLineDash(dashed?[6,5]:[]);ctx.beginPath();let prev=null;for(const p of points){if(prev===null||(p.ts-prev)>(dashed?7500:1800))ctx.moveTo(x(p.ts),y(p.w));else ctx.lineTo(x(p.ts),y(p.w));prev=p.ts;}ctx.stroke();ctx.setLineDash([]);if(points.length===1){ctx.beginPath();ctx.arc(x(points[0].ts),y(points[0].w),3,0,Math.PI*2);ctx.fill();}}
  ctx.save();ctx.beginPath();ctx.rect(L,T,W-L-R,H-T-B);ctx.clip();
  line(pred,'#b18136',true);for(const segment of actual)line(segment,'#365e4d',false);
  ctx.strokeStyle='#8958ab';ctx.fillStyle='#8958ab';ctx.lineWidth=2;
  for(const segment of socSegments){ctx.beginPath();segment.forEach((p,i)=>{if(i===0)ctx.moveTo(x(p.ts),sy(p.soc));else ctx.lineTo(x(p.ts),sy(p.soc));});ctx.stroke();if(segment.length===1){ctx.beginPath();ctx.arc(x(segment[0].ts),sy(segment[0].soc),3,0,Math.PI*2);ctx.fill();}}
  ctx.restore();
  el('forecast-empty').hidden=[...all,...socPoints].some(p=>p.ts>=start&&p.ts<=end);el('forecast-empty').textContent='Im gewählten Zeitbereich liegen noch keine Kurvenwerte vor.';
 }
 el('forecast-chart').addEventListener('pointermove',e=>{if(!scale||!payload)return;const s=scale,px=e.clientX-el('forecast-chart').getBoundingClientRect().left,t=s.start+(px-s.L)/(s.W-s.L-s.R)*(s.end-s.start);
  const series=[['Prognose',payload.forecast?.points||[],3700],['SolarEdge',payload.actual.flat(),1000],['Akku',payload.battery?.segments?.flat()||[],90]];
  el('forecast-tooltip').textContent=series.map(([name,points,tolerance])=>{let nearest=null;for(const p of points.filter(p=>p.ts>=s.start&&p.ts<=s.end))if(!nearest||Math.abs(p.ts-t)<Math.abs(nearest.ts-t))nearest=p;return nearest&&Math.abs(nearest.ts-t)<=tolerance?name+' '+new Date(nearest.ts*1000).toLocaleTimeString('de-DE',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit'})+': '+(name==='Akku'?nf.format(nearest.soc)+' %':nf.format(nearest.w/1000)+' kW'):name+': keine Daten';}).join(' · ');
 });
 el('forecast-today-button').onclick=()=>{selected='today';refresh();};
 const forecastTomorrow=el('forecast-tomorrow-button'),forecastPrevious=el('forecast-previous-day'),forecastNext=el('forecast-next-day');
 if(forecastTomorrow)forecastTomorrow.onclick=()=>{selected='tomorrow';refresh();};
 if(forecastPrevious)forecastPrevious.onclick=()=>shiftSelectedDay(-1);
 if(forecastNext)forecastNext.onclick=()=>shiftSelectedDay(1);
 el('forecast-date').onchange=()=>{selected='custom';refresh();};
 window.addEventListener('energypi-settings',refresh);
 new ResizeObserver(draw).observe(el('forecast-chart'));
 async function poll(){await refresh();setTimeout(poll,60000);}poll();
})();
