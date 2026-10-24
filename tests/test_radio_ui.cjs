const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map();let resolvePlay,rejectPlay;
function node(id){if(id==='radio-volume')throw Error('Removed slider must not be accessed');if(!nodes.has(id)){const n={value:'0.5',dataset:{},handlers:{},addEventListener(k,v){this.handlers[k]=v;},setAttribute(k,v){this[k]=v;},removeAttribute(k){delete this[k];},pause(){this.paused=true;},load(){},play(){return new Promise((resolve,reject)=>{resolvePlay=resolve;rejectPlay=reject;});}};if(id==='radio-toggle')n.dataset={src:'https://example.test/info.mp3',label:'NDR Info'};if(id==='radio-ndr2')n.dataset={src:'https://example.test/ndr2.mp3',label:'NDR 2'};nodes.set(id,n);}return nodes.get(id);}
vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../static/radio.js'),'utf8'),{document:{getElementById:node},window:{addEventListener(){}}});
(async()=>{
 const a=node('radio-audio'),b=node('radio-toggle'),n=node('radio-ndr2');assert.equal(a.src,undefined);
 const start=b.handlers.click();assert.equal(a.src,b.dataset.src);
 await b.handlers.click();assert.equal(a.src,undefined);resolvePlay();await start;assert.equal(b.textContent,'▶ NDR Info');
 const success=b.handlers.click();resolvePlay();await success;assert.equal(b.textContent,'■ NDR Info');
 const switchStation=n.handlers.click();assert.equal(a.src,n.dataset.src);resolvePlay();await switchStation;assert.equal(n.textContent,'■ NDR 2');assert.equal(b['aria-pressed'],'false');
 a.handlers.error();assert.equal(a.src,undefined);assert.match(node('radio-status').textContent,/unterbrochen/);
 const failure=n.handlers.click();rejectPlay(Error());await failure;assert.equal(n['aria-pressed'],'false');
 console.log('OK: no autoplay, exclusive NDR Info/NDR 2 playback, races and failures');
})().catch(e=>{console.error(e);process.exitCode=1;});
