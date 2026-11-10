"""Audit and freeze existing full Wabun splits without changing original data."""
from common import *
from collections import Counter
from src.test_protection import verify_lock

def main():
    if (ROOT/'reports/data_audit.json').exists() or (ROOT/'runs').exists(): raise FileExistsError('Already prepared')
    source=PROJECT/'data/dataset/m4_300'
    rows=read_csv(source/'metadata.csv')
    mapping={r['label']:int(r['class_index']) for r in rows}
    assert len(mapping)==65 and set(mapping.values())==set(range(65))
    groups={s:[] for s in ('train','validation','test')}
    hashes={}; noise_groups={}; seed_groups={}
    for r in rows:
        s=r['split'];p=source/r['filepath'];h=sha(p)
        assert h==r['wav_sha256'],str(p)
        if h in hashes and hashes[h]!=s: raise ValueError('Cross-split waveform duplicate')
        hashes[h]=s
        for field,seen in [('esc50_src_file',noise_groups),('base_sample_id',seed_groups)]:
            v=r[field]
            if v and v in seen and seen[v]!=s: raise ValueError(f'Cross-split {field}')
            if v: seen[v]=s
        groups[s].append({'filename':str(p.resolve()),'label':r['label'],'split':s,'sha256':h,
            'morse_code':r['morse_code'],'noise_type':r['noise_type'],'snr_db':r['snr_db'],'speed':r['speed']})
    assert len(groups['test'])==2925
    frozen=verify_lock(PROJECT/'phase1_data')
    (ROOT/'metadata').mkdir(exist_ok=True);(ROOT/'config').mkdir(exist_ok=True);(ROOT/'reports').mkdir(exist_ok=True)
    write_json(ROOT/'metadata/label_mapping.json',mapping)
    for split,items in groups.items(): write_csv(ROOT/f'metadata/{split}.csv',items)
    write_json(ROOT/'metadata/lock.json',{name:sha(ROOT/'metadata'/name) for name in ('train.csv','validation.csv','test.csv','label_mapping.json')})
    for i in range(1,5):
        cfg=json.loads((PROJECT/['phase2_m1','phase3_m2','phase4_m3','phase5_m4'][i-1]/f'config/m{i}.json').read_text())
        cfg['model']['classes']=65
        cfg['architecture']=cfg.get('architecture',f'M{i}')+'__wabun65'
        write_json(ROOT/f'config/m{i}.json',cfg)
    protected={str(source/'metadata.csv'):sha(source/'metadata.csv')}
    for name in ('phase2_m1','phase3_m2','phase4_m3','phase5_m4'):
        for p in (PROJECT/name).rglob('*'):
            if p.is_file() and (p.suffix in ('.pt','.py') or p.name=='test_metrics.json'):
                protected[str(p)]=sha(p)
    write_json(ROOT/'reports/protected_files.json',protected)
    result={'status':'PASS','source':str(source),'split_counts':{s:len(r) for s,r in groups.items()},
        'class_counts':{s:dict(Counter(r['label'] for r in rr)) for s,rr in groups.items()},
        'cross_split_waveform_duplicates':0,'cross_split_noise_source_overlap':0,'frozen_test_files':len(frozen),
        'training_policy':'From scratch, seed 23456, max 30 epochs, selection only by validation loss',
        'comparison_scope':'Full Wabun 65 classes; original m4_300 train/validation/test; no real recordings'}
    write_json(ROOT/'reports/data_audit.json',result)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
