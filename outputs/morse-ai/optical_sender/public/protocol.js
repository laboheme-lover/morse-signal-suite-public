export const SCHEMA_VERSION = '1.0.0';
export const PROTOCOL_VERSION = 'wabun-optical-1.0.0';
export const NORMALIZATION_VERSION = 'audio-nfkc-nfd-trace-1.0.0';
export const TIMING = Object.freeze({dot_ms: 200, dash_ms: 600, intra_symbol_gap_ms: 200,
  character_gap_ms: 600, pre_start_wait_ms: 3000});
export const LIMITS = Object.freeze({max_signal_duration_ms: 60000, max_transition_lateness_ms: 50});

export function id(prefix) {
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes); // available on LAN HTTP; randomUUID need not be
  return `${prefix}-${Array.from(bytes, v => v.toString(16).padStart(2, '0')).join('')}`;
}
export function deepFreeze(value) {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    Object.values(value).forEach(deepFreeze); Object.freeze(value);
  }
  return value;
}

export class InputError extends Error {
  constructor(issues) { super(issues.map(i => i.message).join('\n')); this.issues = issues; }
}

export function normalizeInput(original, table) {
  const tokens = [], issues = [];
  if (!original.length) throw new InputError([{position: 0, source: '', message: '文章が空です。'}]);
  if (Array.from(original).length > 1000) throw new InputError([{position: 0, source: '', message: '入力は1,000文字以内にしてください。'}]);
  let offset = 0, position = 0;
  for (const source of original) {
    position++;
    const expanded = source.replaceAll('゛', '\u3099').replaceAll('゜', '\u309a').normalize('NFKC').normalize('NFD');
    for (let label of expanded) {
      const code = label.codePointAt(0);
      if (code >= 0x3041 && code <= 0x3096) label = String.fromCodePoint(code + 0x60);
      label = ({'\u3099':'゛','\u309a':'゜','(':'（',')':'）'})[label] || label;
      let reason = '';
      if (table.deferred_tokens.includes(label)) reason = '括弧と括弧内欧文は次段階の対象です。';
      else if (/\s/u.test(label)) reason = '空白・改行の送信間隔は未定義です。';
      else if (!Object.hasOwn(table.entries, label)) reason = `変換後の「${label}」は未対応です（小書きカナ・英字・漢字等）。`;
      if (reason) issues.push({position, utf16_offset: offset, source, normalized: label,
        message: `${position}文字目 ${JSON.stringify(source)}：${reason}`});
      else tokens.push({index: tokens.length, label, code: table.entries[label], source,
        source_position: position, source_utf16_offset: offset});
    }
    offset += source.length;
  }
  if (issues.length) throw new InputError(issues);
  return tokens;
}

export function buildPlan(original, table, display, planId = id('plan')) {
  const tokens = normalizeInput(original, table), intervals = [];
  let t = 0;
  function add(duration, state, kind, token_index, symbol_index) {
    intervals.push({start_ms: t, end_ms: t + duration, state, kind, token_index, symbol_index}); t += duration;
  }
  tokens.forEach((token, ti) => {
    Array.from(token.code).forEach((symbol, si) => {
      if (si) add(TIMING.intra_symbol_gap_ms, 'off', 'intra_symbol_gap', ti, si - 1);
      add(symbol === '.' ? TIMING.dot_ms : TIMING.dash_ms, 'on', symbol === '.' ? 'dot' : 'dash', ti, si);
    });
    if (ti < tokens.length - 1) add(TIMING.character_gap_ms, 'off', 'character_gap', ti, null);
  });
  if (t > LIMITS.max_signal_duration_ms) throw new InputError([{position: 0, source: original,
    message: `送信予定は${(t / 1000).toFixed(1)}秒です。上限60秒以内に短くしてください（開始前待機は別）。`}]);
  return deepFreeze({schema_version: SCHEMA_VERSION, protocol_version: PROTOCOL_VERSION,
    plan_id: planId, table_version: table.table_version, normalization_version: NORMALIZATION_VERSION,
    original_text: original, transmit_text: tokens.map(t => t.label).join(''), tokens,
    timing: {...TIMING}, limits: {...LIMITS}, display: {...display},
    interval_convention: '[start_ms,end_ms)', intervals, total_duration_ms: t});
}
