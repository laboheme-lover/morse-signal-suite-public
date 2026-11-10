"""Read-only comparison of normalized saved evaluations; no inference or tuning."""
import hashlib
import json
from collections import defaultdict

SCHEMA = 'morse-saved-evaluation-v1'

def distance(a, b):
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j-1] + (x != y)))
        previous = current
    return previous[-1]

def load_bundle(raw):
    if len(raw) > 20_000_000:
        raise ValueError('ファイルは20 MB以下にしてください。')
    try:
        data = json.loads(raw)
        if not isinstance(data, dict): raise ValueError('評価JSONはオブジェクトにしてください。')
        if data['schema'] != SCHEMA or not data['scoring_policy'] or not data['scope']:
            raise ValueError('評価形式が対応していません。')
        if not isinstance(data['name'], str) or not isinstance(data['rows'], list) or len(data['rows']) > 10000:
            raise ValueError('評価名または件数が不正です。')
        seen = set()
        for r in data['rows']:
            if not isinstance(r, dict): raise ValueError('評価行が不正です。')
            if not all(isinstance(r[k], str) for k in ('id','model','input_sha256','reference','hypothesis')):
                raise ValueError('文字列フィールドが不正です。')
            if len(r['reference']) > 2000 or len(r['hypothesis']) > 2000:
                raise ValueError('本文が長すぎます。')
            if len(r['input_sha256']) != 64 or any(c not in '0123456789abcdef' for c in r['input_sha256']):
                raise ValueError('音声ハッシュが不正です。')
            key = (r['id'], r['model'])
            if key in seen: raise ValueError('重複した評価行です。')
            seen.add(key)
            edits = distance(r['reference'], r['hypothesis'])
            if type(r['edits']) is not int or r['edits'] != edits or r['reference_units'] != len(r['reference']) or not r['reference']:
                raise ValueError('本文と採点値が一致しません。')
            if r['status'] not in ('OK','REVIEW','FAILED'):
                raise ValueError('状態が不正です。')
        return data
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('比較用JSONの形式が不正です。') from exc

def aggregate(rows):
    groups = defaultdict(list)
    for r in rows: groups[(r['evaluation'],r['model'])].append(r)
    return [dict(評価=name, モデル=model, 件数=len(rs), 正解文字数=sum(r['reference_units'] for r in rs),
                 編集距離=sum(r['edits'] for r in rs), CER=sum(r['edits'] for r in rs)/sum(r['reference_units'] for r in rs),
                 完全一致=sum(r['edits']==0 and r['status']!='FAILED' for r in rs),
                 処理失敗=sum(r['status']=='FAILED' for r in rs)) for (name,model),rs in groups.items()]

def paired(left, right):
    """Caller supplies one model per side. Match bytes AND normalized reference."""
    def index(rows):
        result = defaultdict(dict)
        for r in rows:
            key = (r['input_sha256'], r['reference'])
            if r['id'] in result[key]: raise ValueError('同じ条件ID・音声・正解文が重複しています。')
            result[key][r['id']] = r
        return result
    a,b = index(left),index(right)
    matches=[];repeated=0
    for key in a.keys() & b.keys():
        if len(a[key])==len(b[key])==1:matches.append((next(iter(a[key].values())),next(iter(b[key].values()))))
        else:
            for ident in a[key].keys() & b[key].keys():
                matches.append((a[key][ident],b[key][ident]));repeated+=1
    units=sum(x['reference_units'] for x,y in matches)
    return dict(共通件数=len(matches), 左のみ=len(left)-len(matches), 右のみ=len(right)-len(matches),
                左CER=sum(x['edits'] for x,y in matches)/units if units else None,
                右CER=sum(y['edits'] for x,y in matches)/units if units else None,
                改善件数=sum(y['edits']<x['edits'] for x,y in matches),
                悪化件数=sum(y['edits']>x['edits'] for x,y in matches),重複音声の条件ID一致=repeated)
