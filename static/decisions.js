(() => {
 const list=document.getElementById('decisions-list'),status=document.getElementById('decisions-status');
 async function refresh(){
  try{
   const response=await fetch('/api/marstek/decisions',{signal:AbortSignal.timeout(8000)});
   if(!response.ok)throw Error();
   const data=await response.json();list.replaceChildren();
   for(const entry of data.entries){
    const item=document.createElement('li'),stamp=document.createElement('time'),text=document.createElement('span');
    const date=new Date(entry.ts*1000);stamp.dateTime=date.toISOString();
    stamp.textContent=date.toLocaleString('de-DE',{timeZone:'Europe/Berlin',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'});
    text.textContent=entry.text;if(entry.kind==='error')item.className='decision-error';
    item.append(stamp,text);list.append(item);
   }
   status.textContent=data.entries.length?'':'Noch keine Entscheidungen protokolliert.';
  }catch(_){status.textContent='Protokoll konnte nicht aktualisiert werden; angezeigte Einträge möglicherweise veraltet.';}
  finally{setTimeout(refresh,15000);}
 }
 refresh();
})();
