import assert from 'node:assert/strict';
import test from 'node:test';
import { CoverageGeneration, presentApprovedEvaluation } from '../src/features/counseling/coverage/coverage-safety.ts';

test('approved Evaluation distinguishes omission, null, empty and numeric values',()=>{
 const fields=presentApprovedEvaluation({academic_adjustment_rating:null,recommendations:'',social_adjustment_rating:7});
 assert.deepEqual(fields.map(f=>[f.key,f.value]),[['academic_adjustment_rating','Not rated'],['social_adjustment_rating','7'],['recommendations','No text recorded']]);
});
test('an ordinary future Evaluation field does not enter the pinned display inventory',()=>assert.deepEqual(presentApprovedEvaluation({future_sensitive_field:'never display'}),[]));
test('Unicode and whitespace in approved narratives remain exact',()=>{const value='  你好\nsecond line  \n';assert.equal(presentApprovedEvaluation({recommendations:value})[0].value,value);});
test('empty projection does not invent placeholders or ratings',()=>assert.deepEqual(presentApprovedEvaluation({}),[]));
test('current generation permits the response',()=>{const barrier=new CoverageGeneration();barrier.assertCurrent(barrier.current());});
for(const reason of ['revocation','expiry','account switch','logout','hidden tab','offline','policy unavailable']){
 test(`${reason} invalidates an already started protected response`,async()=>{
  const barrier=new CoverageGeneration();const captured=barrier.current();let release;
  const response=new Promise(resolve=>{release=resolve;});
  const guarded=response.then(()=>barrier.assertCurrent(captured));barrier.invalidate();release();
  await assert.rejects(guarded,/access needs to be checked/);
 });
}
test('request cancellation rejects a response even in the current generation',()=>{const barrier=new CoverageGeneration(),controller=new AbortController();controller.abort();assert.throws(()=>barrier.assertCurrent(barrier.current(),controller.signal));});
test('generation never reuses an invalidated response after a deliberate check',()=>{const barrier=new CoverageGeneration(),old=barrier.current();barrier.invalidate();barrier.invalidate();assert.throws(()=>barrier.assertCurrent(old));barrier.assertCurrent(barrier.current());});
