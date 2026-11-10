"""Run pure-Java Android logic checks with generated synthetic light traces."""
import ast
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
table = {}
for node in ast.parse((ROOT / 'outputs/morse-ai/morse_table.py').read_text(encoding='utf-8')).body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ('KANA', 'MARKS', 'DIGITS', 'SYMBOLS') for t in node.targets):
        table.update(ast.literal_eval(node.value))
if len(table) != 65:
    raise AssertionError('Expected 65 Wabun symbols')
for executable in ('javac', 'java'):
    if not shutil.which(executable):
        raise RuntimeError('JDK 17 required on PATH: ' + executable)
with tempfile.TemporaryDirectory() as temp:
    folder = Path(temp)
    expected = folder / 'expected.tsv'
    expected.write_text('\n'.join(k + '\t' + v for k, v in table.items()), encoding='utf-8')
    states = [(False, 7)]
    for code in ('.-..', '..', '...'):  # independently specified KA + dakuten + RA
        for i, mark in enumerate(code):
            states.extend([(True, 1 if mark == '.' else 3), (False, 1 if i < len(code)-1 else 3)])
    states.append((False, 7))
    for fps in (30, 15):
        rows = []
        for on, units in states:
            for _ in range(round(units * .6 * fps)):
                rows.append(f'{len(rows)/fps:.9f}\t{235 if on else 16}')
        (folder / f'light_{fps}fps.tsv').write_text('\n'.join(rows), encoding='utf-8')
    source = ROOT / 'android-morse/app/src/main/java/jp/local/wabun'
    classes = ['JapaneseNumbers', 'MorseCodec', 'TextInput', 'OpticalSignal']
    subprocess.run(['javac', '-encoding', 'UTF-8', '-d', temp,
                    *[str(source / (name + '.java')) for name in classes],
                    str(ROOT / 'android-morse/core-tests/CoreTest.java')], check=True)
    subprocess.run(['java', '-Dfile.encoding=UTF-8', '-cp', temp, 'CoreTest', str(expected), temp], check=True)
    sender = ROOT / 'android-morse/opticaltest/src/main/java/jp/local/wabun'
    tests = ['BatchSelectionTest', 'RemoteStartPolicyTest']
    subprocess.run(['javac', '-encoding', 'UTF-8', '-cp', temp, '-d', temp,
                    *[str(sender / (name + '.java')) for name in ('BatchSelection', 'BatchRange', 'RemoteStartPolicy', 'OpticalHeader')],
                    *[str(ROOT / 'optical-batch-test' / (name + '.java')) for name in tests]], check=True)
    for name in tests:
        subprocess.run(['java', '-Dfile.encoding=UTF-8', '-cp', temp, name], check=True)
