"""Wabun parentheses are punctuation, never international-mode switches."""
import copy,unicodedata
from recognition_policy import interpret
from evaluate_recording import canonical_reference
from morse_table import MORSE_TABLE
VERSION='wabun-parentheses-v1'
def normalize_reference(text):
    text=unicodedata.normalize('NFKC',text)
    text=''.join(c for c in text if c not in '()「」★')
    return canonical_reference(text)
def render_body(source):
    rows=copy.deepcopy(source)
    for r in rows:
        if 'observed_pattern' in r:r['pattern']=r.pop('observed_pattern')
    warnings=interpret(rows,mixed_mode=False)
    punctuation={MORSE_TABLE[c] for c in '、」（）'}
    text=''.join(r['text_prediction'] for r in rows if r['pattern'] not in punctuation)
    return text,rows,warnings
