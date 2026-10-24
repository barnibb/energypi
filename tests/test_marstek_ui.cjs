const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map(),timers=[];
function node(id){if(!nodes.has(id))nodes.set(id,{textContent:'',title:'',disabled:false,style:{},attrs:{},classList:{toggle(name,on){this[name]=on;}},setAttribute(k,v){this.attrs[k]=v;},getAttribute(k){return this.attrs[k];}});return nodes.get(id);}
const payload={sample:{soc:59,ac_power_w:797,ts:1000},stale:false,discharge_target_w:200,control:{message:'Morgenkomfort',soc_band:'medium',soc_limit_w:300,soc_stale:false,effective_target_w:800,effective_reason:'morning',morning:{active:true,window_start_hour:5,window_end_hour:10,min_soc:12,night_start_hour:22,night_energy_kwh:1.6,night_target_soc:46.4,pv_remaining_kwh:5}},operating:{label:'Eigenverbrauch',limit_w:800,stale:false},action:{status:'idle',message:''}};
const calls=[];const sandbox={document:{getElementById:node},window:{dispatchEvent(){}},Event:class{},JSON,Intl,Date,AbortSignal,setTimeout:fn=>timers.push(fn),fetch:async(url,options)=>{calls.push([url,options]);return url.includes('discharge-target')?{ok:true,json:async()=>({value_w:350})}:{ok:true,json:async()=>payload};},Number};
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../static/marstek.js'),'utf8'),sandbox);await flush();
 assert.equal(node('marstek-soc').textContent,'59 %');assert.match(node('marstek-soc-ring').style.background,/212\.4deg/);
 assert.equal(node('marstek-soc-ring').attrs['aria-label'],'Akku-Ladestand 59 Prozent');
 assert.match(node('marstek-soc-safety').textContent,/41–60 %.*300 W/);assert.match(node('marstek-effective').textContent,/800 W.*Morgenkomfort/);assert.match(node('marstek-morning').textContent,/1,6 kWh.*46,4 %/);
 assert.equal(node('marstek-target-value').textContent,'200 W');node('marstek-target-slider').value='350';node('marstek-target-slider').oninput();assert.equal(node('marstek-target-save').disabled,false);await node('marstek-target-save').onclick();
 assert.equal(node('marstek-target-value').textContent,'350 W');assert.match(node('marstek-target-status').textContent,/Gespeichert/);assert.match(calls[1][1].body,/350/);
 console.log('OK: Ladestandsring und bewusst bestätigter Entlade-Zielregler dargestellt');
})().catch(error=>{console.error(error);process.exitCode=1;});
