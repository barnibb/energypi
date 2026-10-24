const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map(),requests=[],labels=[];const handlers={};
const ctx=new Proxy({}, {get:(_,k)=>k==='fillText'?(v)=>labels.push(v):()=>{},set:()=>true});
function node(id){if(!nodes.has(id))nodes.set(id,{textContent:'',open:false,handlers:{},attributes:{},addEventListener(k,v){this.handlers[k]=v;},setAttribute(k,v){this.attributes[k]=v;},showModal(){this.open=true;},close(){this.open=false;this.handlers.close?.();},focus(){},getBoundingClientRect:()=>({width:780,height:350,left:0}),getContext:()=>ctx});return nodes.get(id);}
const days=['2026-10-05','2026-10-06','2026-10-07','2026-10-08','2026-10-09','2026-10-10','2026-10-11'];
const payload={week_number:41,week_year:2026,week_start:days[0],week_end:days[6],points:days.map((day,i)=>({day,today:i===4,complete:i<5&&i!==2,effective_house_price_ct:i===2?null:i-3,import_cost_eur:1.1,feed_revenue_eur:.27,net_cost_eur:.83,house_kwh:10}))};
const sandbox={document:{getElementById:node},Intl,Date,devicePixelRatio:1,AbortController,encodeURIComponent,setTimeout:()=>1,clearTimeout(){},ResizeObserver:class{observe(){}},fetch:async url=>{requests.push(url);return{ok:true,json:async()=>payload};}};
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../static/finance-history.js'),'utf8'),sandbox);
 assert.equal(requests.length,0);node('finance-history-open').onclick();await flush();assert.match(requests[0],/^\/api\/finance\/history\?days=7&week=\d{4}-\d{2}-\d{2}$/);assert.ok(node('finance-history-dialog').open);assert.match(node('finance-week-label').textContent,/KW 41 \/ 2026/);assert.match(node('finance-history-status').textContent,/4 von 7/);assert.ok(labels.includes('Mo'));assert.ok(labels.includes('So'));assert.ok(labels.includes('-5,0'));assert.ok(labels.includes('0,0'));assert.ok(labels.includes('5,0'));
 node('finance-week-previous').onclick();await flush();assert.equal(requests.length,2);
 node('finance-history-chart').handlers.pointermove({clientX:730});assert.match(node('finance-history-tooltip').textContent,/bisher/);assert.match(node('finance-history-tooltip').textContent,/Effektiver Haushaltsstrompreis/);
 node('finance-history-close').onclick();assert.equal(node('finance-history-dialog').open,false);console.log('OK: finance history popup, ten weekdays, partial today, tooltip and close');
})().catch(e=>{console.error(e);process.exitCode=1;});
