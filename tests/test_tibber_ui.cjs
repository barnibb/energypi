// Run with node tests/test_tibber_ui.cjs; no browser or network required.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map(),requests=[],timers=[];
const context=new Proxy({}, {get:(_,key)=>key==='measureText'?()=>({width:40}):()=>{},set:()=>true});
function node(id){if(!nodes.has(id))nodes.set(id,{value:'',textContent:'',hidden:true,addEventListener(){},getBoundingClientRect:()=>({width:800,height:400}),getContext:()=>context});return nodes.get(id);}
const payload={points:[],slots:[],feed_in_ct:9,start:0,end:86400,pending:true,average_ct:null,cheap_threshold_ct:null,battery_pv_threshold_ct:15.59,battery_grid_threshold_ct:25.06,battery_grid_reference_ct:17.05};
let fail=false;
const sandbox={document:{getElementById:node},window:{addEventListener(){}},Intl,Date,devicePixelRatio:1,AbortSignal,
 ResizeObserver:class{constructor(callback){this.callback=callback;}observe(){this.callback();}},
 setTimeout:fn=>timers.push(fn),fetch:async url=>{requests.push(url);if(fail)throw Error('offline');return {ok:true,json:async()=>payload};}};
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../static/tibber.js'),'utf8'),sandbox);
 await flush();assert.equal(requests.length,1);
 node('tibber-date').value='2026-09-15';
 node('tibber-date').onchange();
 assert.equal(requests.length,2,'Date change must fetch immediately, without polling');
 assert.match(requests[1],/date=2026-09-15/);await flush();
 node('tibber-tomorrow').onclick();assert.equal(requests.length,3);await flush();
 fail=true;node('tibber-today').onclick();await flush();
 assert.match(node('tibber-state').textContent,/nicht erreichbar/);
 fail=false;node('tibber-date').onchange();await flush();assert.equal(requests.length,5);
 console.log('OK: initial empty render, immediate date/button requests, fetch error and recovery');
})().catch(error=>{console.error(error);process.exitCode=1;});
