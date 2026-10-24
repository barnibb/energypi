(() => {
 const el=id=>document.getElementById(id),dialog=el('fan-dialog');let data=null,busy=false;
 function render(){
  let label='Nicht erreichbar';
  if(data){
   if(data.observed===true)label=data.remaining_seconds>0?'noch '+Math.ceil(data.remaining_seconds/60)+' Min.':data.desired===0?'Abschaltung ausstehend':'An · ohne EnergyPi-Timer';
   else if(data.observed===false)label=data.desired===1?'Start angefordert':'Aus';
   if(!data.available)label='Nicht bereit';
  }
  el('fan-open').textContent='Lüfter Bad · '+label;
  el('fan-state').textContent=label+(data?.error?' · '+data.error:'');
  el('fan-start').textContent=(data?.desired===1?'Neu starten · ':'Einschalten · ')+(data?.duration_minutes??20)+' Min.';
  el('fan-start').disabled=busy||!data?.available;el('fan-stop').disabled=busy;
 }
 async function refresh(){try{const r=await fetch('/api/fan',{signal:AbortSignal.timeout(5000),cache:'no-store'});if(!r.ok)throw Error();data=await r.json();}catch{data=null;}render();}
 async function command(action){busy=true;render();try{const r=await fetch('/api/fan',{method:'POST',headers:{'Content-Type':'application/json','X-EnergyPi':'settings'},body:JSON.stringify({action}),signal:AbortSignal.timeout(5000)});const result=await r.json();if(!r.ok)throw Error(result.error||'Anforderung fehlgeschlagen');data=result;busy=false;render();}catch(error){busy=false;render();el('fan-state').textContent=error.message;}}
 el('fan-open').onclick=()=>{dialog.showModal();refresh();};el('fan-close').onclick=()=>dialog.close();
 el('fan-start').onclick=()=>command('start');el('fan-stop').onclick=()=>command('stop');
 window.addEventListener('energypi-settings',refresh);
 async function poll(){await refresh();setTimeout(poll,5000);}poll();
})();
