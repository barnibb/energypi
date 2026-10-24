'use strict';
(() => {
 const dialog=document.getElementById('phase-dialog');
 const open=document.getElementById('phase-open');
 const close=document.getElementById('phase-close');
 if(!dialog||!open||!close)return;
 open.onclick=()=>dialog.showModal();
 close.onclick=()=>dialog.close();
 dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
})();
