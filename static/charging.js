'use strict';
(() => {
 const label=document.getElementById('charging-label'),detail=document.getElementById('charging-detail'),rule=document.getElementById('charging-rule'),card=label.closest('section');
 const stamp=t=>new Date(t*1000).toLocaleString('de-DE',{timeZone:'Europe/Berlin'});
 const watts=v=>v===null||v===undefined?'—':Math.round(v).toLocaleString('de-DE')+' W';
 async function update(){
  try{const r=await fetch('/api/charging',{signal:AbortSignal.timeout(4000),cache:'no-store'});if(!r.ok)throw Error();const result=await r.json(),s=result.state;
   if(s)rule.textContent='Logik aktuell: Start über '+watts(s.start_w)+' für '+Math.round(s.hold_s/60)+' Min · oder Akku-Abgabe ab '+watts(s.protection_w)+' für '+Math.round(s.protection_hold_s/60)+' Min · Ende unter '+watts(s.stop_w)+' für '+Math.round(s.hold_s/60)+' Min · Ziel '+watts(result.discharge_limit_w)+' · Messlücke max. '+result.max_gap_seconds+' s · Schreibabstand '+Math.round(result.marstek_interval_seconds/60)+' Min. Andere Dauerlasten können ebenfalls auslösen.';
   if(result.stale){label.textContent='Schutzstatus unbekannt';card.className='chargingcard unknown';detail.textContent=s?'Keine aktuellen gültigen Shelly-Messwerte. Zuletzt '+(s.active?(s.reason==='sustained_discharge'?'Dauerlastschutz aktiv':'Autoladen vermutet'):'kein Schutz aktiv')+' · '+stamp(s.updated_at):'Erkennung startet mit dem aktualisierten Sammler.';}
   else{label.textContent=s.active?(s.reason==='sustained_discharge'?'Dauerlastschutz aktiv':'Autoladen vermutet'):'Autoladen nicht erkannt';card.className='chargingcard'+(s.active?' active':'');
    let text=s.active&&s.active_since?'Aktiv seit '+stamp(s.active_since)+'. ':'';
    if(s.pending){const pending={start:'Korrigierte Last: Startprüfung',protection:'Hohe Akku-Abgabe: Dauerlastprüfung',end:'Korrigierte Last niedrig: Endprüfung'};text+=(pending[s.pending]||'Prüfung')+' · noch '+Math.ceil(s.remaining)+' s.';}
    else text+='Aktuell: Netz '+watts(s.net_power_w)+' · Akku-Abgabe '+watts(s.battery_discharge_w)+' · Erkennungsleistung '+watts(s.corrected_power_w)+'.';
    detail.textContent=text;
   }
  }catch(e){label.textContent='Schutzstatus unbekannt';detail.textContent='Anzeige nicht erreichbar; letzter Zustand nicht bestätigt.';rule.textContent='Erkennungslogik nicht verfügbar.';card.className='chargingcard unknown';}
  setTimeout(update,5000);
 }
 update();
})();
