'use strict';
(() => {
 const el=id=>document.getElementById(id);
 const stamp=t=>new Date(t*1000).toLocaleString('de-DE',{timeZone:'Europe/Berlin',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
 async function refresh(){
  try{
   const r=await fetch('/api/weather',{cache:'no-store',signal:AbortSignal.timeout(8000)});
   if(!r.ok)throw Error();const p=await r.json();
   if(el('weather-site-name'))el('weather-site-name').textContent=p.site_name||'Anlagenstandort';
   el('weather-value').textContent=p.sample?new Intl.NumberFormat('de-DE',{minimumFractionDigits:1,maximumFractionDigits:1}).format(p.sample.temperature_c)+' °C':'—';
   const sevilla=p.sevilla||{};
   el('weather-sevilla-value').textContent=sevilla.sample?new Intl.NumberFormat('de-DE',{minimumFractionDigits:1,maximumFractionDigits:1}).format(sevilla.sample.temperature_c)+' °C':'—';
   el('weather-time').textContent=p.sample?'Wetterstand: '+stamp(p.sample.valid_at)+(p.stale?' · veraltet':''):'Noch keine Wetterdaten';
   el('weather-state').textContent=p.error?'Abruf fehlgeschlagen · letzter Wert':p.stale&&p.sample?'Letzter verfügbarer Modellwert':'Wettermodell · kein Sensor am Haus';
   el('weather-value').classList.toggle('weather-stale',p.stale);
   el('weather-sevilla-value').classList.toggle('weather-stale',Boolean(sevilla.stale));
   el('weather-value').title=p.sample?'Abgerufen: '+stamp(p.sample.fetched_at):'';
   el('weather-sevilla-value').title=sevilla.sample?'Sevilla · abgerufen: '+stamp(sevilla.sample.fetched_at):'';
   window.dispatchEvent(new CustomEvent('energypi-weather',{detail:{temperature:p.sample?.temperature_c,valid:Boolean(p.sample&&!p.stale)}}));
  }catch(e){el('weather-value').textContent=el('weather-sevilla-value').textContent='—';el('weather-time').textContent='Wetterdaten nicht erreichbar';el('weather-state').textContent='Erneuter Versuch folgt';window.dispatchEvent(new CustomEvent('energypi-weather',{detail:{temperature:null,valid:false}}));}
  setTimeout(refresh,60000);
 }refresh();
})();
