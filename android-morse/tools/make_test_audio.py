"""Independent deterministic fixtures, using the established Wabun table."""
from pathlib import Path
import ast, array, json, math, random, wave
ROOT = Path(__file__).resolve().parents[1]
table = {}
source = ROOT.parent/'outputs/morse-ai/morse_table.py'
for node in ast.parse(source.read_text(encoding='utf-8')).body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ('KANA','MARKS','DIGITS','SYMBOLS') for t in node.targets):
        table.update(ast.literal_eval(node.value))
out = ROOT/'test-data'
out.mkdir(exist_ok=True)
cases = [
    ('01_clean_120ms', 'コンニチハ', 'こんにちは', .12, 0),
    ('02_marks_180ms', 'カ゛ツコウ ハ゜ヒ゜フ゜ヘ゜ホ゜ （123）', 'がつこう ぱぴぷぺぽ （123）', .18, 0),
    ('03_noise_240ms', 'アシタハハレ」', 'あしたははれ」', .24, .008),
]
manifest = []
for name, labels, expected, unit, noise in cases:
    pulses = [(False, 7)]
    for i, char in enumerate(labels):
        if char == ' ': continue
        code = table[char]
        for j, mark in enumerate(code):
            pulses.append((True, 1 if mark == '.' else 3))
            if j < len(code)-1: pulses.append((False, 1))
        pulses.append((False, 7 if i == len(labels)-1 or labels[i+1] == ' ' else 3))
    samples = array.array('h'); rate = 16000; rng = random.Random(20260929)
    for on, units in pulses:
        count = round(units*unit*rate)
        for i in range(count):
            ramp = min(1, i/(rate*.005), (count-1-i)/(rate*.005))
            v = (.25*ramp*math.sin(2*math.pi*700*i/rate) if on else 0)+rng.uniform(-noise, noise)
            samples.append(round(max(-1, min(1, v))*32767))
    with wave.open(str(out/(name+'.wav')), 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(rate); f.writeframes(samples.tobytes())
    manifest.append(dict(file=name+'.wav', expected=expected, dot_ms=round(unit*1000), frequency_hz=700, duration_seconds=len(samples)/rate, synthetic=True, real_device_verified=False))
(out/'expected.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print('Created', len(manifest), 'synthetic WAV fixtures:', out)
