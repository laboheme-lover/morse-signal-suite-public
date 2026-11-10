"""Explicit v2 evaluation policy; historical scores stay immutable."""
from pathlib import Path
import sys,re,unicodedata,copy
PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT))
from evaluate_recording import canonical_reference
from recognition_policy import interpret
from morse_table import MORSE_TABLE

def normalize_reference(text):
    text=unicodedata.normalize('NFKC',text)
    text=re.sub(r'^\s*HR\s+HR\s*','',text)
    text=re.sub(r'<(?:ホレ|ラタ)>','',text)
    result=[];inside=False
    for i,c in enumerate(text):
        if c=='(':
            if inside:raise ValueError('Nested reference parentheses')
            inside=True;continue
        if c==')':
            if not inside:raise ValueError('Unmatched reference close')
            inside=False;continue
        if c in '★「」' or c.isspace():continue
        if c=='?':result.append('?');continue
        decimal=c=='.' and i>0 and i+1<len(text) and text[i-1].isascii() and text[i-1].isdigit() and text[i+1].isascii() and text[i+1].isdigit()
        if decimal:result.append('.' if inside else 'テン');continue
        if inside and c in '.,':result.append(c);continue
        if c.isascii() and c.isalpha():result.append(c.upper());continue
        result.append(canonical_reference(c))
    if inside:raise ValueError('Unclosed reference parentheses')
    return ''.join(result)

def render_body(source):
    rows=copy.deepcopy(source)
    # Determine punctuation role before interpretation mutates the rule label.
    inside=False;included=[]
    for row in rows:
        pattern=row['pattern']
        if pattern==MORSE_TABLE['（']:inside=True;included.append(False)
        elif pattern==MORSE_TABLE['）']:inside=False;included.append(False)
        else:included.append(inside or row['rule_prediction'] not in '、」')
    warnings=interpret(rows)
    return ''.join(r['text_prediction'] for r,keep in zip(rows,included) if keep),rows,warnings
