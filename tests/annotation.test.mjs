import test from 'node:test';
import assert from 'node:assert/strict';
import { eventPoint, toOriginal } from '../frontend/annotation.js';

test('responsive canvas click uses its actual displayed rectangle', () => {
  assert.deepEqual(eventPoint({clientX:250,clientY:130}, {left:10,top:10,width:480,height:240}, 960,480), [480,240]);
});
test('preview mapping uses each actual dimension independently', () => {
  assert.deepEqual(toOriginal([[96,60.5],[768,96.8]],960,121,1000,126), [[100,63],[800,100.8]]);
});
test('outside pointer positions clamp to the image interior', () => {
  assert.deepEqual(eventPoint({clientX:999,clientY:-10}, {left:0,top:0,width:480,height:240},960,480), [959,0]);
});
