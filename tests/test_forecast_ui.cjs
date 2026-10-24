const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map(),labels=[];
const context=new Proxy({}, {get:(_,key)=>key==='fillText'?(text)=>labels.push(text):()=>{},set:()=>true});
function node(id){if(!nodes.has(id))nodes.set(id,{value:'',textContent:'',hidden:true,addEventListener(name,fn){this[name]=fn;},getBoundingClientRect:()=>({width:800,height:400,left:0}),getContext:()=>context});return nodes.get(id);}
const payload={day:'2026-09-18',start:0,end:86400,view_start:1800,view_end:5400,actual:[],forecast:null,battery:{segments:[[{ts:3600,soc:60},{ts:3630,soc:61}]]}};
const sandbox={document:{getElementById:node},window:{addEventListener(){}},Intl,Date,devicePixelRatio:1,AbortSignal,ResizeObserver:class{constructor(fn){this.fn=fn;}observe(){this.fn();}},setTimeout(){},fetch:async()=>({ok:true,json:async()=>payload})};
(async()=>{vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../static/forecast.js'),'utf8'),sandbox);await new Promise(r=>setImmediate(r));assert.ok(labels.includes('%'));assert.ok(labels.includes('100'));assert.equal(node('forecast-empty').hidden,true);node('forecast-chart').pointermove({clientX:395});assert.match(node('forecast-tooltip').textContent,/Akku.*6[01].*%/);console.log('OK: SOC-only chart, right percent axis, tooltip');})().catch(e=>{console.error(e);process.exitCode=1;});
