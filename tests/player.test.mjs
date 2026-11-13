import test from 'node:test';
import assert from 'node:assert/strict';
import render, { fittedSize } from '../frontend/player.js';

test('portrait and landscape media fit available width and viewport height',()=>{
 assert.deepEqual(fittedSize(1080,1920,900,600),{width:337.5,height:600});
 assert.deepEqual(fittedSize(1920,1080,800,600),{width:800,height:450});
});
test('native player starts unmuted without extra controls and fits portrait video',()=>{
 const v={muted:true,volume:0,videoWidth:1080,videoHeight:1920,style:{},src:'',getAttribute(){return this.src;}};
 const root={clientWidth:900,querySelector:s=>s==='video'?v:null};
 globalThis.window={innerHeight:790,addEventListener(){},removeEventListener(){}};
 globalThis.ResizeObserver=class{observe(){}disconnect(){}};
 const cleanup=render({parentElement:{querySelector:()=>root},data:{url:'https://example.com/clip.mp4'}});
 assert.equal(v.muted,false);assert.equal(v.volume,1);
 assert.equal(v.style.height,'600px');assert.equal(v.style.width,'337.5px');
 cleanup();
});
