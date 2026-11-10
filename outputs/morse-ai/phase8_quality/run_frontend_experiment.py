"""Development on old conditions, then locked unused-condition synthetic check."""
from pathlib import Path
import argparse,json,sys,copy
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parent;P=ROOT.parent
sys.path.insert(0,str(P));sys.path.insert(0,str(ROOT))
import evaluate_new as runner
from experimental_frontend import segment_candidate,repair_mode
from analyze_saved_errors import read,write,sha,ideal,diagnose,ui_review
from warning_localization import audit,summarize as summarize_positions
from noise_preparation import mix_at_snr
from generate_morse_audio import generate_morse_audio
from morse_segmentation import segment_morse
from morse_table import MORSE_TABLE,REVERSE_TABLE
from evaluate_recording import edit_alignment
from evaluation_compare import SCHEMA,load_bundle

OUT=ROOT/'frontend_experiment_v1'
TEXTS=[('kana','カキクケコ','カキクケコ'),('latin','ナ（イホ）ニ','ナADニ'),('double','ヌ（34）ネ（ヘハ）ノ','ヌ34ネEBノ')]

def result(ident,model,method,ref,data,input_hash,condition,expected):
    text,segments,warnings,failure=data
    metric,alignment=edit_alignment(ref,text)
    diagnostic=diagnose(expected,segments)
    controls=[s['pattern'] for s in segments if s['pattern'] in (MORSE_TABLE['（'],MORSE_TABLE['）'])]
    wanted=[s['pattern'] for s in expected if s['label'] in '（）']
    row=dict(id=ident,model=model,method=method,input_sha256=input_hash,reference=ref,hypothesis=text,
             reference_units=metric['reference_units'],edits=metric['edit_distance'],status='FAILED' if failure else 'OK',error=failure,
             baseline_alert=bool(warnings or any(s['review_reason'] for s in segments) or failure),
             ui_alert=bool(warnings or any(ui_review(s) for s in segments) or failure),
             mode_sequence_mismatch=controls!=wanted,mode_repairs=sum('observed_pattern' in s for s in segments),**condition,**diagnostic)
    return row,dict(text=text,segments=segments,warnings=warnings,alignment=alignment,metric=row)

def infer_variants(audio,models,cfg,labels,methods):
    outputs={}
    for method in methods:
        if method=='segment_mode_v1':
            for name in models:
                base=outputs[('segment_v1',name)]
                outputs[(method,name)]=(*repair_mode(base[1]),'') if not base[3] else base
            continue
        try:
            body,detector=(segment_morse(audio) if method=='baseline' else segment_candidate(audio))
            for i,s in enumerate(body):s.update(index=i,rule_prediction=REVERSE_TABLE.get(s['pattern'],'?'))
            error=''
        except (ValueError,RuntimeError) as exc:body=[];error=str(exc)
        for name,model in models.items():
            if error:outputs[(method,name)]=('',[],[],error);continue
            try:outputs[(method,name)]=(*runner.infer(body,audio,model,cfg,labels),'')
            except (ValueError,RuntimeError) as exc:outputs[(method,name)]=('',[],[],str(exc))
    return outputs

def summary(rows):
    values=[]
    for method in dict.fromkeys(r['method'] for r in rows):
        for model in ('M1','M2','M3','M4'):
            rs=[r for r in rows if (r['method'],r['model'])==(method,model)];units=sum(r['reference_units'] for r in rs)
            values.append(dict(method=method,model=model,cases=len(rs),units=units,edits=sum(r['edits'] for r in rs),
                cer=sum(r['edits'] for r in rs)/units,failures=sum(r['status']=='FAILED' for r in rs),
                exact=sum(not r['edits'] and r['status']!='FAILED' for r in rs),mode_mismatches=sum(r['mode_sequence_mismatch'] for r in rs),
                repairs=sum(r['mode_repairs'] for r in rs),boundary_cases=sum(any(r[k] for k in ('missing','split','merged','extra')) for r in rs)))
    return values

def save(stage,rows,position_rows):
    directory=OUT/stage;write(directory/'results.json',rows);stats=summary(rows);write(directory/'summary.json',stats)
    write(directory/'position_summary.json',[dict(method=method,model=model,**summarize_positions([r for r in position_rows if (r['method'],r['model'])==(method,model)]))
        for method in dict.fromkeys(r['method'] for r in rows) for model in ('M1','M2','M3','M4')])
    for s in stats:
        name=f"{stage}_{s['method']}_{s['model']}"
        bundle=dict(schema=SCHEMA,name=name,scoring_policy='phase8-content-v2-normalized-codepoints',scope='synthetic-noise-diagnostic',
            model_sha256=sha(P/f"phase6_wabun65/runs/{s['model'].lower()}_wabun65_20260922/best.pt"),
            rows=[r for r in rows if (r['method'],r['model'])==(s['method'],s['model'])])
        raw=json.dumps(bundle,ensure_ascii=False);load_bundle(raw.encode());(directory/(name+'_comparison.json')).write_text(raw,encoding='utf-8')
    return stats

def main(stage):
    runner.verify_frozen()
    if stage=='development':
        OUT.mkdir(exist_ok=False)
        scripts=[Path(__file__),ROOT/'experimental_frontend.py',ROOT/'warning_localization.py',ROOT/'noise_preparation.py']
        write(OUT/'plan.json',dict(scope='SYNTHETIC_DEVELOPMENT_AND_UNUSED_CONDITIONS_NOT_REAL_RECORDING_ACCEPTANCE',
            development='existing noise_expanded 366 conditions; now development, previous reported values preserved',
            methods=['baseline','segment_v1','segment_mode_v1'],parameters='See hashed experimental_frontend.py; no reference input',
            held_texts=TEXTS,dots=[.06,.12],frequencies=[500,1100],noise_offsets=[60,250],snr_db=[10,0,-5],
            noises=['OOFFICE','DKITCHEN','STRAFFIC'],conditions=228,
            selection='lowest pooled development edits among experimental methods; ties prefer segment_v1; no retuning after held validation',
            adoption='experiment only, keep production baseline regardless of outcome',
            scripts={str(p.relative_to(P)):sha(p) for p in scripts},
            source_sha256={n:sha(ROOT/'external_noise/DEMAND'/f'{n}_ch01.wav') for n in ('OOFFICE','DKITCHEN','STRAFFIC')},
            previous_results_sha256=sha(ROOT/'noise_expanded/results.json')))
    plan=read(OUT/'plan.json')
    for p,h in plan['scripts'].items():assert sha(P/p)==h,p
    directory=OUT/stage;directory.mkdir(exist_ok=False)
    models,cfg,labels=runner.load_models();rows=[];positions=[]
    if stage=='development':
        old=read(ROOT/'noise_expanded/results.json');by_id={r['id']:r for r in old}
        from analyze_saved_errors import SIGNALS
        for index,(ident,m) in enumerate(by_id.items()):
            folder=ROOT/'noise_expanded'/ident;meta=read(folder/'input.json');audio=runner.load_audio(folder/'input.wav')
            outputs=infer_variants(audio,models,cfg,labels,['segment_v1','segment_mode_v1'])
            for name in models:
                d=read(folder/(name+'.json'));outputs[('baseline',name)]=(d['text'],d['segments'],d['warnings'],d['metric']['error'])
            condition={k:m[k] for k in ('noise','snr_db','dot_seconds','text_id','offset_seconds')};condition['frequency_hz']=700
            expected=ideal(SIGNALS[m['text_id']],m['dot_seconds']);dest=directory/ident;dest.mkdir()
            for (method,model),data in outputs.items():
                row,detail=result(ident,model,method,meta['reference'],data,meta['sha256'],condition,expected)
                rows.append(row);write(dest/(method+'_'+model+'.json'),detail)
                positions.extend(dict(model=model,method=method,**p) for p in audit(meta['reference'],data[0],data[1]))
            if index%40==0:print(f'development {index+1}/366',flush=True)
        stats=save(stage,rows,positions)
        totals={method:sum(s['edits'] for s in stats if s['method']==method) for method in plan['methods']}
        selected=min(['segment_v1','segment_mode_v1'],key=lambda method:totals[method])
        write(OUT/'selection_lock.json',dict(selected=selected,development_edits=totals,plan_sha256=sha(OUT/'plan.json'),results_sha256=sha(directory/'results.json')))
    else:
        lock=read(OUT/'selection_lock.json');assert lock['plan_sha256']==sha(OUT/'plan.json');assert lock['results_sha256']==sha(OUT/'development/results.json')
        selected=lock['selected'];noises={}
        for n,h in plan['source_sha256'].items():
            path=ROOT/'external_noise/DEMAND'/f'{n}_ch01.wav';assert sha(path)==h;noises[n]=sf.read(path,dtype='float64')[0]
        previous=[]
        for m in read(ROOT/'noise_expanded/results.json'):
            if m['noise'] in noises:
                duration=sf.info(ROOT/'noise_expanded'/m['id']/'input.wav').duration
                previous.append((m['noise'],m['offset_seconds'],m['offset_seconds']+duration))
        counter=0
        for text_id,signal,ref in plan['held_texts']:
            for dot in plan['dots']:
                for frequency in plan['frequencies']:
                    clean=np.concatenate([generate_morse_audio(c,dot,frequency,.7,padding=1.5*dot) for c in signal])
                    cases=[('clean',None,None)]+[(n,o,s) for n in noises for o in plan['noise_offsets'] for s in plan['snr_db']]
                    for noise,offset,snr in cases:
                        ident=f'{text_id}_d{round(dot*1000)}_f{frequency}_{noise}_o{offset}_s{snr}';folder=directory/ident;folder.mkdir()
                        if noise=='clean':audio=clean;mix={}
                        else:
                            end=offset+len(clean)/16000
                            assert all(n!=noise or end<=start or offset>=stop for n,start,stop in previous),'Noise excerpt overlaps development'
                            assert end<=len(noises[noise])/16000
                            audio,mix=mix_at_snr(clean,noises[noise],snr,offset=round(offset*16000))
                        sf.write(folder/'input.wav',audio,16000,subtype='FLOAT');h=sha(folder/'input.wav')
                        write(folder/'input.json',dict(reference=ref,signal=signal,sha256=h,mix=mix))
                        audio=runner.load_audio(folder/'input.wav')
                        methods=['baseline','segment_v1']+(['segment_mode_v1'] if selected=='segment_mode_v1' else [])
                        outputs=infer_variants(audio,models,cfg,labels,methods)
                        condition=dict(noise=noise,offset_seconds=offset,snr_db=snr,dot_seconds=dot,text_id=text_id,frequency_hz=frequency)
                        for (method,model),data in outputs.items():
                            if method not in ('baseline',selected):continue
                            row,detail=result(ident,model,method,ref,data,h,condition,ideal(signal,dot));rows.append(row)
                            write(folder/(method+'_'+model+'.json'),detail)
                            positions.extend(dict(model=model,method=method,**p) for p in audit(ref,data[0],data[1]))
                        counter+=1
                        if counter%30==0:print(f'held {counter}/228',flush=True)
        assert counter==228;save(stage,rows,positions)
    runner.verify_frozen()
    for p,h in plan['scripts'].items():assert sha(P/p)==h
    assert sha(ROOT/'noise_expanded/results.json')==plan['previous_results_sha256']
    write(directory/'verification.json',dict(completed=True,frozen_hashes_match=True,rows=len(rows),source_results_unchanged=True,plan_sha256=sha(OUT/'plan.json')))
    print(stage+' complete',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['development','held']);main(parser.parse_args().stage)
