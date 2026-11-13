import test from 'node:test';
import assert from 'node:assert/strict';
import { playWithSound, alarmActive, fittedSize } from '../frontend/player.js';
test('explicit sound play clears native mute and zero volume before playing', async()=>{
 const v={muted:true,volume:0,play:async function(){assert.equal(this.muted,false);assert.equal(this.volume,1);}};
 await playWithSound(v);
});
test('browser alarm follows half-open intervals',()=>{
 const a=[{start_seconds:5.005,end_seconds:18.418}];
 assert.equal(alarmActive(5,a),false);assert.equal(alarmActive(7,a),true);assert.equal(alarmActive(18.418,a),false);
});
test('portrait and landscape media fit available width and viewport height',()=>{
 assert.deepEqual(fittedSize(1080,1920,900,600),{width:337.5,height:600});
 assert.deepEqual(fittedSize(1920,1080,800,600),{width:800,height:450});
});

import render from '../frontend/player.js';
function harness() {
 const events=new Map(); const levels=[];
 const video={muted:false,volume:0,paused:true,ended:false,seeking:false,currentTime:0,videoWidth:1080,videoHeight:1920,style:{},src:'',
  getAttribute(){return this.src;},async play(){this.paused=false;},pause(){this.paused=true;},
  addEventListener(e,f){if(!events.has(e))events.set(e,new Set());events.get(e).add(f);},
  removeEventListener(e,f){events.get(e)?.delete(f);},emit(e){for(const f of events.get(e)||[])f();}};
 const controls={'video':video,'[data-play]':{},'[data-test]':{},'select':{value:'video'},'[data-status]':{textContent:''}};
 class FakeAudio {
  currentTime=0;destination={};closed=false;
  createGain(){return {gain:{value:0,setTargetAtTime(v){levels.push(v);},setValueAtTime(v){levels.push(v);}},connect(){}};}
  createOscillator(){return {frequency:{value:0},connect(){},start(){}};}
  async resume(){} async close(){this.closed=true;}
 }
 globalThis.window={AudioContext:FakeAudio,innerHeight:790,addEventListener(){},removeEventListener(){}};
 globalThis.ResizeObserver=class{observe(){} disconnect(){}};
 const root={clientWidth:900,querySelector:s=>controls[s]};
 const cleanup=render({parentElement:{querySelector:()=>root},data:{url:'https://example.com/clip.mp4',alarms:[{start_seconds:5,end_seconds:10}]}});
 return {controls,video,levels,cleanup};
}
test('renderer enables browser sound only in alarm interval and stops on pause or buffering',async()=>{
 const h=harness();try{
  h.controls.select.value='browser';h.controls.select.onchange();await h.controls['[data-play]'].onclick();
  h.video.currentTime=7;h.video.emit('timeupdate');assert.equal(h.video.muted,true);assert.equal(h.levels.at(-1),.25);
  h.video.emit('waiting');assert.equal(h.levels.at(-1),0);
  h.video.emit('playing');assert.equal(h.levels.at(-1),.25);
  h.video.pause();h.video.emit('pause');assert.equal(h.levels.at(-1),0);
 }finally{h.cleanup();}
});
test('rerender cleanup cannot leave muted video playing without browser alarm',async()=>{
 const h=harness();h.controls.select.value='browser';h.controls.select.onchange();await h.controls['[data-play]'].onclick();
 h.cleanup();assert.equal(h.video.paused,true);
});
