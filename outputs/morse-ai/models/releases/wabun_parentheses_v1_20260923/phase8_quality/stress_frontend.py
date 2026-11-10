"""Locked stress diagnostic: no tuning, no production model changes."""
from pathlib import Path
import sys,json,csv
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parent;P=ROOT.parent
sys.path.insert(0,str(P));sys.path.insert(0,str(ROOT))
import evaluate_new as runner
from analyze_saved_errors import read,write,sha
from run_frontend_experiment import infer_variants,result,summary
from noise_preparation import mix_at_snr
from morse_table import MORSE_TABLE
from mixed_morse import INTERNATIONAL_REVERSE
from evaluation_compare import SCHEMA,load_bundle,distance,paired
from warning_localization import audit,summarize

OUT=ROOT/'frontend_stress_v1'
TEXTS=[('kana','スセソ','スセソ'),('latin','サ（ヘイ）シ','サEAシ'),('digits','タ（56）テ','タ56テ')]
PROFILES=['stable','drift30','drift100','wobble60','jitter30','control_notch','control_spike','combined']

def synth(signal,dot,profile,seed):
    sr=16000;rng=np.random.default_rng(seed);parts=[];expected=[];cursor=0;inside=False;tones=[];faults=[]
    def silence(n):
        nonlocal cursor
        parts.append(np.zeros(n,dtype=np.float64));cursor+=n
    for char in signal:
        pad=round(dot*1.5*sr);silence(pad);start=cursor;code=MORSE_TABLE[char]
        for i,symbol in enumerate(code):
            jitter=rng.uniform(.7,1.3) if profile in ('jitter30','combined') else 1
            n=round(dot*sr*(1 if symbol=='.' else 3)*jitter)
            gate=np.ones(n);ramp=min(80,n//2);fade=.5-.5*np.cos(np.linspace(0,np.pi,ramp));gate[:ramp]=fade;gate[-ramp:]=fade[::-1]
            if char in '（）' and symbol=='-' and profile=='control_notch':
                width=min(round(.03*sr),n//3);a=(n-width)//2;gate[a:a+width]=0;faults.append(dict(kind='notch',start_sample=cursor+a,end_sample=cursor+a+width))
            parts.append(gate);tones.append((cursor,cursor+n));cursor+=n
            if i<len(code)-1:
                gap=round(dot*sr*(rng.uniform(.7,1.3) if profile in ('jitter30','combined') else 1))
                if char in '（）' and profile=='control_spike' and i==0:
                    gate=np.zeros(gap);width=min(round(.025*sr),gap//2);a=(gap-width)//2;gate[a:a+width]=1
                    parts.append(gate);faults.append(dict(kind='spike',start_sample=cursor+a,end_sample=cursor+a+width));cursor+=gap
                else:silence(gap)
        expected.append(dict(start_sample=start,end_sample=cursor,label=char,pattern=code,mode='international' if inside else 'wabun'))
        if char in '（）':inside=char=='（'
        silence(pad)
    envelope=np.concatenate(parts);t=np.arange(len(envelope))/sr;duration=len(envelope)/sr
    if profile in ('drift30','drift100'):spread=30 if profile=='drift30' else 100;frequency=700+spread*(2*t/duration-1)
    elif profile in ('wobble60','combined'):frequency=700+60*np.sin(2*np.pi*.7*t)
    else:frequency=np.full(len(t),700.)
    phase=2*np.pi*np.cumsum(frequency)/sr
    audio=.7*envelope*np.sin(phase)
    return audio.astype(np.float32),expected,dict(faults=faults,frequency_min=float(min(frequency)),frequency_max=float(max(frequency)),duration_seconds=duration)

def main():
    OUT.mkdir(exist_ok=False);runner.verify_frozen()
    old=read(ROOT/'frontend_experiment_v1/plan.json')
    for p,h in old['scripts'].items():assert sha(P/p)==h
    plan=dict(scope='SYNTHETIC_STRESS_NOT_REAL_RECORDING_OR_INDEPENDENT_TEST',texts=TEXTS,profiles=PROFILES,dots=[.08,.16],seeds=[41,73],
        noise=['clean','gaussian_0dB'],methods=['baseline','segment_v1','segment_mode_v1'],conditions=192,
        parameters='drift endpoints 700 +/-30 or100 Hz; wobble +/-60Hz at0.7Hz; independent mark/gap jitter +/-30%; control dash notch30ms; control first intra-gap spike25ms',
        interpretation='fault injection diagnoses robustness, not natural recording prevalence; Gaussian is not an unseen noise category; same text/seed under two noises are paired',
        selection='No selection or tuning. Retain frozen candidate and deployed baseline.',
        scripts={str(p.relative_to(P)):sha(p) for p in [Path(__file__),ROOT/'experimental_frontend.py',ROOT/'run_frontend_experiment.py',ROOT/'warning_localization.py']},
        previous_result_hashes={str(p.relative_to(P)):sha(p) for p in [ROOT/'noise_expanded/results.json',ROOT/'frontend_experiment_v1/development/results.json',ROOT/'frontend_experiment_v1/held/results.json']})
    # Check references against the explicitly prescribed send codes, before inference.
    for _,signal,reference in TEXTS:
        rendered='';inside=False
        for c in signal:
            if c in '（）':inside=c=='（';continue
            rendered+=INTERNATIONAL_REVERSE[MORSE_TABLE[c]] if inside else c
        assert rendered==reference
    write(OUT/'plan.json',plan)
    models,cfg,labels=runner.load_models();rows=[];positions=[];counter=0
    for text_id,signal,reference in TEXTS:
        for dot in plan['dots']:
            for profile in PROFILES:
                for seed in plan['seeds']:
                    clean,expected,meta=synth(signal,dot,profile,seed)
                    for noise in plan['noise']:
                        ident=f'{text_id}_d{round(dot*1000)}_{profile}_seed{seed}_{noise}';folder=OUT/ident;folder.mkdir()
                        if noise=='clean':audio=clean;mix={}
                        else:audio,mix=mix_at_snr(clean,np.random.default_rng(seed+1000).normal(0,.1,len(clean)),0)
                        sf.write(folder/'input.wav',audio,16000,subtype='FLOAT');h=sha(folder/'input.wav')
                        write(folder/'input.json',dict(reference=reference,signal=signal,sha256=h,expected=expected,**meta,mix=mix))
                        outputs=infer_variants(runner.load_audio(folder/'input.wav'),models,cfg,labels,plan['methods'])
                        condition=dict(noise=noise,snr_db=None if noise=='clean' else 0,dot_seconds=dot,text_id=text_id,frequency_hz=700,profile=profile,seed=seed)
                        for (method,model),data in outputs.items():
                            row,detail=result(ident,model,method,reference,data,h,condition,expected);rows.append(row);write(folder/(method+'_'+model+'.json'),detail)
                            positions.extend(dict(method=method,model=model,profile=profile,**p) for p in audit(reference,data[0],data[1]))
                        counter+=1
                        if counter%24==0:print(f'{counter}/192',flush=True)
    assert counter==192 and len(rows)==2304
    write(OUT/'results.json',rows);write(OUT/'summary.json',summary(rows))
    groups=[]
    for profile in PROFILES:
        groups.extend(dict(profile=profile,**s) for s in summary([r for r in rows if r['profile']==profile]))
    write(OUT/'profile_summary.json',groups)
    write(OUT/'position_summary.json',[dict(method=method,model=model,**summarize([r for r in positions if (r['method'],r['model'])==(method,model)])) for method in plan['methods'] for model in models])
    bundle_dir=OUT/'comparisons';bundle_dir.mkdir()
    for method in plan['methods']:
        for model in models:
            bundle=dict(schema=SCHEMA,name=f'stress_{method}_{model}',scoring_policy='phase8-content-v2-normalized-codepoints',scope='synthetic-noise-diagnostic',
                model_sha256=sha(P/f'phase6_wabun65/runs/{model.lower()}_wabun65_20260922/best.pt'),rows=[r for r in rows if (r['method'],r['model'])==(method,model)])
            raw=json.dumps(bundle,ensure_ascii=False);load_bundle(raw.encode());(bundle_dir/f'stress_{method}_{model}_comparison.json').write_text(raw,encoding='utf-8')
    # Independent distance calculation; also check written WAV bytes.
    for r in rows:assert distance(r['reference'],r['hypothesis'])==r['edits']
    for folder in OUT.iterdir():
        if (folder/'input.json').is_file():assert sha(folder/'input.wav')==read(folder/'input.json')['sha256']
    for p,h in {**plan['scripts'],**plan['previous_result_hashes']}.items():assert sha(P/p)==h
    runner.verify_frozen();write(OUT/'verification.json',dict(completed=True,rows=2304,inputs=192,independent_scores_pass=True,frozen_and_previous_hashes_pass=True))
    print('PASS: stress completed',flush=True)

if __name__=='__main__':main()
