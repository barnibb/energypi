(() => {
  const value = document.getElementById('marstek-soc');
  const ring = document.getElementById('marstek-soc-ring');
  const power = document.getElementById('marstek-power');
  const state = document.getElementById('marstek-state');
  const stamp = document.getElementById('marstek-time');
  const button=document.getElementById('marstek-self'), feedback=document.getElementById('marstek-action');
  const targetSlider=document.getElementById('marstek-target-slider'),targetValue=document.getElementById('marstek-target-value'),targetSave=document.getElementById('marstek-target-save'),targetStatus=document.getElementById('marstek-target-status');
  let submitting=false,targetSaving=false,targetDirty=false,savedTarget=null;
  function showSoc(soc,stale=false){
    const valid=Number.isFinite(soc)&&soc>=0&&soc<=100;
    value.textContent=valid?soc.toLocaleString('de-DE')+' %':'—';
    const color=!valid?'#e5e9e5':soc<=20?'#c46a4b':soc<=50?'#d6a13b':'#5f9b68';
    ring.style.background=valid?`conic-gradient(${color} ${soc*3.6}deg,#e5e9e5 0)`:'#e5e9e5';
    ring.classList.toggle('stale',stale);
    ring.setAttribute('aria-label',valid?'Akku-Ladestand '+soc.toLocaleString('de-DE')+' Prozent'+(stale?', Messwert veraltet':''):'Akku-Ladestand nicht verfügbar');
    ring.title=ring.getAttribute('aria-label');
  }
  function showTarget(value,fromServer=false){
    if(fromServer&&!targetDirty&&!targetSaving){savedTarget=value;targetSlider.value=value;}
    const draft=Number(targetSlider.value);targetValue.textContent=draft.toLocaleString('de-DE')+' W';
    targetSave.disabled=targetSaving||!targetDirty;
  }
  targetSlider.oninput=()=>{targetDirty=savedTarget===null||Number(targetSlider.value)!==savedTarget;showTarget(Number(targetSlider.value));targetStatus.textContent=targetDirty?'Noch nicht übernommen.':'';};
  targetSave.onclick=async()=>{
    const requested=Number(targetSlider.value);targetSaving=true;targetSave.disabled=true;targetSlider.disabled=true;targetStatus.textContent='Wird gespeichert …';
    try{
      const response=await fetch('/api/marstek/discharge-target',{method:'POST',headers:{'Content-Type':'application/json','X-EnergyPi':'settings'},body:JSON.stringify({value_w:requested}),signal:AbortSignal.timeout(5000)});
      const result=await response.json();if(!response.ok)throw Error(result.error||'Speichern fehlgeschlagen');
      savedTarget=result.value_w;targetSlider.value=savedTarget;targetDirty=false;targetStatus.textContent='Gespeichert. Wird bei aktivem Schutz unter Beachtung des Schreibabstands übernommen.';window.dispatchEvent(new Event('energypi-settings'));
    }catch(error){targetStatus.textContent=error.message||'Zielwert konnte nicht gespeichert werden.';}
    finally{targetSaving=false;targetSlider.disabled=false;showTarget(Number(targetSlider.value));}
  };
  button.onclick=async()=>{
    submitting=true;button.disabled=true;feedback.textContent='Wird angefordert …';
    try{
      const response=await fetch('/api/marstek/self-consumption',{method:'POST',headers:{'Content-Type':'application/json','X-EnergyPi':'settings'},body:'{}',signal:AbortSignal.timeout(8000)});
      if(!response.ok)throw Error();
      feedback.textContent=(await response.json()).action.message;
    }catch(_){feedback.textContent='Anforderung nicht bestätigt; Status wird erneut geprüft.';}
    finally{submitting=false;}
  };
  async function refresh() {
    try {
      const response = await fetch('/api/marstek', {signal: AbortSignal.timeout(8000)});
      if (!response.ok) throw new Error('HTTP');
      const data = await response.json(), sample = data.sample;
      if(Number.isFinite(data.discharge_target_w))showTarget(data.discharge_target_w,true);
      document.getElementById('marstek-control').textContent = data.control?.message || 'Begrenzung noch nicht geprüft';
      const operating=data.operating;
      document.getElementById('marstek-mode').textContent=(operating?.stale?'Zuletzt: ':'')+(operating?.label||'Betriebsart unbekannt');
      document.getElementById('marstek-limit').textContent='Entladegrenze: '+(operating?.limit_w==null?'—':operating.limit_w.toLocaleString('de-DE')+' W')+(operating?.stale?' · veraltet':'');
      const control=data.control||{},reason={soc_safety:'SOC-Sicherheit',sustained_limit:'Dauerlastschutz',ev_limit:'Autoladen',night_reserve:'Nachtreserve',night_supply:'Nachtversorgung',morning:'Morgenkomfort',normal:'Normalbetrieb'}[control.effective_reason]||'noch nicht bestimmt';
      document.getElementById('marstek-effective').textContent='Wirksames Ziel: '+(Number.isFinite(control.effective_target_w)?control.effective_target_w.toLocaleString('de-DE')+' W · '+reason:'—');
      const bands={high:'über 60 %',medium:'41–60 %',low:'21–40 %',reserve:'bis 20 %'};
      document.getElementById('marstek-soc-safety').textContent=control.soc_band?'SOC-Sicherheit: '+(control.soc_label||bands[control.soc_band]||control.soc_band)+' → max. '+control.soc_limit_w.toLocaleString('de-DE')+' W'+(control.soc_stale?' · SOC veraltet, keine Erhöhung':''):'SOC-Sicherheit: wartet auf aktuellen Ladestand';
      const morning=control.morning;document.getElementById('marstek-morning').textContent=morning?(morning.active?'Morgenfreigabe aktiv · ':'Morgenfreigabe '+String(morning.window_start_hour).padStart(2,'0')+':00–'+String(morning.window_end_hour).padStart(2,'0')+':00 Uhr · ')+'Nachtreserve '+morning.night_energy_kwh.toLocaleString('de-DE',{maximumFractionDigits:2})+' kWh → Ziel '+morning.night_target_soc.toLocaleString('de-DE',{maximumFractionDigits:1})+' % um '+String(morning.night_start_hour).padStart(2,'0')+':00 · Restprognose '+(morning.pv_remaining_kwh==null?'—':morning.pv_remaining_kwh.toLocaleString('de-DE',{maximumFractionDigits:1})+' kWh'):'Energieregel: wartet auf Status';
      const pending=['pending','processing'].includes(data.action?.status);
      button.disabled=submitting||data.stale||pending;
      if(!submitting)feedback.textContent=data.action?.message||'';
      showSoc(sample?.soc,data.stale);
      if (!sample) {
        power.textContent = '—';
        state.textContent = 'Noch keine Akku-Messung';
        stamp.textContent = 'Marstek-Sammler noch nicht gestartet oder nicht erreichbar.';
        return;
      }
      const watts = sample.ac_power_w;
      power.textContent = `${Math.abs(watts).toLocaleString('de-DE')} W`;
      state.textContent = (data.stale ? 'Veraltet · zuletzt: ' : '') +
        (watts > 0 ? 'Entlädt ins Haus' : watts < 0 ? 'Lädt den Akku' : 'Keine AC-Leistung');
      stamp.textContent = `Messung: ${new Date(sample.ts*1000).toLocaleString('de-DE')}` +
        (data.stale ? ' · Verbindung prüfen' : ' · Messwerte aktuell');
    } catch (_) {
      button.disabled=true;
      document.getElementById('marstek-mode').textContent='Betriebsart nicht erreichbar';
      document.getElementById('marstek-limit').textContent='Entladegrenze: —';
      document.getElementById('marstek-effective').textContent='Wirksames Ziel: —';
      document.getElementById('marstek-soc-safety').textContent='SOC-Sicherheit: Status nicht erreichbar';
      document.getElementById('marstek-morning').textContent='Morgenkomfort: Status nicht erreichbar';
      showSoc(null,true); power.textContent = '—';
      document.getElementById('marstek-control').textContent = 'Begrenzungsstatus unbekannt';
      state.textContent = 'Akku-Status nicht erreichbar';
      stamp.textContent = 'Keine aktuellen Daten verfügbar.';
    } finally { setTimeout(refresh, 10000); }
  }
  refresh();
})();
