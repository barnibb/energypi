'use strict';
(() => {
 const audio=document.getElementById('radio-audio'),buttons=[document.getElementById('radio-toggle'),document.getElementById('radio-ndr2')],status=document.getElementById('radio-status');
 let active=null,request=0;
 function resetButtons(){for(const button of buttons){button.textContent='▶ '+button.dataset.label;button.setAttribute('aria-pressed','false');}}
 function stop(message=''){
  active=null;request++;audio.pause();audio.removeAttribute('src');audio.load();
  resetButtons();status.textContent=message;
 }
 audio.volume=0.5;
 for(const button of buttons)button.addEventListener('click',async()=>{
  if(active===button){stop();return;}
  if(active)stop();
  active=button;const id=++request;resetButtons();button.textContent='■ '+button.dataset.label+' · verbindet';button.setAttribute('aria-pressed','true');status.textContent='Livestream wird verbunden …';
  audio.src=button.dataset.src;
  try{await audio.play();if(id!==request)return;button.textContent='■ '+button.dataset.label;status.textContent='Live · '+button.dataset.label+' auf diesem Gerät';}
  catch(e){if(id===request)stop('Stream nicht verfügbar · erneut starten oder NDR öffnen');}
 });
 audio.addEventListener('error',()=>{if(active)stop('Stream unterbrochen · erneut starten oder NDR öffnen');});
 audio.addEventListener('waiting',()=>{if(active)status.textContent='Stream puffert …';});
 audio.addEventListener('playing',()=>{if(active)status.textContent='Live · Wiedergabe auf diesem Gerät';});
 audio.addEventListener('ended',()=>stop('Stream beendet'));
 window.addEventListener('pagehide',()=>stop());
})();
