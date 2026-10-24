(() => {
 const el=id=>document.getElementById(id),nf=new Intl.NumberFormat('de-DE',{maximumFractionDigits:2});
 const stamp=t=>new Date(t*1000).toLocaleString('de-DE',{timeZone:'Europe/Berlin',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
 const clock=t=>new Date(t*1000).toLocaleTimeString('de-DE',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit'});
 async function refreshPlan(){
  const r=await fetch('/api/observation-plan',{signal:AbortSignal.timeout(8000)});if(!r.ok)throw Error();const p=await r.json();
  el('observation-status').textContent=p.message+(p.stale?' · Plan veraltet':'')+(p.settings_changed?' · Einstellungen geändert; nächster Plan steht aus':'');
  el('observation-summary').textContent=p.status==='ready'?`Planstand ${stamp(p.created)} · ${stamp(p.start)} bis ${stamp(p.end)} · Modellkosten inkl. Verschleiß abzüglich Einspeisung: ${nf.format(p.cost_eur)} € · Start ${nf.format(p.start_soc)} % → Ende ${nf.format(p.end_soc)} %`:'';
  el('observation-notes').replaceChildren();for(const note of p.warnings||[]){const li=document.createElement('li');li.textContent=note;el('observation-notes').append(li);}
  el('observation-rows').replaceChildren();for(const slot of p.slots||[]){const tr=document.createElement('tr');for(const text of [stamp(slot.start)+'–'+clock(slot.end),slot.action,nf.format(slot.price_ct),nf.format(slot.soc)+' %']){const td=document.createElement('td');td.textContent=text;tr.append(td);}el('observation-rows').append(tr);}
 }
 async function poll(){try{await refreshPlan();}catch(_){el('observation-status').textContent='Beobachtungsplan nicht erreichbar · vorhandene Anzeige möglicherweise veraltet';}setTimeout(poll,30000);}poll();
 window.addEventListener('energypi-settings',refreshPlan);
})();
