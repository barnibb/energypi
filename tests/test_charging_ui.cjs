const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map(),timers=[];
function node(id){if(!nodes.has(id))nodes.set(id,{textContent:'',className:'',closest(){return node('card')}});return nodes.get(id);}
const payload={stale:false,discharge_limit_w:200,max_gap_seconds:15,marstek_interval_seconds:900,state:{active:false,updated_at:1,active_since:null,pending:null,remaining:null,start_w:1600,stop_w:1000,hold_s:180,reason:null,net_power_w:1590,battery_discharge_w:800,corrected_power_w:2390,protection_w:750,protection_hold_s:600}};
const sandbox={document:{getElementById:node},Intl,Date,AbortSignal,setTimeout:fn=>timers.push(fn),fetch:async()=>({ok:true,json:async()=>payload})};
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../static/charging.js'),'utf8'),sandbox);await flush();
 assert.match(node('charging-detail').textContent,/Netz 1\.590 W/);assert.match(node('charging-detail').textContent,/Erkennungsleistung 2\.390 W/);
 assert.match(node('charging-rule').textContent,/750 W für 10 Min/);assert.match(node('charging-rule').textContent,/Ziel 200 W/);assert.match(node('charging-rule').textContent,/Schreibabstand 15 Min/);
 console.log('OK: aktuelle Leistungen und alle Schutzparameter kompakt angezeigt');
})().catch(error=>{console.error(error);process.exitCode=1;});
