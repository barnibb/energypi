(() => {
 const el=id=>document.getElementById(id),dialog=el('weather-dialog'),canvas=el('weather-chart');
 const nf=new Intl.NumberFormat('de-DE',{minimumFractionDigits:1,maximumFractionDigits:1});
 const clock=timestamp=>timestamp==null?'—':new Date(timestamp*1000).toLocaleTimeString('de-DE',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit'});
 const duration=seconds=>{if(seconds==null)return '—';const total=Math.round(seconds/60),hours=Math.floor(total/60),minutes=total%60;return hours+' '+(hours===1?'Stunde':'Stunden')+' und '+minutes+' '+(minutes===1?'Minute':'Minuten');};
 const today=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Berlin'}).format(new Date());
 let payload=null,scale=null,generation=0,request=null;
 function dayOffset(offset,base=today()){const date=new Date(base+'T12:00:00Z');date.setUTCDate(date.getUTCDate()+offset);return date.toISOString().slice(0,10);}
 function shiftSelectedDay(offset){const input=el('weather-date');if(!input.value)return;input.value=dayOffset(offset,input.value);load();}
 async function load(){
  const id=++generation;request?.abort();request=new AbortController();const controller=request;const timeout=setTimeout(()=>controller.abort(),8000);
  payload=null;el('weather-history-status').textContent='Temperaturdaten werden geladen …';el('weather-extremes').textContent='';el('weather-history-tooltip').textContent='Kurve berühren oder mit der Maus darüberfahren.';draw();
  try{
   const response=await fetch('/api/weather/history?date='+encodeURIComponent(el('weather-date').value),{signal:controller.signal,cache:'no-store'});
   if(!response.ok)throw Error();const data=await response.json();if(id!==generation)return;payload=data;
   const sevilla=data.sevilla||{segments:[],count:0,minimum:null,maximum:null};
   const siteName=data.site_name||'Anlagenstandort';
   const dateLabel=new Date(data.day+'T12:00:00').toLocaleDateString('de-DE');
   el('weather-history-status').textContent=(data.count||sevilla.count)?dateLabel+' · '+siteName+' '+data.count+' Werte · Sevilla '+sevilla.count+' Werte':'Keine Temperaturdaten gespeichert.';
   el('weather-sunrise').textContent=clock(data.sunrise);el('weather-sunset').textContent=clock(data.sunset);el('weather-daylight').textContent=duration(data.daylight_seconds);
   el('weather-sun-source').textContent=data.polar_state==='polar_night'?'Polarnacht':data.polar_state==='midnight_sun'?'Mitternachtssonne':data.source+' für '+siteName+' · lokale Ortszeit';
   el('weather-sevilla-sunrise').textContent=clock(sevilla.sunrise);el('weather-sevilla-sunset').textContent=clock(sevilla.sunset);el('weather-sevilla-daylight').textContent=duration(sevilla.daylight_seconds);
   el('weather-sevilla-sun-source').textContent=sevilla.polar_state==='polar_night'?'Polarnacht':sevilla.polar_state==='midnight_sun'?'Mitternachtssonne':sevilla.source+' für Sevilla · spanische Ortszeit';
   const ranges=[];if(data.count)ranges.push(siteName+' '+nf.format(data.minimum)+' bis '+nf.format(data.maximum)+' °C');if(sevilla.count)ranges.push('Sevilla '+nf.format(sevilla.minimum)+' bis '+nf.format(sevilla.maximum)+' °C');el('weather-extremes').textContent=ranges.join(' · ');draw();
  }catch(_){if(id===generation){el('weather-history-status').textContent='Temperaturverlauf konnte nicht geladen werden.';for(const name of ['weather-sunrise','weather-sunset','weather-daylight','weather-sevilla-sunrise','weather-sevilla-sunset','weather-sevilla-daylight'])el(name).textContent='—';draw();}}
  finally{clearTimeout(timeout);}
 }
 function draw(){
  if(!dialog.open)return;const rect=canvas.getBoundingClientRect(),W=rect.width,H=rect.height;if(!W||!H)return;
  const dpr=devicePixelRatio||1;canvas.width=W*dpr;canvas.height=H*dpr;const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);scale=null;
  if(!payload)return;
  const siteName=payload.site_name||'Anlagenstandort',site=payload.segments.flat(),sevilla=(payload.sevilla?.segments||[]).flat(),points=[...site,...sevilla],L=46,R=12,T=20,B=32;
  const values=points.map(point=>point.temperature_c);let low=values.length?Math.floor(Math.min(...values)-1):0,high=values.length?Math.ceil(Math.max(...values)+1):20;
  const x=t=>L+(t-payload.start)/(payload.end-payload.start)*(W-L-R),y=v=>H-B-(v-low)/(high-low)*(H-T-B);
  const sunrise=payload.sunrise,sunset=payload.sunset;
  if(Number.isFinite(sunrise)&&Number.isFinite(sunset)){const left=Math.max(L,x(sunrise)),right=Math.min(W-R,x(sunset));if(right>left){ctx.fillStyle='rgba(223,140,60,.07)';ctx.fillRect(left,T,right-left,H-T-B);}for(const [stamp,color,label] of [[sunrise,'#f0aa55',siteName+' ↑'],[sunset,'#d86f32',siteName+' ↓']]){ctx.strokeStyle=color;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x(stamp),T);ctx.lineTo(x(stamp),H-B);ctx.stroke();ctx.fillStyle=color;ctx.textAlign=stamp===sunrise?'left':'right';ctx.fillText(label+' '+clock(stamp),x(stamp)+(stamp===sunrise?4:-4),T+11);}}
  const sevillaSunrise=payload.sevilla?.sunrise,sevillaSunset=payload.sevilla?.sunset;
  if(Number.isFinite(sevillaSunrise)&&Number.isFinite(sevillaSunset)){for(const [stamp,color,label] of [[sevillaSunrise,'#72c477','Sevilla ↑'],[sevillaSunset,'#4f9c72','Sevilla ↓']]){ctx.save();ctx.setLineDash([5,4]);ctx.strokeStyle=color;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x(stamp),T);ctx.lineTo(x(stamp),H-B);ctx.stroke();ctx.restore();ctx.fillStyle=color;ctx.textAlign=stamp===sevillaSunrise?'left':'right';ctx.fillText(label+' '+clock(stamp),x(stamp)+(stamp===sevillaSunrise?4:-4),T+25);}}
  ctx.font='11px system-ui';ctx.fillStyle='#63756e';ctx.textAlign='right';
  for(let i=0;i<=4;i++){const v=low+(high-low)*i/4;ctx.beginPath();ctx.strokeStyle='#e5e9e5';ctx.moveTo(L,y(v));ctx.lineTo(W-R,y(v));ctx.stroke();ctx.fillText(nf.format(v),L-7,y(v)+4);}
  ctx.textAlign='left';ctx.fillText('°C',L,12);
  for(let i=0;i<=4;i++){const t=payload.start+(payload.end-payload.start)*i/4;ctx.textAlign=i===0?'left':i===4?'right':'center';ctx.fillText(i===4?'24:00':new Date(t*1000).toLocaleTimeString('de-DE',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit'}),x(t),H-8);}
  function curve(segments,color){ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=2;for(const segment of segments){ctx.beginPath();segment.forEach((p,i)=>{if(i===0)ctx.moveTo(x(p.ts),y(p.temperature_c));else ctx.lineTo(x(p.ts),y(p.temperature_c));});ctx.stroke();for(const p of segment){ctx.beginPath();ctx.arc(x(p.ts),y(p.temperature_c),2,0,2*Math.PI);ctx.fill();}}}
  curve(payload.segments,'#df8c3c');curve(payload.sevilla?.segments||[],'#72c477');
  scale={L,R,W,site,sevilla};
 }
 canvas.addEventListener('pointermove',event=>{
  if(!scale||!payload)return;const t=payload.start+(event.clientX-canvas.getBoundingClientRect().left-scale.L)/(scale.W-scale.L-scale.R)*(payload.end-payload.start);
  const nearest=points=>{let result=null;for(const p of points)if(!result||Math.abs(p.ts-t)<Math.abs(result.ts-t))result=p;return result&&Math.abs(result.ts-t)<=600?result:null;};
  const b=nearest(scale.site),k=nearest(scale.sevilla),parts=[];if(b)parts.push((payload.site_name||'Anlagenstandort')+' '+nf.format(b.temperature_c)+' °C');if(k)parts.push('Sevilla '+nf.format(k.temperature_c)+' °C');const time=b?.ts||k?.ts;
  el('weather-history-tooltip').textContent=parts.length?new Date(time*1000).toLocaleTimeString('de-DE',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit'})+' · '+parts.join(' · '):'Keine Wetterwerte an dieser Stelle.';
 });
 el('weather-open').onclick=()=>{el('weather-date').value=today();el('weather-date').max=today();dialog.showModal();load();};
 el('weather-close').onclick=()=>dialog.close();
 dialog.addEventListener('close',()=>{generation++;request?.abort();el('weather-open').focus();});
 el('weather-previous-day').onclick=()=>shiftSelectedDay(-1);
 el('weather-today').onclick=()=>{el('weather-date').value=today();load();};
 el('weather-next-day').onclick=()=>shiftSelectedDay(1);
 el('weather-date').onchange=()=>{if(el('weather-date').value)load();};
 new ResizeObserver(draw).observe(canvas);
 setInterval(()=>{if(dialog.open&&el('weather-date').value===today())load();},60000);
})();
