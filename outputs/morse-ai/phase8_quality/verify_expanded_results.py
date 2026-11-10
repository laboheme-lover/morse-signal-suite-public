"""Independent artifact consistency checks for expanded noise and load reports."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent
sys.path.insert(0,str(PROJECT));sys.path.insert(0,str(ROOT))
from optical_video.field_eval import score
import evaluate_new

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    directory=ROOT/'noise_expanded';rows=json.loads((directory/'results.json').read_text(encoding='utf-8'))
    assert len(rows)==1464 and len({r['id'] for r in rows})==366
    assert len({(r['id'],r['model']) for r in rows})==1464
    for ident in {r['id'] for r in rows}:
        folder=directory/ident;meta=json.loads((folder/'input.json').read_text(encoding='utf-8'))
        assert sha(folder/'input.wav')==meta['sha256']
        if 'measured_snr_db' in meta['mix']:assert abs(meta['mix']['requested_snr_db']-meta['mix']['measured_snr_db'])<1e-8
        for model in ('M1','M2','M3','M4'):
            result=json.loads((folder/(model+'.json')).read_text(encoding='utf-8'));r=result['metric']
            measured=score(meta['reference'],result['text'])
            assert measured['edits']==r['edit_distance'] and measured['reference_units']==r['reference_units']
            assert r['edit_distance']==r['substitutions']+r['insertions']+r['deletions']
    summary=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    for s in summary:
        subset=[r for r in rows if all(r[k]==s[k] for k in ('noise','snr_db','model'))]
        assert len(subset)==s['cases']
        assert sum(r['edit_distance'] for r in subset)==s['edits']
        assert abs(s['cer']-s['edits']/sum(r['reference_units'] for r in subset))<1e-12
    for r in rows:
        if r['noise']=='clean':assert r['edit_distance']==0
    ops=ROOT/'model_operations';runs=json.loads((ops/'runs.json').read_text(encoding='utf-8'))
    assert len(runs)==12
    for r in runs:
        assert r['threads']==4 and len(r['results'])==3 and r['ready_seconds']>0
        for c in r['results']:
            assert len(c['warmed_seconds'])==5 and all(t>0 for t in c['warmed_seconds'])
            assert c['score']['edit_distance']==0
    evaluate_new.verify_frozen()
    result=dict(status='PASS',noise_conditions=366,noise_model_cases=1464,score_crosscheck='Independent Levenshtein distance implementation',input_wav_hashes=True,
        aggregate_denominators=True,operation_processes=12,operation_requests=216,frozen_models_and_code=True)
    (ROOT/'expanded_final_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':main()
