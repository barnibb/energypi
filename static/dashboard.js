'use strict';
const $ = id => document.getElementById(id);
const colors = {total_act_power:'#365e4d', a_act_power:'#c78842', b_act_power:'#6888ba', c_act_power:'#a17aa5'};
const names = {total_act_power:'Gesamt',a_act_power:'A',b_act_power:'B',c_act_power:'C'};
const fmt = (n, digits=0) => n.toLocaleString('de-DE',{maximumFractionDigits:digits});
const clock = t => new Date(t*1000).toLocaleTimeString('de-DE',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit',second:'2-digit'});
const localDay = () => new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Berlin'}).format(new Date());
let mode='day', followsToday=true, data=null, liveFlowResult=null, requestId=0, plotScale=null, historyPending=false, historyController=null, loadedHistoryKey=null;
let pageVisible=!document.hidden,statusTimer=null,historyTimer=null,statusPending=false;
$('date').value=localDay();
async function get(url){const r=await fetch(url,{signal:AbortSignal.timeout(8000),cache:'no-store'});if(!r.ok)throw new Error('Abruf fehlgeschlagen');return r.json();}
function updateGridAverage(average){
 const box=$('grid-average'),value=$('grid-average-value');if(!box||!value)return;
 box.classList.remove('average-import','average-export','average-balanced');
 if(!average||!average.complete||!Number.isFinite(average.watts)){value.textContent='Ø noch nicht genügend Messwerte';return;}
 const watts=Math.round(average.watts),direction=watts>0?'Netzbezug':watts<0?'Einspeisung':'ausgeglichen';
 value.textContent='Ø '+fmt(Math.abs(watts))+' W '+direction;
 box.classList.add(watts>0?'average-import':watts<0?'average-export':'average-balanced');
}
async function updateStatus(){
 try{const s=await get('/api/status');$('status').textContent=s.stale?'Keine aktuellen Messwerte':'● Messwerte aktuell';$('status').className='status '+(s.stale?'warn':'live');updateGridAverage(s.average_15m);
  if(s.sample){const v=s.sample,p=v.total_act_power,gridCard=document.querySelector('.grid-card');$('direction').textContent=p>0?'Aktuell · Netzbezug':p<0?'Aktuell · Einspeisung':'Aktuell · Ausgeglichen';$('power').textContent=fmt(Math.abs(p))+' W';$('last').textContent='Letzte Messung: '+new Date(v.ts*1000).toLocaleString('de-DE',{timeZone:'Europe/Berlin'})+(s.stale?' · veraltet':'');
   if(gridCard){gridCard.classList.toggle('grid-import',p>0);gridCard.classList.toggle('grid-export',p<0);gridCard.classList.toggle('grid-balanced',p===0);}
   for(const phase of 'abc'){$('phase-'+phase).textContent=(v[phase+'_act_power']>0?'+':'')+fmt(v[phase+'_act_power'])+' W';$('detail-'+phase).textContent=fmt(v[phase+'_voltage'],1)+' V · '+fmt(v[phase+'_current'],2)+' A';}}
 }catch(e){$('status').textContent='Dashboard-Verbindung unterbrochen';$('status').className='status warn';$('last').textContent='Anzeige möglicherweise veraltet · Verbindung wird erneut geprüft';}
}
async function updateHistory(){const id=++requestId;
 historyController?.abort();
 const controller=new AbortController();historyController=controller;historyPending=true;
 const timeout=setTimeout(()=>controller.abort(),15000);
 if(followsToday)$('date').value=localDay();
 const key=mode+':'+$('date').value;
 if(key!==loadedHistoryKey){data=null;draw();drawFlows(null);$('empty').textContent='Tagesdaten werden geladen …';$('empty').hidden=false;$('balance-day').textContent=$('date').value;$('balance-import').textContent='—';$('balance-export').textContent='—';$('balance-quality').textContent='Tagesdaten werden geladen …';}
 try{const response=await fetch('/api/history?mode='+mode+'&date='+encodeURIComponent($('date').value),{signal:controller.signal,cache:'no-store'});if(!response.ok)throw Error('Abruf fehlgeschlagen');const next=await response.json();if(id!==requestId)return;data=next;loadedHistoryKey=key;if(next.balance_day===localDay()){liveFlowResult=next;drawLiveFlows(liveFlowResult);}drawFlows(next);const b=next.balance;$('balance-day').textContent=next.balance_day;$('balance-import').textContent=b.import_kwh==null?'—':fmt(b.import_kwh,3)+' kWh';$('balance-export').textContent=b.export_kwh==null?'—':fmt(b.export_kwh,3)+' kWh';$('balance-quality').textContent='Bis zum aktuellen Zeitpunkt bzw. Tagesende · Datenabdeckung '+fmt(b.coverage*100,1)+' % · Nicht erfasst: '+fmt(b.missing_seconds/60,1)+' Minuten. Ältere Minutenmittel können Richtungswechsel verdecken.';draw();}
 catch(e){if(id!==requestId||(!pageVisible&&e.name==='AbortError'))return;data=null;drawFlows(null);$('balance-import').textContent='—';$('balance-export').textContent='—';$('balance-quality').textContent='Bilanz nicht erreichbar';draw();$('empty').textContent='Verlauf konnte nicht geladen werden.';$('empty').hidden=false;}
 finally{clearTimeout(timeout);if(id===requestId)historyPending=false;}
}
function selected(){return [...document.querySelectorAll('[data-field]:checked')].map(e=>e.dataset.field);}
function draw(){
 const canvas=$('chart'),rect=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;
 canvas.width=rect.width*dpr;canvas.height=rect.height*dpr;const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
 const W=rect.width,H=rect.height,L=52,R=12,T=18,B=34,fields=selected(),points=data?data.segments.flat():[];
 let limit=1000;for(const p of points)for(const f of fields)limit=Math.max(limit,Math.abs(p[f+'_min']),Math.abs(p[f+'_max']));limit=Math.ceil(limit/500)*500;
 const start=data?data.start:0,end=data?data.end:1,x=t=>L+(t-start)/(end-start)*(W-L-R),y=v=>T+(limit-v)/(2*limit)*(H-T-B);
 plotScale={x,start,end,L,R,W,points};ctx.font='11px system-ui';ctx.lineWidth=1;
 if(data){ctx.fillStyle='rgba(68,150,95,.16)';for(const period of data.charging_periods||[])ctx.fillRect(x(period.start),T,x(period.end)-x(period.start),H-T-B);}
 for(let i=-2;i<=2;i++){const v=limit*i/2;ctx.strokeStyle=i===0?'#a8b9ab':'#e8ede5';ctx.beginPath();ctx.moveTo(L,y(v));ctx.lineTo(W-R,y(v));ctx.stroke();ctx.fillStyle='#6e7e74';ctx.textAlign='right';ctx.fillText(fmt(v/1000,2),L-8,y(v)+4);}
 ctx.textAlign='left';ctx.fillText('kW',L,11);
 if(data)for(let i=0;i<=4;i++){const t=start+(end-start)*i/4;ctx.textAlign=i===0?'left':i===4?'right':'center';ctx.fillText(clock(t).slice(0,5),x(t),H-8);}
 $('empty').hidden=points.length>0&&fields.length>0;$('empty').textContent=fields.length?'Für diesen Zeitraum sind noch keine Messungen gespeichert.':'Bitte mindestens eine Kurve auswählen.';
 if(!data)return;
 for(const segment of data.segments)for(const f of fields){ctx.strokeStyle=colors[f];ctx.fillStyle=colors[f];
  if(data.mode==='day'){ctx.globalAlpha=.12;ctx.beginPath();segment.forEach((p,i)=>i?ctx.lineTo(x(p.ts),y(p[f+'_max'])):ctx.moveTo(x(p.ts),y(p[f+'_max'])));[...segment].reverse().forEach(p=>ctx.lineTo(x(p.ts),y(p[f+'_min'])));ctx.closePath();ctx.fill();ctx.globalAlpha=1;}
  ctx.lineWidth=1.8;ctx.beginPath();segment.forEach((p,i)=>i?ctx.lineTo(x(p.ts),y(p[f])):ctx.moveTo(x(p.ts),y(p[f])));ctx.stroke();
  if(segment.length===1){ctx.beginPath();ctx.arc(x(segment[0].ts),y(segment[0][f]),3,0,Math.PI*2);ctx.fill();}
 }
}
$('chart').addEventListener('pointermove',e=>{if(!plotScale||!data)return;const s=plotScale,px=e.clientX-$('chart').getBoundingClientRect().left,t=s.start+(px-s.L)/(s.W-s.L-s.R)*(s.end-s.start);let best=null;for(const p of s.points)if(!best||Math.abs(p.ts-t)<Math.abs(best.ts-t))best=p;
 if(!best||Math.abs(best.ts-t)>(data.mode==='day'?90:15)){$('tooltip').textContent='Hier liegt keine Messung vor.';return;}
 $('tooltip').textContent=clock(best.ts)+' · '+selected().map(f=>names[f]+': '+fmt(best[f])+' W'+(data.mode==='day'?' (Min '+fmt(best[f+'_min'])+' / Max '+fmt(best[f+'_max'])+' W)':'')).join(' · ');
});
function changeMode(next){mode=next;$('day').setAttribute('aria-pressed',next==='day');$('hour').setAttribute('aria-pressed',next==='hour');$('resolution').textContent=next==='day'?'Minutenmittel mit Minimum und Maximum':'Einzelmessungen im Fünfsekundentakt';$('tooltip').textContent='Kurve berühren oder mit der Maus darüberfahren, um Werte zu sehen.';updateHistory();}
$('day').onclick=()=>changeMode('day');$('hour').onclick=()=>changeMode('hour');
function selectHistoryDay(day){$('date').value=day;followsToday=day===localDay();$('today').setAttribute('aria-pressed',followsToday);changeMode('day');}
function shiftHistoryDay(offset){const d=new Date(($('date').value||localDay())+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+offset);selectHistoryDay(d.toISOString().slice(0,10));}
$('previous-day').onclick=()=>shiftHistoryDay(-1);
$('today').onclick=()=>selectHistoryDay(localDay());
$('next-day').onclick=()=>shiftHistoryDay(1);
$('date').onchange=()=>selectHistoryDay($('date').value);
for(const c of document.querySelectorAll('[data-field]'))c.onchange=draw;
new ResizeObserver(draw).observe($('chart'));
// Schnelle Livewerte und der große Tagesabruf laufen getrennt und pausieren im Hintergrund.
async function refreshStatus(){
 if(!pageVisible||statusPending)return;
 statusPending=true;
 try{await updateStatus();}finally{statusPending=false;if(pageVisible)statusTimer=setTimeout(refreshStatus,5000);}
}
async function refreshHistory(){
 if(!pageVisible)return;
 if(!historyPending&&(mode==='hour'||followsToday||$('date').value===localDay()||!data))await updateHistory();
 if(pageVisible)historyTimer=setTimeout(refreshHistory,30000);
}
function resumeDashboard(){
 clearTimeout(statusTimer);clearTimeout(historyTimer);
 $('status').textContent='Werte werden aktualisiert …';$('status').className='status';
 refreshStatus();historyTimer=setTimeout(refreshHistory,300);
}
document.addEventListener('visibilitychange',()=>{
 pageVisible=!document.hidden;
 clearTimeout(statusTimer);clearTimeout(historyTimer);
 if(!pageVisible){requestId++;historyController?.abort();historyController=null;historyPending=false;return;}
 resumeDashboard();
});
resumeDashboard();

let sunshineThreshold=2000,sunshineActive=false,currentSolarPower=null,currentSolarValid=false;
function updateSunshine(power=currentSolarPower,valid=currentSolarValid){
 const card=document.querySelector('.pv-card');if(!card)return;
 if(!valid||!Number.isFinite(power))sunshineActive=false;
 else if(!sunshineActive&&power>=sunshineThreshold)sunshineActive=true;
 else if(sunshineActive&&power<Math.max(0,sunshineThreshold-200))sunshineActive=false;
 card.classList.toggle('sunshine-active',sunshineActive);card.classList.toggle('sunshine-strong',sunshineActive&&power>=sunshineThreshold+2000);
}
async function updateSunshineSettings(){
 try{const result=await get('/api/preferences'),value=Number(result.values?.pv_sunshine_threshold_w);if(Number.isFinite(value))sunshineThreshold=value;updateSunshine();}catch(_){}
}
window.addEventListener('energypi-settings',updateSunshineSettings);updateSunshineSettings();
async function updateSolar(){
 try{const result=await get('/api/solaredge');
  $('solar-state').textContent=result.message || (result.sample ? (result.stale?'Letzter Wert · veraltet':'Zuletzt abgerufener Wert') : 'Noch nicht eingerichtet oder noch keine Messung');
  currentSolarPower=Number(result.sample?.pv_w);currentSolarValid=Boolean(result.sample&&!result.stale&&!result.message);updateSunshine();
  if(result.sample){$('solar-pv').textContent=fmt(result.sample.pv_w)+' W';$('solar-time').textContent='Abgerufen: '+new Date(result.sample.ts*1000).toLocaleString('de-DE',{timeZone:'Europe/Berlin'});}
  if(result.scheduled_pause)$('solar-state').textContent+=' · Nachtpause';
 }catch(e){currentSolarValid=false;updateSunshine();$('solar-state').textContent='SolarEdge-Anzeige nicht erreichbar · Werte möglicherweise veraltet';}
 setTimeout(updateSolar,30000);
}
updateSolar();

function drawLiveFlows(result){const card=$('live-energy-card');if(!card)return;const f=result?.flows,m=f?.money,valid=Boolean(f?.valid);
 const kwh=value=>Number.isFinite(value)?value.toLocaleString('de-DE',{minimumFractionDigits:1,maximumFractionDigits:1})+' kWh':'—',euro=value=>Number.isFinite(value)?value.toLocaleString('de-DE',{style:'currency',currency:'EUR'}):'—',cents=value=>Number.isFinite(value)?fmt(value,1)+' ct/kWh':'—';
 $('live-energy-title').textContent='Energieanteile · '+(result?.balance_day||'heute');$('live-energy-time').textContent=Number.isFinite(f?.until)?'Bilanz bis '+clock(f.until).slice(0,5)+' Uhr':'Bilanzstand noch nicht verfügbar';
 const sources=[['PV',f?.pv_kwh,'#72c477'],['Netz',f?.import_kwh,'#df8c3c'],['Akku',f?.battery_out_kwh,'#aa85d6']],targets=[['Haus',f?.house_kwh,'#5ea3da'],['Netz',f?.export_kwh,'#397c56'],['Akku',f?.battery_in_kwh,'#aa85d6']];
 function compactBar(id,parts){const node=$(id);node.replaceChildren();const complete=valid&&parts.every(part=>Number.isFinite(part[1])&&part[1]>=0),total=complete?parts.reduce((sum,part)=>sum+part[1],0):0;for(const [,value,color] of parts){const segment=document.createElement('span');segment.style.background=color;segment.style.flexGrow=total>0?value/total:1;node.append(segment);}node.classList.toggle('incomplete',!complete);return complete?total:null;}
 const sourceTotal=compactBar('live-source-bar',sources),targetTotal=compactBar('live-target-bar',targets);$('live-source-total').textContent=kwh(sourceTotal);$('live-target-total').textContent=kwh(targetTotal);$('live-source-values').textContent=sources.map(part=>part[0]+' '+kwh(valid?part[1]:null)).join(' · ');$('live-target-values').textContent=targets.map(part=>part[0]+' '+kwh(valid?part[1]:null)).join(' · ');
 $('live-energy-cost').textContent=m?.complete?euro(m.import_cost_eur):'—';$('live-energy-benefit').textContent=m?.complete?euro(m.benefit_eur):'—';$('live-energy-effective').textContent=m?.complete?cents(m.effective_house_price_ct):'—';$('live-energy-soc').textContent=Number.isFinite(f?.battery_start_soc)&&Number.isFinite(f?.battery_end_soc)?fmt(f.battery_start_soc)+' → '+fmt(f.battery_end_soc)+' %':'—';
 card.classList.toggle('incomplete',!valid);card.title=f?.reason||'Tagesbilanz nicht verfügbar';$('live-energy-status').textContent=valid?(m?.complete?'Vollständige Energie- und Kostenbilanz':'Energiebilanz vollständig · Kosten noch unvollständig'):'Tagesbilanz noch unvollständig';
}

function drawFlows(result){
 const f=result?.flows;
 $('flows-day').textContent=result?.balance_day||'gewählter Tag';
 $('flows-note').textContent=f?.reason||'Tagesdaten nicht verfügbar.';
 $('flows-time').textContent=Number.isFinite(f?.until)?'Bilanzzeitraum bis: '+new Date(f.until*1000).toLocaleString('de-DE',{timeZone:'Europe/Berlin'})+' · SolarEdge kann zeitverzögert sein.':'Bilanzstand noch nicht verfügbar.';
 const energy=v=>v==null?'—':fmt(v,3)+' kWh',soc=v=>v==null?'—':fmt(v,1)+' %';
 $('battery-summary').textContent=f
   ? 'Akku (violett): In den Akku '+energy(f.battery_in_kwh)+' · Aus dem Akku '+energy(f.battery_out_kwh)+
     ' · Erster / letzter erfasster Ladestand im Bilanzzeitraum: '+soc(f.battery_start_soc)+' / '+soc(f.battery_end_soc)+
     (f.battery_coverage<0.95?' · Unvollständige Aufzeichnung.':'')
   : 'Akku: Tagesdaten nicht verfügbar.';
 function ring(id,legendId,parts,caption){
  const node=$(id),legend=$(legendId);legend.replaceChildren();
  const complete=f?.valid&&parts.every(p=>Number.isFinite(p.value)&&p.value>=0);
  const total=complete?parts.reduce((s,p)=>s+p.value,0):0;
  const valid=complete&&total>0;let angle=0;const stops=[];
  for(const p of parts){
   const text=p.label+': '+(p.value==null?'—':fmt(p.value,3)+' kWh')+(valid?' · '+fmt(p.value/total*100,1)+' %':'');
   const item=document.createElement('p');item.textContent=text;item.style.borderLeft='5px solid '+p.color;item.style.paddingLeft='8px';legend.append(item);
   if(valid){const end=angle+p.value/total*360;stops.push(p.color+' '+angle+'deg '+end+'deg');angle=end;}
  }
  node.style.background=valid?'conic-gradient('+stops.join(',')+')':'#e5e9e5';node.querySelector('span').textContent=complete?total.toLocaleString('de-DE',{minimumFractionDigits:1,maximumFractionDigits:1})+' kWh':'Nicht bestimmbar';
  node.title=caption+(complete?' · Summe: '+total.toLocaleString('de-DE',{minimumFractionDigits:1,maximumFractionDigits:1})+' kWh':'')+' · '+parts.map(p=>p.label+': '+(p.value==null?'unbekannt':fmt(p.value,3)+' kWh')).join(' · ');
  node.setAttribute('role','img');node.setAttribute('aria-label',node.title);
 }
 ring('pv-ring','pv-ring-legend',[{label:'PV-Erzeugung',value:f?.pv_kwh??null,color:'#a7d88c'},{label:'Netzbezug',value:f?.import_kwh??null,color:'#e69a42'},{label:'Akku-Abgabe',value:f?.battery_out_kwh??null,color:'#8958ab'}],'Energiequellen');
 ring('supply-ring','supply-ring-legend',[{label:'Hausverbrauch (berechnet)',value:f?.house_kwh??null,color:'#5a99cf'},{label:'Einspeisung ins Netz',value:f?.export_kwh??null,color:'#286344'},{label:'Akku-Ladung',value:f?.battery_in_kwh??null,color:'#8958ab'}],'Energieziele');
 function moneyRing(id,legendId,parts,caption,totalValue){
  const node=$(id),legend=$(legendId);legend.replaceChildren();
  const complete=f?.money?.complete&&parts.every(p=>Number.isFinite(p.value)&&p.value>=0);
  const total=complete?totalValue:null,shareTotal=complete?parts.reduce((sum,p)=>sum+p.value,0):0;
  let angle=0;const stops=[];
  for(const p of parts){
   const amount=Number.isFinite(p.value)?p.value.toLocaleString('de-DE',{style:'currency',currency:'EUR'}):'—';
   const item=document.createElement('p');item.textContent=p.label+': '+amount;item.style.borderLeft='5px solid '+p.color;item.style.paddingLeft='8px';legend.append(item);
   if(complete&&shareTotal>0){const end=angle+p.value/shareTotal*360;stops.push(p.color+' '+angle+'deg '+end+'deg');angle=end;}
  }
  node.style.background=complete&&shareTotal>0?'conic-gradient('+stops.join(',')+')':complete?'#dfe7df':'#e5e9e5';
  node.querySelector('span').textContent=Number.isFinite(total)?total.toLocaleString('de-DE',{style:'currency',currency:'EUR'}):'Nicht bestimmbar';
  node.title=caption+' · '+parts.map(p=>p.label+': '+(Number.isFinite(p.value)?p.value.toLocaleString('de-DE',{style:'currency',currency:'EUR'}):'unbekannt')).join(' · ');
  node.setAttribute('role','img');node.setAttribute('aria-label',node.title);
 }
 const m=f?.money;
 moneyRing('cost-ring','cost-ring-legend',[{label:'Netzbezug',value:m?.import_cost_eur??null,color:'#e69a42'}],'Tatsächliche Netzbezugskosten',m?.import_cost_eur??null);
 moneyRing('benefit-ring','benefit-ring-legend',[{label:'PV-Eigenverbrauch',value:m?.pv_benefit_eur??null,color:'#a7d88c'},{label:'Einspeisevergütung',value:m?.feed_revenue_eur??null,color:'#286344'},{label:'Akku-Abgabe (brutto)',value:m?.battery_value_eur??null,color:'#8958ab'}],'Nutzen der Eigenversorgung',m?.benefit_eur??null);
 const cents=value=>Number.isFinite(value)?value.toLocaleString('de-DE',{minimumFractionDigits:1,maximumFractionDigits:1})+' ct/kWh':'—';
 $('cost-rate').textContent='Ø tatsächlicher Bezugspreis: '+cents(m?.actual_import_price_ct);
 $('effective-rate').textContent='Effektiver Haushaltsstrompreis: '+cents(m?.effective_house_price_ct);
 const euro=value=>value.toLocaleString('de-DE',{style:'currency',currency:'EUR'});
 const selectedDay=result?.balance_day||'';
 const dayLabel=selectedDay===localDay()?'Netzstrom kostete heute':('Am '+(selectedDay?new Date(selectedDay+'T12:00:00Z').toLocaleDateString('de-DE',{timeZone:'Europe/Berlin'}):'gewählten Tag')+' kostete Netzstrom');
 $('money-summary').textContent=m?.complete
   ? dayLabel+' '+euro(m.import_cost_eur)+(Number.isFinite(m.actual_import_price_ct)?' bei einem tatsächlichen Bezugspreis von '+cents(m.actual_import_price_ct):'')+'. Nach '+euro(m.feed_revenue_eur)+' Einspeisevergütung betrug der effektive Strompreis für den gesamten Hausverbrauch '+cents(m.effective_house_price_ct)+'. Durch PV-Eigenverbrauch und Akkuentladung wurden rechnerisch '+euro(m.pv_benefit_eur+m.battery_value_eur)+' Netzbezug vermieden.'
   : 'Der Kostenvergleich ist für diesen Zeitraum nicht vollständig bestimmbar.';
 $('money-note').textContent=m?.complete
   ? m.note+' Preisabdeckung '+fmt(m.price_coverage*100,1)+' % · zeitgewichteter Tibber-Preis '+fmt(m.average_price_ct,2)+' ct/kWh.'
   : 'Geldwerte nicht vollständig bestimmbar: lückenlose Energiebilanz und mindestens 95 % Tibber-Preisabdeckung erforderlich.';
}
