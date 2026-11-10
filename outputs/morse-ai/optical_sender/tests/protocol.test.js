import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {buildPlan, normalizeInput, LIMITS} from '../public/protocol.js';
import {Sender} from '../public/scheduler.js';
const table = JSON.parse(readFileSync(new URL('../public/morse_table.json', import.meta.url)));
const display = {position:'viewport_center', width_css_px:48, height_css_px:48,
  center_x_css_px:180, center_y_css_px:400, viewport_width_css_px:360, viewport_height_css_px:800,
  device_pixel_ratio:1, visual_viewport_width:360, visual_viewport_height:800, visual_viewport_scale:1,
  visual_viewport_offset_top:0, visual_viewport_offset_left:0,
  on_color:'#ffffff', off_color:'#000000', background_color:'#000000'};
const plan = text => buildPlan(text, table, display);
function fake() {
  let t = 100, callback, lit = false, reason = null, calls = 0;
  const sender = new Sender({now:()=>t, requestFrame:cb=>{callback=cb;return ++calls;}, cancelFrame:()=>{callback=null;},
    paint:on=>{lit=on;}, checkEnvironment:()=>reason, wallClock:()=> '2026-09-17T00:00:00.000Z'});
  return {sender, get lit(){return lit;}, get calls(){return calls;}, setReason:r=>{reason=r;},
    tick:ms=>{t=100+ms;const cb=callback;callback=null;cb?.();}};
}
test('イ: dot, gap, dash; イイ: exactly 600ms between characters', () => {
  const p=plan('イ'); assert.equal(p.total_duration_ms,1000);
  assert.deepEqual(p.intervals.map(i=>[i.start_ms,i.end_ms,i.kind]),[[0,200,'dot'],[200,400,'intra_symbol_gap'],[400,1000,'dash']]);
  const p2=plan('イイ');assert.equal(p2.total_duration_ms,2600);
  assert.deepEqual(p2.intervals[3],{start_ms:1000,end_ms:1600,state:'off',kind:'character_gap',token_index:0,symbol_index:null});
});
test('all sendable labels produce contiguous positive intervals with matching token indices', () => {
  for(const label of Object.keys(table.entries).filter(l=>!table.deferred_tokens.includes(l))) {
    const p=plan(label); let end=0;
    for(const interval of p.intervals) {assert.equal(interval.start_ms,end);assert.ok(interval.end_ms>end);end=interval.end_ms;assert.ok(p.tokens[interval.token_index]);}
    assert.equal(end,p.total_duration_ms);assert.equal(p.intervals.at(-1).state,'on');
  }
});
test('normalization and trace preserve source and split voiced kana', () => {
  const p=plan('がぱヴｶﾞ１２');assert.equal(p.original_text,'がぱヴｶﾞ１２');assert.equal(p.transmit_text,'カ゛ハ゜ウ゛カ゛12');
  assert.equal(p.tokens[1].source_position,1);assert.equal(p.tokens[1].source,'が');
  assert.ok(Object.isFrozen(p.intervals[0]));assert.throws(()=>p.intervals[0].start_ms=9);
});
test('normalization matches reference Python corpus', () => {
  const fixtures=JSON.parse(readFileSync(new URL('../artifacts/normalization_fixtures.json',import.meta.url)));
  for (const row of fixtures) {
    if (row.error) assert.throws(()=>normalizeInput(row.input,table),row.input);
    else assert.equal(normalizeInput(row.input,table).map(t=>t.label).join(''),row.output,row.input);
  }
});
test('invalid input includes its position; never silently drops characters', () => {
  for(const s of ['', ' ', 'イ\nイ','イ イ','イッ','漢字','A','（イ）','(IPCC)','イ。','😀']) assert.throws(()=>plan(s));
  try{plan('イ 漢');assert.fail();}catch(e){assert.deepEqual(e.issues.map(i=>i.position),[2,3]);}
  assert.throws(()=>plan('ム'.repeat(51)),/60秒/);
  assert.equal(plan('ム'.repeat(50)).total_duration_ms,59400);
  assert.throws(()=>plan('イ'.repeat(1001)),/1,000/);
});
test('normal completion includes 3s wait and terminal off; no auto repeat', () => {
  const f=fake();f.sender.start(plan('イ'));assert.equal(f.lit,false);
  f.tick(2999);assert.equal(f.lit,false);f.tick(3000);assert.equal(f.lit,true);
  f.tick(3200);assert.equal(f.lit,false);f.tick(3400);assert.equal(f.lit,true);
  f.tick(4000);assert.equal(f.lit,false);assert.equal(f.sender.log.status,'completed');
  assert.equal(f.sender.log.transitions.at(-1).planned_time_ms,1000);
  const calls=f.calls;f.tick(9000);assert.equal(f.calls,calls);
});
test('double start rejected, stops during wait and while lit', () => {
  for(const elapsed of [0,3000]) {
    const f=fake();f.sender.start(plan('イ'));assert.throws(()=>f.sender.start(plan('イ')));
    if(elapsed)f.tick(elapsed);f.sender.stop();assert.equal(f.lit,false);assert.equal(f.sender.log.status,'stopped');
    f.tick(3400);assert.equal(f.lit,false);
  }
});
test('50ms allowed, >50ms interrupted, skipped boundaries never caught up', () => {
  const a=fake();a.sender.start(plan('イ'));a.tick(3050);assert.equal(a.sender.log.status,'running');assert.equal(a.sender.log.transitions.at(-1).lateness_ms,50);
  for(const delay of [3051,3500,6000]) {
    const f=fake();f.sender.start(plan('イ'));f.tick(delay);
    assert.equal(f.sender.log.status,'interrupted');assert.equal(f.sender.log.abort_reason,'transition_late');
    assert.equal(f.sender.log.transitions.filter(t=>t.state==='on').length,0);assert.equal(f.lit,false);
  }
});
test('late final off still extinguishes and records interruption', () => {
  const f=fake();f.sender.start(plan('イ'));for(const t of [3000,3200,3400,4051])f.tick(t);
  assert.equal(f.sender.log.status,'interrupted');assert.equal(f.lit,false);
});
test('visibility, display changes interrupt without automatic resume', () => {
  for(const reason of ['page_hidden','display_changed','lamp_geometry_changed']) {
    const f=fake();f.sender.start(plan('イ'));f.tick(3000);f.setReason(reason);f.tick(3010);
    assert.equal(f.sender.log.abort_reason,reason);assert.equal(f.lit,false);f.setReason(null);f.tick(3400);assert.equal(f.lit,false);
  }
});
test('explicit visibility event works while rAF is suspended', () => {
  const f=fake();f.sender.start(plan('イ'));f.tick(3000);f.sender.interrupt('page_hidden');
  assert.equal(f.lit,false);assert.equal(f.sender.active,false);
});
test('paint exceptions end run as error', () => {
  let light=false;
  const s=new Sender({now:()=>0,requestFrame:()=>1,cancelFrame:()=>{},paint:on=>{light=on;throw Error('paint failed');}});
  s.start(plan('イ'));assert.equal(s.log.status,'error');assert.equal(s.active,false);assert.equal(light,false);
});
test('plan and run serialize independently; sample artifacts', () => {
  const p=plan('イ');const f=fake();f.sender.start(p,{test:'virtual-clock'});
  for(const t of [3000,3200,3400,4000])f.tick(t);
  assert.equal(JSON.parse(JSON.stringify(p)).total_duration_ms,1000);
  assert.equal(JSON.parse(JSON.stringify(f.sender.log)).plan_id,p.plan_id);
  const dir=new URL('../artifacts/',import.meta.url);mkdirSync(dir,{recursive:true});
  writeFileSync(new URL('plan_i.json',dir),JSON.stringify(p,null,2));
  writeFileSync(new URL('plan_ii.json',dir),JSON.stringify(plan('イイ'),null,2));
  writeFileSync(new URL('run_virtual_i.json',dir),JSON.stringify(f.sender.log,null,2));
});
