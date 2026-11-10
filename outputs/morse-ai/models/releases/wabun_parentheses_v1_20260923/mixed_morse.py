"""User-confirmed convention: international Morse inside Wabun parentheses."""
import re
import unicodedata
from morse_table import MORSE_TABLE,DIGITS,REVERSE_TABLE
from evaluate_recording import canonical_reference

LATIN=dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ',
    ['.-','-...','-.-.','-..','.','..-.','--.','....','..','.---','-.-','.-..','--','-.','---','.--.','--.-','.-.','...','-','..-','...-','.--','-..-','-.--','--..']))
INTERNATIONAL=LATIN|DIGITS|{'.':'.-.-.-',',':'--..--'}
INTERNATIONAL_REVERSE={v:k for k,v in INTERNATIONAL.items()}

def normalize_mixed_reference(text):
    text=unicodedata.normalize('NFKC',text)
    text=re.sub(r'^\s*HR\s+HR\s*','',text)
    text=re.sub(r'<(?:ホレ|ラタ)>','',text)
    result=[];inside=False
    for c in text:
        if c.isspace():continue
        if c=='(':
            if inside:raise ValueError('Nested reference parentheses')
            inside=True;result.append('（')
        elif c==')':
            if not inside:raise ValueError('Unmatched reference close')
            inside=False;result.append('）')
        elif inside:
            c=c.upper()
            if c not in INTERNATIONAL:raise ValueError(f'Unsupported international character: {c}')
            result.append(c)
        elif c not in '★?「」':result.append(canonical_reference(c))
    if inside:raise ValueError('Unclosed reference parentheses')
    return ''.join(result)

def decode_mixed(rows):
    """Gate mode by observed delimiters; preserve CNN codes within either mode."""
    cnn=[];rule=[];inside=False
    for r in rows:
        pattern=r['pattern']
        cnn_code=MORSE_TABLE.get(r['prediction'],'?')
        if pattern==MORSE_TABLE['（']:
            if inside:raise ValueError('Nested audio parentheses')
            cnn.append(r['prediction']);rule.append('（');inside=True
        elif pattern==MORSE_TABLE['）']:
            if not inside:raise ValueError('Unmatched audio close')
            cnn.append(r['prediction']);rule.append('）');inside=False
        elif inside:
            cnn.append(INTERNATIONAL_REVERSE.get(cnn_code,'?'))
            rule.append(INTERNATIONAL_REVERSE.get(pattern,'?'))
        elif r['rule_prediction'] not in '、」':
            cnn.append(r['prediction']);rule.append(r['rule_prediction'])
    if inside:raise ValueError('Unclosed audio parentheses')
    return ''.join(cnn),''.join(rule)
