'use strict';
(()=>{
 const el=id=>document.getElementById(id),fmt=(v,d=0)=>v.toLocaleString('de-DE',{maximumFractionDigits:d}),watts=v=>Math.abs(v)>=1000?fmt(Math.abs(v)/1000,1)+' kW':fmt(Math.abs(v))+' W';
 let last=null,failures=0;
 async function json(url){const response=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(9000)});if(!response.ok)throw Error(url);return response.json();}
 function direction(id,from,to,color,amount,stale=false){
  const path=el('flow-'+id),tag=el('tag-'+id),text=el('tag-'+id+'-text'),active=Number.isFinite(amount)&&Math.abs(amount)>=20;
  path.classList.toggle('off',!active);path.classList.toggle('stale',stale);tag.classList.toggle('off',!active);
  text.textContent=active?from+' → '+to:from+' · '+to;
  path.style.animationDuration=active?Math.max(.5,2.2-Math.min(Math.abs(amount),5000)/3000).toFixed(2)+'s':'';
  if(color==='green'){path.classList.add('export');}else path.classList.remove('export');
 }
 function reverse(path,yes,a,b){path.setAttribute('d',yes?b:a);}
 function render(data){
  const sample=data.status.sample,solar=data.solar.sample,battery=data.marstek.sample,charge=data.charging.state;
  const net=Number(sample?.total_act_power),pv=Number(solar?.pv_w),bp=Number(battery?.ac_power_w);
  const imported=Number.isFinite(net)?Math.max(0,net):0,exported=Number.isFinite(net)?Math.max(0,-net):0,discharge=Number.isFinite(bp)?Math.max(0,bp):0,batteryCharge=Number.isFinite(bp)?Math.max(0,-bp):0;
  const house=Number.isFinite(net)&&Number.isFinite(pv)&&Number.isFinite(bp)?Math.max(0,pv+imported+discharge-exported-batteryCharge):null;
  const evActive=Boolean(charge?.active),evEstimate=evActive&&Number.isFinite(charge?.corrected_power_w)?Math.max(0,charge.corrected_power_w):0;
  el('grid-power').textContent=Number.isFinite(net)?watts(net):'—';el('grid-mode').textContent=!Number.isFinite(net)?'Keine aktuellen Daten':net>20?'Netzbezug':net< -20?'Einspeisung':'Ausgeglichen';
  el('pv-power').textContent=Number.isFinite(pv)?watts(pv):'—';el('house-power').textContent=Number.isFinite(house)?'≈ '+watts(house):'—';
  el('battery-power').textContent=Number.isFinite(bp)?watts(bp):'—';el('battery-mode').textContent=!Number.isFinite(bp)?'Keine aktuellen Daten':bp>20?'Entlädt ins Haus':bp< -20?'Wird geladen':'Bereit';
  const soc=Number(battery?.soc),level=Math.max(0,Math.min(100,soc||0));el('battery-soc').textContent=Number.isFinite(soc)?fmt(soc)+' %':'—';el('battery-fill').setAttribute('y',String(143-level*1.31));el('battery-fill').setAttribute('height',String(level*1.31));
  el('car-power').textContent=evActive?'≈ '+watts(evEstimate):'Bereit';el('car-mode').textContent=evActive?(charge.reason==='sustained_discharge'?'Dauerlast erkannt':'Autoladen erkannt'):'Autoladen nicht erkannt';
  const gridPath=el('flow-grid'),batteryPath=el('flow-battery');
  reverse(gridPath,net<0,'M928 340 L622 340','M622 340 L928 340');
  reverse(batteryPath,bp<0,'M600 535 L600 362','M600 362 L600 535');
  direction('pv','PV','Verteilung','green',pv,data.solar.stale);direction('house','Verteilung','Haus','blue',house,data.status.stale);direction('grid',net<0?'Verteilung':'Netz',net<0?'Netz':'Verteilung',net<0?'green':'blue',net,data.status.stale);direction('battery',bp<0?'Verteilung':'Akku',bp<0?'Akku':'Verteilung','purple',bp,data.marstek.stale);direction('car','Verteilung','Auto','orange',evEstimate,data.charging.stale);
  const times=[sample?.ts,solar?.ts,battery?.ts].filter(Number.isFinite),latest=times.length?Math.max(...times):null;
  el('flow-time').textContent=latest?'Datenstand: '+new Date(latest*1000).toLocaleString('de-DE',{timeZone:'Europe/Berlin'}):'Noch keine Messung';
  el('flow-status').textContent=(data.status.stale||data.marstek.stale)?'Einzelne Werte veraltet':'● Messwerte aktuell';document.body.classList.remove('connection-error');
 }
 async function refresh(){
  try{const [status,solar,marstek,charging]=await Promise.all([json('/api/status'),json('/api/solaredge'),json('/api/marstek'),json('/api/charging')]);last={status,solar,marstek,charging};failures=0;render(last);}
  catch(_){failures++;if(last){render(last);el('flow-status').textContent='Aktualisierung verzögert';}else el('flow-status').textContent=failures<3?'Verbindung wird erneut geprüft …':'Vorschau nicht erreichbar';document.body.classList.add('connection-error');}
  finally{setTimeout(refresh,failures?2500:5000);}
 }
 refresh();
})();
