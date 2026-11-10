"""Export the existing audio table without importing ML dependencies."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / 'morse_table.py'


def exported_table():
    source = SOURCE.read_bytes()
    tree = ast.parse(source.decode('utf-8-sig'))
    groups = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ('KANA', 'MARKS', 'DIGITS', 'SYMBOLS'):
                groups[name] = ast.literal_eval(node.value)
    table = {}
    for name in ('KANA', 'MARKS', 'DIGITS', 'SYMBOLS'):
        table.update(groups[name])
    canonical = json.dumps(table, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return {'table_version': 'sha256:' + hashlib.sha256(canonical.encode()).hexdigest(),
            'source': 'morse_table.py:MORSE_TABLE',
            'source_sha256': hashlib.sha256(source).hexdigest(),
            'entries': table,
            'deferred_tokens': ['（', '）']}


if __name__ == '__main__':
    target = ROOT / 'public' / 'morse_table.json'
    target.write_text(json.dumps(exported_table(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(target)
