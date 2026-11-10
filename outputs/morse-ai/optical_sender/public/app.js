import {buildPlan} from './protocol.js';
import {Sender} from './scheduler.js';

const $ = id => document.getElementById(id);
let table, plan = null, lastRunPlan = null;
function display() {
  return {position: 'viewport_center', width_css_px: 48, height_css_px: 48,
    center_x_css_px: document.documentElement.clientWidth / 2, center_y_css_px: document.documentElement.clientHeight / 2,
    viewport_width_css_px: document.documentElement.clientWidth, viewport_height_css_px: document.documentElement.clientHeight,
    device_pixel_ratio: devicePixelRatio, visual_viewport_width: visualViewport?.width ?? innerWidth,
    visual_viewport_height: visualViewport?.height ?? innerHeight,
    visual_viewport_scale: visualViewport?.scale ?? 1,
    visual_viewport_offset_top: visualViewport?.offsetTop ?? 0,
    visual_viewport_offset_left: visualViewport?.offsetLeft ?? 0,
    on_color: '#ffffff', off_color: '#000000', background_color: '#000000'};
}
function changed() { return JSON.stringify(display()) !== JSON.stringify(plan?.display); }
function environmentReason() {
  if (document.hidden) return 'page_hidden';
  if (changed()) return 'display_changed';
  const rect = $('lamp').getBoundingClientRect();
  if (Math.abs(rect.width - 48) > .5 || Math.abs(rect.height - 48) > .5 ||
    Math.abs(rect.x + 24 - plan.display.center_x_css_px) > .5 ||
    Math.abs(rect.y + 24 - plan.display.center_y_css_px) > .5) return 'lamp_geometry_changed';
  return null;
}
const labels = {waiting:'開始前待機（3秒）', running:'送信中', completed:'完了・消灯',
  stopped:'停止・消灯', interrupted:'中断・消灯', error:'エラー・消灯'};
const sender = new Sender({paint: on => $('lamp').classList.toggle('on', on), checkEnvironment: environmentReason,
  notify: (state, log) => {
    $('status').textContent = labels[state] + (log.abort_reason ? `：${log.abort_reason}` : '');
    $('stage-status').textContent = labels[state];
    if (!sender.active) {
      $('stage').hidden = true; $('controls').inert = false;
      $('input-controls').disabled = false; $('save-log').disabled = false;
      updatePlanSave(); updateStart();
    }
  }});

function updateStart() { $('start').disabled = sender.active || !plan || !$('ack').checked; }
function updatePlanSave() {
  $('save-plan').disabled = sender.active || !(plan || lastRunPlan);
  $('save-plan').textContent = !plan && lastRunPlan ? '直近の送信予定JSONを保存' : '予定JSONを保存';
}
function invalidate() {
  if (sender.active) return;
  plan = null; $('preview').hidden = true; updatePlanSave(); updateStart();
}
function prepare() {
  if (sender.active) return;
  invalidate(); $('error').textContent = '';
  try {
    plan = buildPlan($('message').value, table, display());
    $('transmit-text').textContent = plan.transmit_text;
    $('duration').textContent = `${plan.tokens.length}送信単位 / 信号 ${(plan.total_duration_ms / 1000).toFixed(1)}秒 ＋ 待機3秒`;
    $('tokens').replaceChildren();
    for (const token of plan.tokens) {
      const row = document.createElement('tr');
      for (const value of [token.index + 1, token.source_position, token.label, token.code]) {
        const cell = document.createElement('td'); cell.textContent = value; row.append(cell);
      }
      $('tokens').append(row);
    }
    $('preview').hidden = false; updatePlanSave();
    $('status').textContent = '内容を確認し、開始ボタンを押してください。'; updateStart();
  } catch (error) { $('error').textContent = error.message; }
}

function download(data, filename) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type:'application/json'}));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename;
  document.body.append(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
$('prepare').addEventListener('click', prepare);
$('message').addEventListener('input', () => { invalidate(); $('error').textContent = ''; });
$('ack').addEventListener('change', updateStart);
$('start').addEventListener('click', () => {
  if (sender.active || !plan || !$('ack').checked) return;
  if (document.hidden || changed()) { invalidate(); $('error').textContent = '表示領域が変わりました。画面とキーボードを固定して、もう一度送信内容を確認してください。'; return; }
  $('input-controls').disabled = true; $('start').disabled = true;
  $('save-plan').disabled = true; $('save-log').disabled = true;
  $('stage').hidden = false; $('controls').inert = true; $('stop').focus();
  lastRunPlan = plan;
  sender.start(plan, {user_agent: navigator.userAgent, language: navigator.language,
    platform: navigator.platform, screen_width: screen.width, screen_height: screen.height,
    device_pixel_ratio: devicePixelRatio, secure_context: isSecureContext, display: display()});
});
$('stop').addEventListener('click', () => { sender.stop(); $('lamp').classList.remove('on'); });
$('save-plan').addEventListener('click', () => {
  const selected = plan || lastRunPlan;
  if (selected && !sender.active) download(selected, `${selected.plan_id}.json`);
});
$('save-log').addEventListener('click', () => { if (sender.log && !sender.active) download(sender.log, `${sender.log.run_id}.json`); });
document.addEventListener('visibilitychange', () => { if (document.hidden) sender.interrupt('page_hidden'); });
window.addEventListener('pagehide', () => { sender.interrupt('page_hidden'); $('lamp').classList.remove('on'); });
window.addEventListener('pageshow', () => { $('lamp').classList.remove('on'); });
function resized() {
  if (sender.active) sender.interrupt('display_changed');
  else if (plan && changed()) {
    invalidate(); $('error').textContent = '画面サイズが変わりました。もう一度送信内容を確認してください。';
  }
}
window.addEventListener('resize', resized);
window.addEventListener('orientationchange', resized);
window.visualViewport?.addEventListener('resize', resized);
window.visualViewport?.addEventListener('scroll', () => { if (sender.active) sender.interrupt('display_changed'); });
window.addEventListener('keydown', e => { if (e.key === 'Escape') sender.stop(); });
window.addEventListener('error', event => { if (sender.active) sender.fail(event.error || new Error(event.message)); });
window.addEventListener('unhandledrejection', event => { if (sender.active) sender.fail(new Error(String(event.reason))); });

try {
  const response = await fetch('morse_table.json', {cache:'no-store'});
  if (!response.ok) throw new Error(`対応表 HTTP ${response.status}`);
  table = await response.json();
  if (!table.entries || !table.table_version || !Array.isArray(table.deferred_tokens)) throw new Error('対応表の形式が不正です。');
  $('input-controls').disabled = false; $('status').textContent = '待機・消灯。送信内容を確認してください。';
} catch (error) { $('error').textContent = `読込失敗：${error.message}。serve.pyから開いてください。`; }
