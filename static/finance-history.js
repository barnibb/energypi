'use strict';
(() => {
 const el=id=>document.getElementById(id),dialog=el('finance-history-dialog'),canvas=el('finance-history-chart');
 const number=new Intl.NumberFormat('de-DE',{minimumFractionDigits:1,maximumFractionDigits:1});
 const money=new Intl.NumberFormat('de-DE',{style:'currency',currency:'EUR'});
 let payload=null,scale=null,generation=0,request=null,week=null,view='price';
 const dateObject=day=>new Date(day+'T12:00:00Z');
 const weekday=day=>dateObject(day).toLocaleDateString('de-DE',{weekday:'short',timeZone:'Europe/Berlin'}).replace('.','');
 const shortDate=day=>dateObject(day).toLocaleDateString('de-DE',{day:'2-digit',month:'2-digit',timeZone:'Europe/Berlin'});
 const rangeDate=day=>dateObject(day).toLocaleDateString('de-DE',{day:'2-digit',month:'2-digit',year:'numeric',timeZone:'Europe/Berlin'});
 const fullDate=day=>dateObject(day).toLocaleDateString('de-DE',{weekday:'long',day:'2-digit',month:'2-digit',year:'numeric',timeZone:'Europe/Berlin'});
 const isoDay=date=>date.toISOString().slice(0,10);
 const currentWeek=()=>{const d=dateObject(new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Berlin'}).format(new Date())),weekday=d.getUTCDay()||7;d.setUTCDate(d.getUTCDate()-weekday+1);return isoDay(d);};
 const shiftWeek=offset=>{const d=dateObject(week||currentWeek());d.setUTCDate(d.getUTCDate()+offset*7);week=isoDay(d);load();};
 const formatMoney=value=>Number.isFinite(value)?money.format(value):'—';
 function updateSummary(){
  const summary=payload?.summary||{};el('finance-week-summary').hidden=view!=='money';
  el('finance-summary-benefit').textContent=formatMoney(summary.benefit_eur);
  el('finance-summary-cost').textContent=formatMoney(summary.net_cost_eur);
  el('finance-summary-reference').textContent=formatMoney(summary.cost_without_self_supply_eur);
  el('finance-summary-share').textContent=Number.isFinite(summary.self_supply_percent)?number.format(summary.self_supply_percent)+' %':'—';
 }
 function setView(next){
  view=next;el('finance-view-price').setAttribute('aria-pressed',view==='price');el('finance-view-money').setAttribute('aria-pressed',view==='money');
  el('finance-history-title').textContent=view==='price'?'Effektiver Haushaltsstrompreis · 7 Tage':'Eigenversorgung und Energiekosten · 7 Tage';
  el('finance-history-explanation').textContent=view==='price'?'Jeder Balken zeigt die verbleibenden Stromkosten eines Tages je verbrauchter Kilowattstunde: Netzbezugskosten abzüglich Einspeisevergütung, geteilt durch den gesamten Hausverbrauch.':'Grün zeigt den rechnerischen Nutzen aus PV-Eigenverbrauch, Einspeisevergütung und Akkuabgabe. Orange zeigt die verbleibenden Energiekosten nach Abzug der Einspeisevergütung.';
  el('finance-history-note').textContent=view==='price'?'Ein niedriger Wert bedeutet, dass PV-Erzeugung und Einspeisevergütung die Stromkosten stark verringert haben. Ein negativer Wert bedeutet, dass die Einspeisevergütung höher war als die Netzbezugskosten. Grundgebühr, Anschaffungskosten von PV und Akku sowie Akkuverschleiß sind nicht enthalten.':'Der Vergleichswert ohne Eigenversorgung ist die Summe aus verbleibenden Energiekosten und berechnetem Nutzen. Akku-Abgabe ist ein Bruttowert; Ladeverluste, Ladekosten, Verschleiß, Grundgebühren und Anschaffungskosten sind nicht enthalten.';
  canvas.setAttribute('aria-label',view==='price'?'Effektiver Haushaltsstrompreis der gewählten Kalenderwoche in Cent pro Kilowattstunde':'Nutzen der Eigenversorgung und verbleibende Energiekosten der gewählten Kalenderwoche in Euro');
  el('finance-history-tooltip').textContent='Balken berühren oder mit der Maus darüberfahren.';updateSummary();draw();
 }
 async function load(){
  const id=++generation;request?.abort();request=new AbortController();const controller=request;const timeout=setTimeout(()=>controller.abort(),60000);
  payload=null;scale=null;el('finance-history-status').textContent='Tageswerte werden geladen …';el('finance-history-tooltip').textContent='Balken berühren oder mit der Maus darüberfahren.';updateSummary();draw();
  try{const response=await fetch('/api/finance/history?days=7&week='+encodeURIComponent(week),{signal:controller.signal,cache:'no-store'});if(!response.ok)throw Error();const data=await response.json();if(id!==generation)return;payload=data;
   const count=data.points.filter(p=>p.complete).length;el('finance-week-current').setAttribute('aria-pressed',week===currentWeek());el('finance-week-label').textContent='KW '+data.week_number+' / '+data.week_year+' · '+shortDate(data.week_start)+'–'+rangeDate(data.week_end);el('finance-history-status').textContent=count+' von 7 Tagen vollständig'+(data.points.some(p=>p.today)?' · der heutige Balken zeigt den bisherigen Tagesstand.':'.');updateSummary();draw();
  }catch(_){if(id===generation){el('finance-history-status').textContent='Wochenvergleich konnte nicht geladen werden.';draw();}}
  finally{clearTimeout(timeout);}
 }
 function draw(){
  if(!dialog.open)return;const rect=canvas.getBoundingClientRect(),W=rect.width,H=rect.height;if(!W||!H)return;
  const dpr=devicePixelRatio||1;canvas.width=W*dpr;canvas.height=H*dpr;const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);scale=null;if(!payload)return;
  const points=payload.points,L=54,R=14,T=22,B=56;
  const values=points.filter(p=>p.complete).flatMap(p=>view==='price'?[p.effective_house_price_ct]:[p.benefit_eur,p.net_cost_eur]).filter(Number.isFinite);
  const step=view==='price'?5:1,minimum=Math.min(0,...values),maximum=Math.max(0,...values),low=Math.min(view==='price'?-5:0,Math.floor(minimum/step)*step),high=Math.max(step,Math.ceil(maximum/step)*step);
  const plotW=W-L-R,slot=plotW/points.length,bar=Math.min(view==='price'?42:25,slot*(view==='price' ? .58 : .32)),y=value=>T+(high-value)/(high-low)*(H-T-B),zero=y(0);
  ctx.font='11px system-ui';ctx.textAlign='right';ctx.fillStyle='#94a0aa';
  for(let value=low;value<=high+.001;value+=step){const zeroLine=Math.abs(value)<.001;ctx.strokeStyle=zeroLine?'#667d70':'#29313d';ctx.lineWidth=zeroLine?2:1;ctx.beginPath();ctx.moveTo(L,y(value));ctx.lineTo(W-R,y(value));ctx.stroke();ctx.fillText(number.format(value),L-7,y(value)+4);}ctx.lineWidth=1;
  ctx.textAlign='left';ctx.fillText(view==='price'?'ct/kWh':'€',L,12);const bars=[];
  points.forEach((point,index)=>{const center=L+slot*(index+.5);ctx.textAlign='center';ctx.fillStyle='#94a0aa';ctx.fillText(weekday(point.day),center,H-24);ctx.fillText(shortDate(point.day),center,H-8);
   if(!point.complete){ctx.strokeStyle='#65717b';ctx.setLineDash([3,3]);ctx.strokeRect(center-slot*.28,T,slot*.56,H-T-B);ctx.setLineDash([]);ctx.fillText('—',center,T+18);bars.push({left:center-slot/2,right:center+slot/2,point});return;}
   if(view==='price'){const value=point.effective_house_price_ct,top=Math.min(y(value),zero),height=Math.max(2,Math.abs(y(value)-zero));ctx.fillStyle=point.today?(value<0?'#93bca2':'#9fbfd4'):(value<0?'#4f8a62':'#5a99cf');ctx.fillRect(center-bar/2,top,bar,height);}
   else [{value:point.benefit_eur,color:point.today?'#a9d9ad':'#72c477',offset:-bar*.62},{value:point.net_cost_eur,color:point.today?'#e5b482':'#df8c3c',offset:bar*.62}].forEach(item=>{if(!Number.isFinite(item.value))return;const top=Math.min(y(item.value),zero),height=Math.max(2,Math.abs(y(item.value)-zero));ctx.fillStyle=item.color;ctx.fillRect(center+item.offset-bar/2,top,bar,height);});
   bars.push({left:center-slot/2,right:center+slot/2,point});
  });scale={bars};
  const legend=el('finance-history-dialog').querySelector('.finance-legend');legend.innerHTML=view==='price'?'<span><i class="finance-positive"></i> Positiver Preis</span><span><i class="finance-negative"></i> Einspeisevergütung über Netzstromkosten</span><span><i class="finance-today"></i> Heute · noch nicht abgeschlossen</span><span><i class="finance-missing"></i> Daten unvollständig</span>':'<span><i class="finance-benefit"></i> Nutzen der Eigenversorgung</span><span><i class="finance-cost"></i> Verbleibende Energiekosten</span><span><i class="finance-today"></i> Heute · noch nicht abgeschlossen</span><span><i class="finance-missing"></i> Daten unvollständig</span>';
 }
 function show(event){if(!scale)return;const x=event.clientX-canvas.getBoundingClientRect().left,entry=scale.bars.find(bar=>x>=bar.left&&x<bar.right);if(!entry)return;const p=entry.point;
  if(!p.complete){el('finance-history-tooltip').textContent=fullDate(p.day)+' · Daten unvollständig; kein Tageswert berechnet.';return;}
  el('finance-history-tooltip').textContent=view==='price'
   ? fullDate(p.day)+(p.today?' · bisher':'')+' · Effektiver Haushaltsstrompreis: '+number.format(p.effective_house_price_ct)+' ct/kWh · Netzbezugskosten: '+money.format(p.import_cost_eur)+' · Einspeisevergütung: −'+money.format(p.feed_revenue_eur)+' · Verbleibende Stromkosten: '+money.format(p.net_cost_eur)+' · Hausverbrauch: '+number.format(p.house_kwh)+' kWh'
   : fullDate(p.day)+(p.today?' · bisher':'')+' · Nutzen der Eigenversorgung: '+formatMoney(p.benefit_eur)+' · verbleibende Energiekosten: '+formatMoney(p.net_cost_eur)+' · Vergleich ohne Eigenversorgung: '+formatMoney(p.cost_without_self_supply_eur)+' · Eigenversorgungsanteil: '+(Number.isFinite(p.self_supply_percent)?number.format(p.self_supply_percent)+' %':'—')+' · PV-Nutzen: '+formatMoney(p.pv_benefit_eur)+' · Akku-Abgabe brutto: '+formatMoney(p.battery_value_eur)+' · Einspeisevergütung: '+formatMoney(p.feed_revenue_eur);
 }
 canvas.addEventListener('pointermove',show);canvas.addEventListener('pointerdown',show);
 el('finance-history-open').onclick=()=>{week=currentWeek();dialog.showModal();setView('price');load();};el('finance-history-close').onclick=()=>dialog.close();
 el('finance-view-price').onclick=()=>setView('price');el('finance-view-money').onclick=()=>setView('money');
 el('finance-week-previous').onclick=()=>shiftWeek(-1);el('finance-week-current').onclick=()=>{week=currentWeek();load();};el('finance-week-next').onclick=()=>shiftWeek(1);
 dialog.addEventListener('close',()=>{generation++;request?.abort();el('finance-history-open').focus();});new ResizeObserver(draw).observe(canvas);
})();
