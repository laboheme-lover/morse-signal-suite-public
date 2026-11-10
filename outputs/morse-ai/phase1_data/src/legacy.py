"""Read-only adapters. Extract constants/functions, avoiding legacy ML imports."""
import ast
from pathlib import Path
import numpy as np
from .common import ROOT

PROJECT = ROOT.parent


def legacy_tables(project=PROJECT):
    tree = ast.parse((Path(project) / 'morse_table.py').read_text(encoding='utf-8-sig'))
    groups = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
              if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
              and n.targets[0].id in ('KANA', 'MARKS', 'DIGITS', 'SYMBOLS')}
    wabun = groups['KANA'] | groups['MARKS'] | groups['DIGITS'] | groups['SYMBOLS']
    tree = ast.parse((Path(project) / 'mixed_morse.py').read_text(encoding='utf-8-sig'))
    latin = next(n.value for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == 'LATIN')
    args = latin.args[0].args  # existing LATIN=dict(zip(literal alphabet, literal code list))
    international = dict(zip(ast.literal_eval(args[0]), ast.literal_eval(args[1]))) | groups['DIGITS']
    return wabun, international


def legacy_mix():
    tree = ast.parse((PROJECT / 'augment_audio.py').read_text(encoding='utf-8-sig'))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'mix_at_snr')
    namespace = {'np': np}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(PROJECT / 'augment_audio.py'), 'exec'), namespace)
    return namespace['mix_at_snr']
