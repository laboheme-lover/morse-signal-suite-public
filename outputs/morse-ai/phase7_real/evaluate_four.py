"""Additional four recordings: explicit protocol boundary extension, fixed models."""
from evaluate import *
import re,unicodedata
from evaluate_real_collection import prepare_reference
from evaluate_recording import canonical_reference
from morse_segmentation import segment_morse
from morse_table import MORSE_TABLE
from mixed_morse import INTERNATIONAL_REVERSE

ITU='https://www.itu.int/dms_pubrec/itu-r/rec/m/R-REC-M.1677-1-200910-I%21%21PDF-E.pdf'

def select_extended(rows):
    starts=[i for i,r in enumerate(rows) if r['pattern']=='-..---']
    ends=[i for i,r in enumerate(rows) if r['pattern']=='...-.']
    if len(starts)==len(ends)==1 and starts[0]<ends[0]:
        return rows[starts[0]+1:ends[0]],{'method':'existing_HORE_RATA','start_index':starts[0],'end_index':ends[0]}
    # Position and code pattern only: no reference text or CNN predictions used.
    if len(rows)>6 and [r['pattern'] for r in rows[:5]]==['....','.-.','....','.-.','-...-'] and rows[-1]['pattern']=='.-.-.':
        return rows[5:-1],{'method':'HR_HR_BT_prefix_and_terminal_AR','start_index':4,'end_index':len(rows)-1}
    raise ValueError('No accepted protocol framing; do not infer a crop from reference text')

def reference_allow_latin(text):
    text=unicodedata.normalize('NFKC',text)
    text=re.sub(r'^\s*HR\s+HR\s*','',text)
    text=re.sub(r'<(?:ホレ|ラタ)>','',text)
    text=text.translate(str.maketrans('','','★?「」'))
    return ''.join(c.upper() if c.isascii() and c.isalpha() else canonical_reference(c) for c in text)

def decode_drop_controls(rows):
    cnn=[];rule=[];inside=False
    for r in rows:
        pattern=r['pattern']
        if pattern==MORSE_TABLE['（']:
            if inside:raise ValueError('Nested mode')
            inside=True
        elif pattern==MORSE_TABLE['）']:
            if not inside:raise ValueError('Unmatched mode close')
            inside=False
        elif inside:
            cnn.append(INTERNATIONAL_REVERSE.get(MORSE_TABLE.get(r['prediction'],'?'),'?'))
            rule.append(INTERNATIONAL_REVERSE.get(pattern,'?'))
        elif r['rule_prediction'] not in '、」':
            cnn.append(r['prediction']);rule.append(r['rule_prediction'])
    if inside:raise ValueError('Unclosed mode')
    return ''.join(cnn),''.join(rule)

def main():
    out=ROOT/'additional_four';out.mkdir(exist_ok=False)
    models={};protected={};configs=[]
    for name,cls in MODELS.items():
        run=PROJECT/f'phase6_wabun65/runs/{name.lower()}_wabun65_20260922'
        ck=torch.load(run/'best.pt',map_location='cpu',weights_only=True)
        assert sha(run/'best.pt')==json.loads((run/'training_complete.json').read_text())['checkpoint_sha256']
        protected[str(run/'best.pt')]=sha(run/'best.pt')
        model=cls(ck['config']).eval();model.load_state_dict(ck['state_dict']);models[name]=model
        configs.append(ck['config'])
        current_labels=sorted(ck['labels'],key=ck['labels'].get)
        if len(configs)>1:assert labels==current_labels
        labels=current_labels
    cfg=configs[0];setup(cfg)
    assert all(c['preprocessing']==cfg['preprocessing'] for c in configs)
    frozen=verify_lock(PROJECT/'phase1_data')
    write_json(out/'protocol.json',{'numbers':[57,62,64,67],'models':'Frozen phase6 Wabun65 M1-M4',
        'framing':'Unique HORE/RATA; else exact leading HR HR BT and terminal AR, independent of reference and CNN',
        'standard_source':ITU,'standard_sections':'Part I 1.1.3 and Part II 3, 5',
        'reference':'Old normalization for 57/64/67. For 62 allow ASCII letters and uppercase them without adding brackets.',
        'official_mode':'content_without_mode_brackets',
        'user_confirmed_convention':'Parentheses are international-mode controls, absent from manuscript text.',
        'main_score':'Body CER excluding observed mode-control bracket segments; no reference bracket insertion.',
        'supplementary_score':'Retained-bracket values are diagnostic only; not official recognition errors.',
        'legacy_comparable':False,'merge_with_old40':False,'audio_segmentation':'Rerun unchanged original detector and verify against saved boundaries',
        'training':False,'carrier_translation':False,'tuning':False})
    results=[];boundary_records=[]
    for number in (57,62,64,67):
        old=PROJECT/f'evaluation/real_collection_baseline/{number:03d}'
        meta=json.loads((old/'recording_metrics.json').read_text(encoding='utf-8'))
        audio_path=Path(meta['audio_path']);assert sha(audio_path)==meta['audio_sha256']
        raw=(old/'reference_original.txt').read_text(encoding='utf-8')
        ref=reference_allow_latin(raw) if number==62 else prepare_reference(raw)
        rows=read_csv(old/'segments.csv')
        body,boundary=select_extended(rows)
        audio=load_audio(audio_path)
        detected,detector=segment_morse(audio)
        assert len(detected)==len(rows)
        assert all(all(str(new[k])==str(saved[k]) for k in ('start_sample','end_sample','pattern')) for new,saved in zip(detected,rows)), 'Boundary redetection differs'
        boundary.update(number=number,start_pattern=rows[boundary['start_index']]['pattern'],end_pattern=rows[boundary['end_index']]['pattern'],
            body_first_index=body[0]['index'],body_last_index=body[-1]['index'],body_start_seconds=body[0]['start_seconds'],
            body_end_seconds=body[-1]['end_seconds'],segments=len(body),original_segments=len(rows),redetection_matches=True)
        boundary_records.append(boundary)
        folder=out/f'{number:03d}';folder.mkdir()
        (folder/'reference_original.txt').write_text(raw,encoding='utf-8')
        (folder/'reference_normalized.txt').write_text(ref,encoding='utf-8')
        write_json(folder/'boundaries.json',boundary)
        write_json(folder/'mode_controls.json',[{k:r[k] for k in ('index','start_seconds','end_seconds','pattern')} for r in body if r['pattern'] in (MORSE_TABLE['（'],MORSE_TABLE['）'])])
        items=[]
        for i,row in enumerate(body):
            seg={k:int(row[k]) for k in ('start_sample','end_sample')}
            items.append((envelope(extract_character(audio,seg),16000,cfg),0,i))
        loader=torch.utils.data.DataLoader(items,batch_size=128,collate_fn=collate)
        for name,model in models.items():
            predictions=copy.deepcopy(body)
            with torch.inference_mode():
                for x,lengths,_,ids in loader:
                    probabilities=model(x,lengths).softmax(-1);values,classes=probabilities.max(-1)
                    for idx,cls,prob in zip(ids.tolist(),classes.tolist(),values.tolist()):
                        predictions[idx]['prediction']=labels[cls];predictions[idx]['confidence']=prob
            main_text,rule=decode_mixed(predictions)
            content_text,content_rule=decode_drop_controls(predictions)
            for mode,text in [('body_brackets_retained',main_text),('content_without_mode_brackets',content_text)]:
                metric,align=edit_alignment(ref,text)
                metric.update(number=number,model=name,mode=mode)
                results.append(metric)
                (folder/f'{name}_{mode}.txt').write_text(text,encoding='utf-8')
                write_csv(folder/f'{name}_{mode}_alignment.csv',align)
            write_csv(folder/f'{name}_segments.csv',[{k:r[k] for k in ('index','start_seconds','end_seconds','pattern','prediction','confidence','rule_prediction')} for r in predictions])
        for mode,text in [('body_brackets_retained',rule),('content_without_mode_brackets',content_rule)]:
            metric,align=edit_alignment(ref,text);metric.update(number=number,model='Rule',mode=mode);results.append(metric)
            (folder/f'Rule_{mode}.txt').write_text(text,encoding='utf-8');write_csv(folder/f'Rule_{mode}_alignment.csv',align)
        for p in (audio_path,old/'segments.csv',old/'reference_original.txt',old/'recording_metrics.json'):
            protected[str(p)]=sha(p)
        print(f'{number}: '+', '.join(f'{r["model"]} {r["mode"]}: {r["edit_distance"]}/{r["reference_units"]}' for r in results if r['number']==number),flush=True)
    write_csv(out/'recording_results.csv',results);write_json(out/'recording_results.json',results)
    write_csv(out/'boundaries.csv',boundary_records)
    summary=[]
    for name in list(models)+['Rule']:
        for mode in ('body_brackets_retained','content_without_mode_brackets'):
            rows=[r for r in results if r['model']==name and r['mode']==mode]
            n=sum(r['reference_units'] for r in rows);d=sum(r['edit_distance'] for r in rows)
            summary.append({'model':name,'mode':mode,'reference_units':n,'edit_distance':d,'cer':d/n,
                **{k:sum(r[k] for r in rows) for k in ('substitutions','insertions','deletions')}})
    write_csv(out/'summary.csv',summary);write_json(out/'summary.json',summary)
    for r in results:
        folder=out/f'{r["number"]:03d}'
        computed,_=edit_alignment((folder/'reference_normalized.txt').read_text(encoding='utf-8'),(folder/f'{r["model"]}_{r["mode"]}.txt').read_text(encoding='utf-8'))
        assert all(computed[k]==r[k] for k in computed)
    assert all(sha(p)==h for p,h in protected.items())
    assert len(verify_lock(PROJECT/'phase1_data'))==len(frozen)
    write_json(out/'verification.json',{'status':'PASS','all_four_audio_boundaries_redetected':True,'protected_hashes':protected,
        'all_40_scores_recomputed':True,'frozen_test_files_unchanged':len(frozen),'reference_brackets_added':False,'legacy40_modified':False})

if __name__=='__main__':main()
