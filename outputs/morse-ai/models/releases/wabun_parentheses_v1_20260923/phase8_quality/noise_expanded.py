"""Predeclared 366-condition diagnostic; fixed models, no tuning/selection."""
from pathlib import Path
import csv,hashlib,json,sys,time
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent
sys.path.insert(0,str(PROJECT));sys.path.insert(0,str(ROOT))
import evaluate_new as runner
from noise_preparation import mix_at_snr
from generate_morse_audio import generate_morse_audio
from morse_table import MORSE_TABLE,REVERSE_TABLE
from morse_segmentation import segment_morse
from evaluate_recording import edit_alignment
from policy import normalize_reference

TEXTS=[('wabun','イロハニホヘト','イロハニホヘト'),('mixed','イ（ヤチツ）ロ','イWFPロ'),('multi_mode','イ（ヤチ）ロ（12）ハ','イWFロ12ハ')]

def digest(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def write(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    out=ROOT/'noise_expanded';out.mkdir(exist_ok=False)
    runner.verify_frozen();noises={};sources={};source_paths={}
    for name in ('OOFFICE','DKITCHEN','STRAFFIC'):
        path=ROOT/'external_noise/DEMAND'/(name+'_ch01.wav');data,sr=sf.read(path,dtype='float64')
        prov=path.parent/('provenance.json' if name=='OOFFICE' else name+'_provenance.json');p=json.loads(prov.read_text(encoding='utf-8'))
        assert sr==16000 and data.ndim==1 and digest(path)==p['selected_sha256']
        noises[name]=data;sources[name]=p;source_paths[str(path)]=digest(path)
    # A previously used noise TYPE, not another field recording or unseen category.
    noises['gaussian_control']=np.random.default_rng(20260922).normal(0,.1,16000*300)
    local_hashes={digest(p) for p in (PROJECT/'data/ESC-50-master/audio').glob('*.wav')}
    assert not set(source_paths.values())&local_hashes
    plan=dict(scope='EXPANDED_DIAGNOSTIC_NOT_INDEPENDENT_REAL_RECORDING_TEST',texts=TEXTS,dots=[.08,.16],frequency_hz=700,
        padding='1.5 dots on each character side; combined gap 3 dots',offset_seconds=[10,100,200],snr_db=[20,10,5,0,-5],
        gaussian_seed=20260922,sources=sources,source_sha256=source_paths,exact_esc50_byte_overlap=False,
        repeated_excerpts_are_not_independent_recordings=True,selection_or_training=False,
        scripts={str(p.relative_to(PROJECT)):digest(p) for p in [Path(__file__),ROOT/'noise_preparation.py']})
    write(out/'plan.json',plan)
    models,cfg,labels=runner.load_models();rows=[];counter=0;start_all=time.perf_counter()
    for text_id,signal,ref in TEXTS:
        ref=normalize_reference(ref)
        expected_modes=[MORSE_TABLE[c] for c in signal if c in '（）']
        for dot in plan['dots']:
            clean=np.concatenate([generate_morse_audio(c,dot,700,.7,padding=1.5*dot) for c in signal])
            cases=[('clean',None,None)]+[(n,o,s) for n in noises for o in plan['offset_seconds'] for s in plan['snr_db']]
            for noise,offset,snr in cases:
                ident=f'{text_id}_d{round(dot*1000)}_{noise}_o{offset}_s{snr}';folder=out/ident;folder.mkdir()
                if noise=='clean':audio=clean;mix={'condition':'clean'}
                else:audio,mix=mix_at_snr(clean,noises[noise],snr,offset=round(offset*16000))
                path=folder/'input.wav';sf.write(path,audio,16000,subtype='FLOAT')
                write(folder/'input.json',dict(id=ident,reference=ref,mix=mix,sha256=digest(path),expected_mode_patterns=expected_modes))
                error='';body=[];mode_sequence=[]
                try:
                    loaded=runner.load_audio(path);body,detector=segment_morse(loaded)
                    for i,r in enumerate(body):r.update(index=i,rule_prediction=REVERSE_TABLE.get(r['pattern'],'?'))
                    mode_sequence=[r['pattern'] for r in body if r['pattern'] in (MORSE_TABLE['（'],MORSE_TABLE['）'])]
                    write(folder/'detected.json',dict(segments=body,detector=detector))
                except (ValueError,OSError,RuntimeError) as exc:error=str(exc)
                for name,model in models.items():
                    failure=error;text='';segments=[];warnings=[]
                    if not failure:
                        try:text,segments,warnings=runner.infer(body,loaded,model,cfg,labels)
                        except (ValueError,OSError,RuntimeError) as exc:failure=str(exc)
                    metric,alignment=edit_alignment(ref,text)
                    row=dict(id=ident,text_id=text_id,dot_seconds=dot,noise=noise,offset_seconds=offset,snr_db=snr,model=name,
                        **metric,status='FAILED' if failure else 'OK',error=failure,exact=int(text==ref and not failure),
                        review_segments=sum(bool(r['review_reason']) or r['text_prediction']=='□' for r in segments),
                        warning_count=len(warnings),mode_pattern_sequence_mismatch=mode_sequence!=expected_modes)
                    row['silent_error']=bool(metric['edit_distance'] and not failure and not warnings and not row['review_segments'])
                    rows.append(row);write(folder/(name+'.json'),dict(metric=row,text=text,segments=segments,warnings=warnings,alignment=alignment))
                counter+=1
                if counter%20==0:print(f'{counter}/366 conditions',flush=True)
    runner.verify_frozen()
    for path,h in source_paths.items():assert digest(path)==h
    for path,h in plan['scripts'].items():assert digest(PROJECT/path)==h
    assert counter==366 and len(rows)==1464
    write(out/'results.json',rows)
    with (out/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summaries=[]
    for noise in ['clean',*noises]:
        for snr in ([None] if noise=='clean' else plan['snr_db']):
            for name in models:
                subset=[r for r in rows if (r['noise'],r['snr_db'],r['model'])==(noise,snr,name)]
                units=sum(r['reference_units'] for r in subset);edits=sum(r['edit_distance'] for r in subset)
                summaries.append(dict(noise=noise,snr_db=snr,model=name,cases=len(subset),reference_units=units,edits=edits,cer=edits/units,
                    exact=sum(r['exact'] for r in subset),failures=sum(r['status']=='FAILED' for r in subset),silent_errors=sum(r['silent_error'] for r in subset),
                    mode_pattern_mismatches=sum(r['mode_pattern_sequence_mismatch'] for r in subset)))
    write(out/'summary.json',summaries)
    lines=['# ノイズ予備診断の拡充','', '合成3文（和文、和欧混在、複数切替）×短点80/160 ms。DEMAND 3環境のch01、各10/100/200秒から切り出し、SNR20/10/5/0/−5 dB。ガウス雑音を対照とし、各文・速度の無雑音も評価。',
        '366条件×4モデル＝1464推論。過去の開発と独立した実録音テストではなく、採用・学習・調整には使用していない。3区間は同じ録音由来なので独立録音3本とは数えない。',
        'CERは本文抽出・区間検出・モード処理を含む。失敗は全削除。音量は共通ゲインでピークを抑え、全文区間のRMSでSNRを定義。未知カテゴリとは主張しない。','',
        '|環境|SNR|M1 CER|M2 CER|M3 CER|M4 CER|','|---|---:|---:|---:|---:|---:|']
    for noise in ['clean',*noises]:
        for snr in ([None] if noise=='clean' else plan['snr_db']):
            subset=[r for r in summaries if (r['noise'],r['snr_db'])==(noise,snr)]
            lines.append('|'+noise+'|'+str(snr if snr is not None else '—')+'|'+'|'.join(f"{r['cer']:.2%}" for r in subset)+'|')
    lines+=['','モード指標は観測された開閉符号列の一致であり、時刻精度やCNNによるモード解釈の正しさを保証しない。詳細な条件別・警告なし誤り・失敗はresults.csvとsummary.jsonに保存。',
        '出典：[DEMAND公式配布記録](https://zenodo.org/records/1227121)。作者・利用条件・ハッシュはplan.jsonに保存。3環境・3文章に限定され、実録音の汎化性能やモデル採用の根拠には不足する。']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write(out/'verification.json',dict(completed=True,conditions=counter,model_cases=len(rows),elapsed_seconds=time.perf_counter()-start_all,models_and_sources_unchanged=True))
    print('Expanded diagnostic complete',flush=True)

if __name__=='__main__':main()
