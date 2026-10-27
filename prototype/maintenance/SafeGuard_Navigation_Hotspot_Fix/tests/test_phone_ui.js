'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(require('path').join(__dirname,'../patch/scripts/navigation_phone.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements=new Map();
const get=id=>{if(!elements.has(id))elements.set(id,{textContent:'',className:'',hidden:false,disabled:false,value:'',events:{},addEventListener(name,fn){this.events[name]=fn;}});return elements.get(id);};
const storage=new Map(),requests=[],docEvents={},windowEvents={};
let currentCallback,watchCallback,perf=0,count=0,failRequests=false;
const validSample={coords:{latitude:37.5664,longitude:126.9462,accuracy:13},timestamp:Date.now()};
const context={console,Date,Number,Math,JSON,Promise,Error,AbortController,
 document:{getElementById:get,visibilityState:'visible',addEventListener:(n,f)=>docEvents[n]=f},
 window:{isSecureContext:true,addEventListener:(n,f)=>windowEvents[n]=f},
 navigator:{geolocation:{watchPosition:(ok)=>{watchCallback=ok;return 1;},clearWatch:()=>{},getCurrentPosition:(ok)=>{currentCallback=ok;}}},
 sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
 performance:{now:()=>perf},setInterval:()=>1,clearInterval:()=>{},setTimeout:()=>1,clearTimeout:()=>{},
 fetch:async(path,options)=>{if(failRequests)throw new Error('Load failed');const body=options.body?JSON.parse(options.body):null;requests.push({path,body,headers:options.headers});let result;
 if(path==='/api/pair')result={token:'test-only-token',last_seq:0};
 else if(path==='/api/status')result={last_seq:count,accepted_count:count,location:{valid:count>0,status:'awaiting'}};
 else{count++;result={...body,received_wall_s:Date.now()/1000};}
 return {ok:true,status:200,json:async()=>result};}
};
vm.createContext(context);vm.runInContext(script,context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 get('pairCode').value='12345678';await get('pairButton').events.click();assert.equal(get('pairCard').hidden,true);
 await get('start').events.click();currentCallback(validSample);await tick();await tick();
 let samples=requests.filter(x=>x.path==='/api/location'&&x.body.valid);assert.equal(samples.length,1);assert.equal(samples[0].body.latitude,37.5664);assert.equal(samples[0].headers.Authorization,'Bearer test-only-token');
 perf+=3000;watchCallback({...validSample,timestamp:validSample.timestamp+3000});await tick();await tick();
 samples=requests.filter(x=>x.path==='/api/location'&&x.body.valid);assert.equal(samples.length,2);assert.equal(samples[1].body.seq,2);
 context.document.visibilityState='hidden';docEvents.visibilitychange();await tick();await tick();
 const final=requests.filter(x=>x.path==='/api/location').at(-1);assert.equal(final.body.valid,false);assert.equal(final.body.seq,3);assert.equal(get('stop').disabled,true);
 perf+=3000;watchCallback({...validSample,timestamp:validSample.timestamp+6000});await tick();assert.equal(requests.filter(x=>x.path==='/api/location').length,3);
 assert.equal(get('connection').textContent,'Pi 응답 확인됨');
 context.document.visibilityState='visible';
 failRequests=true;await vm.runInContext('refreshStatus()',context);assert.equal(get('connection').textContent,'Pi 응답 확인 필요');
 failRequests=false;await vm.runInContext('refreshStatus()',context);assert.equal(get('connection').textContent,'Pi 응답 확인됨');
 perf+=11000;vm.runInContext('updateConnection()',context);assert.equal(get('connection').textContent,'Pi 응답 확인 필요');
 console.log('Phone UI pairing / real-browser callback payload / automatic update / hidden-stop PASS (mock browser inputs)');
})().catch(error=>{console.error(error);process.exitCode=1;});
