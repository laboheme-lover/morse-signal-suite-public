"""Text policy v2: mode controls are not text; unsupported codes require review."""
from morse_table import MORSE_TABLE,REVERSE_TABLE
from mixed_morse import INTERNATIONAL_REVERSE

UNKNOWN='□'
RULE_EXTRA={'..--..':'?'}

def interpret(rows,mixed_mode=True):
    inside=False;warnings=[]
    framing=len(rows)>6 and [r['pattern'] for r in rows[:5]]==['....','.-.','....','.-.','-...-'] and rows[-1]['pattern']=='.-.-.'
    for i,row in enumerate(rows):
        pattern=row['pattern'];row['mode']='international' if inside else 'wabun'
        row['kind']='character';row['text_prediction']=row['prediction'];row['unsupported_code']=False
        row['review_reason']='';row.pop('prosign',None)
        row['rule_prediction']=RULE_EXTRA.get(pattern,REVERSE_TABLE.get(pattern,'?'))
        if pattern in ('-..---','...-.') or (framing and i in (4,len(rows)-1)):
            row['kind']='prosign';row['prosign']={'-..---':'ホレ','...-.':'ラタ','-...-':'BT','.-.-.':'AR'}[pattern]
            row['text_prediction']='';row['rule_prediction']=''
            if inside:warnings.append(f"segment {row['index']}: prosign inside unclosed parentheses")
            inside=False
        elif mixed_mode and pattern in (MORSE_TABLE['（'],MORSE_TABLE['）']):
            opening=pattern==MORSE_TABLE['（']
            if opening==inside:
                message=f"segment {row['index']}: "+('nested parentheses' if opening else 'unmatched closing parenthesis')
                warnings.append(message);row['review_reason']=message
            inside=opening;row['kind']='mode_control';row['prosign']='欧文開始' if opening else '和文復帰'
            row['text_prediction']='';row['rule_prediction']=''
        elif pattern not in REVERSE_TABLE:
            row['unsupported_code']=True;row['text_prediction']=UNKNOWN
            row['review_reason']='学習クラスにない符号です。元の予測候補を本文に採用していません。'
        elif mixed_mode and inside:
            row['text_prediction']=INTERNATIONAL_REVERSE.get(MORSE_TABLE.get(row['prediction'],''),UNKNOWN)
            row['rule_prediction']=INTERNATIONAL_REVERSE.get(pattern,'?')
        translate=mixed_mode and row['mode']=='international' and row['kind']=='character'
        row['display_candidates']=[dict(c,display_label=INTERNATIONAL_REVERSE.get(MORSE_TABLE.get(c['label'],''),UNKNOWN) if translate else c['label']) for c in row.get('top_k',[])]
        row['disagrees_with_rule']=row['kind']=='character' and row['text_prediction']!=row['rule_prediction']
    if inside:warnings.append('Unclosed international-mode parentheses at end of recording')
    return warnings
