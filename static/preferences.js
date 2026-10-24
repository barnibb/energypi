(() => {
 const dialog=document.getElementById('preferences-dialog'),form=document.getElementById('preferences-form'),message=document.getElementById('preferences-message');
 const defaults={block_above_w:2000,release_below_w:1000,hold_seconds:180,max_gap_seconds:15,sustained_discharge_w:750,sustained_discharge_seconds:600,marstek_interval_seconds:900,feed_in_ct:9,base_load_w:160,ev_current_a:5,fan_minutes:20,ev_discharge_limit_w:200,pv_sunshine_threshold_w:2000,frost_temperature_c:0,forecast_start_hour:5,forecast_end_hour:23,morning_enabled:1,morning_start_hour:5,morning_end_hour:10,morning_release_w:800,morning_min_soc:12,night_start_hour:22,night_energy_kwh:1.6,battery_loss_percent:10,forecast_reserve_margin_kwh:1,soc_high_threshold:60,soc_medium_threshold:40,soc_low_threshold:20,soc_high_w:800,soc_medium_w:300,soc_low_w:100,soc_reserve_w:100,plan_enabled:1,plan_grid_charge:1,plan_capacity_kwh:5.12,plan_min_soc:20,plan_max_soc:95,plan_end_soc:20,plan_efficiency:85,plan_wear_ct:2,plan_margin_ct:3,plan_pv_discount:20,plan_house_w:160,plan_charge_w:2500,plan_discharge_w:800,plan_hours:24};
 function preview(){const base=Number(form.elements.base_load_w.value),amps=Number(form.elements.ev_current_a.value);document.getElementById('pv-settings-preview').textContent='PV-Schwelle: '+((base+3*230*amps)/1000).toLocaleString('de-DE',{maximumFractionDigits:2})+' kW (Grundlast + 3 × 230 V × Ladestrom).';}
 form.addEventListener('input',preview);
 let loaded={...defaults};
 function fill(values){loaded={...defaults,...values};for(const [k,v] of Object.entries(loaded)){const field=form.elements[k];if(field)field.value=k==='marstek_interval_seconds'?v/60:v;}preview();}
 document.getElementById('preferences-open').onclick=async()=>{
  message.textContent='Wird geladen …';dialog.showModal();form.querySelector('[type=submit]').disabled=true;
  try{const r=await fetch('/api/preferences',{signal:AbortSignal.timeout(5000)});if(!r.ok)throw Error();fill((await r.json()).values);message.textContent='';form.querySelector('[type=submit]').disabled=false;}
  catch{message.textContent='Einstellungen konnten nicht geladen werden.';}
 };
 document.getElementById('preferences-close').onclick=()=>dialog.close();
 document.getElementById('preferences-defaults').onclick=()=>{fill(defaults);message.textContent='Standardwerte eingetragen. Zum Übernehmen speichern.';};
 form.onsubmit=async event=>{
  event.preventDefault();const values={...loaded};for(const k of Object.keys(defaults)){const field=form.elements[k];if(field)values[k]=Number(field.value)*(k==='marstek_interval_seconds'?60:1);}
  const button=form.querySelector('[type=submit]');button.disabled=true;
  try{const r=await fetch('/api/preferences',{method:'POST',headers:{'Content-Type':'application/json','X-EnergyPi':'settings'},body:JSON.stringify(values),signal:AbortSignal.timeout(5000)});const result=await r.json();if(!r.ok)throw Error(result.error||'Speichern fehlgeschlagen');fill(result.values);message.textContent='Gespeichert. Erkennung übernimmt die Werte beim nächsten Messzyklus.';window.dispatchEvent(new Event('energypi-settings'));}
  catch(error){message.textContent=error.message;}finally{button.disabled=false;}
 };
})();
