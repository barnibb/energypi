const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map(),requests=[],labels=[];
const ctx=new Proxy({}, {get:(_,k)=>k==='fillText'?(v)=>labels.push(v):()=>{},set:()=>true});
function node(id){if(!nodes.has(id))nodes.set(id,{value:'',textContent:'',open:false,handlers:{},addEventListener(k,v){this.handlers[k]=v;},showModal(){this.open=true;},close(){this.open=false;this.handlers.close?.();},focus(){},getBoundingClientRect:()=>({width:700,height:300,left:0}),getContext:()=>ctx});return nodes.get(id);}
let empty=false;
const sandbox={document:{getElementById:node},Intl,Date,devicePixelRatio:1,AbortController,encodeURIComponent,setTimeout:()=>1,clearTimeout(){},setInterval(){},ResizeObserver:class{observe(){}},fetch:async url=>{requests.push(url);return{ok:true,json:async()=>({day:'2026-09-18',start:0,end:86400,count:empty?0:2,minimum:empty?null:10,maximum:empty?null:12,segments:empty?[]:[[{ts:0,temperature_c:10},{ts:900,temperature_c:12}]]})};}};
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../static/weather-history.js'),'utf8'),sandbox);
 assert.equal(requests.length,0);node('weather-open').onclick();await flush();assert.equal(requests.length,1);assert.ok(node('weather-dialog').open);assert.ok(labels.includes('°C'));assert.match(node('weather-extremes').textContent,/10,0/);
 node('weather-yesterday').onclick();await flush();assert.equal(requests.length,2);
 empty=true;node('weather-date').value='2026-09-01';node('weather-date').onchange();await flush();assert.match(requests[2],/2026-09-01/);assert.match(node('weather-history-status').textContent,/Keine Temperaturdaten/);
 node('weather-close').onclick();assert.equal(node('weather-dialog').open,false);console.log('OK: open, dates, axis, extremes, empty day, close');
})().catch(e=>{console.error(e);process.exitCode=1;});
