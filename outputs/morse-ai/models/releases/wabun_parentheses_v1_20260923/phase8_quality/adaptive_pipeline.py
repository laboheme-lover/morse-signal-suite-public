"""Experimental frequency tracking and envelope-time normalization for M1--M4."""
from pathlib import Path
import sys,copy
import numpy as np
import torch
from scipy.signal import butter,sosfiltfilt,welch,stft,hilbert
from scipy.ndimage import median_filter
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent))
import evaluate_new as runner
from morse_segmentation import segment_morse,extract_character
from timing_frontend import segment_timing
from experimental_frontend import repair_mode
from morse_table import REVERSE_TABLE
from policy import render_body

METHODS=['baseline','timing','tracking','tempo','combined','combined_mode']
LABELS=dict(baseline='従来処理',timing='短点推定',tracking='短点推定＋音程追従',tempo='短点推定＋速度補正',
            combined='短点推定＋音程追従＋速度補正',combined_mode='統合実験版（切替補正付き）')

def track_carrier(audio,sr=16000):
    x=np.asarray(audio,dtype=float)
    if x.ndim!=1 or len(x)<sr//2 or not np.isfinite(x).all():raise ValueError('Invalid mono audio')
    freq,p=welch(x,sr,nperseg=min(len(x),16384));band=(freq>=300)&(freq<=1500)
    anchor=float(freq[band][np.argmax(p[band])])
    f,t,z=stft(x,fs=sr,nperseg=1024,noverlap=896,boundary='zeros',padded=True)
    band=(f>=max(200,anchor-220))&(f<=min(1700,anchor+220));power=abs(z[band])**2
    peak=power.argmax(axis=0);strength=power[peak,np.arange(len(t))]
    if np.quantile(strength,.95)<1e-12:raise ValueError('No trackable carrier')
    active=strength>=max(float(np.quantile(strength,.95))*.15,1e-12)
    if active.sum()<3:raise ValueError('Too few reliable carrier frames')
    # Ridge interpolation across OFF periods; no transcript or true frequency input.
    ridge=f[band][peak];ridge=np.interp(t,t[active],ridge[active]);ridge=median_filter(ridge,size=5,mode='nearest')
    times=np.arange(len(x))/sr;sample_freq=np.interp(times,t,ridge)
    analytic=hilbert(sosfiltfilt(butter(4,[max(100,anchor-270),min(2000,anchor+270)],fs=sr,btype='bandpass',output='sos'),x))
    phase=2*np.pi*np.cumsum(sample_freq)/sr
    baseband=analytic*np.exp(-1j*phase)
    baseband=sosfiltfilt(butter(4,70,fs=sr,output='sos'),baseband)
    translated=np.real(baseband*np.exp(2j*np.pi*700*times)).astype(np.float32)
    meta=dict(anchor_hz=anchor,tracked_min_hz=float(ridge.min()),tracked_max_hz=float(ridge.max()),
              target_hz=700,active_frame_fraction=float(active.mean()),track_seconds=t.tolist(),track_hz=ridge.tolist())
    return translated,meta

def normalize_feature(feature,dot,cfg):
    if not np.isfinite(dot) or not .015<=dot<=.5:raise ValueError('Invalid estimated dot duration')
    scale=.1/dot
    # Preserve fixed training padding; only the signal region changes duration.
    pad=round(.095*1000/cfg['preprocessing']['hop_ms'])
    if feature.shape[0]<=2*pad:raise ValueError('Too few signal frames for time normalization')
    core=feature[pad:-pad];target=max(1,round(len(core)*scale))
    resized=torch.nn.functional.interpolate(core.T.unsqueeze(0),size=target,mode='linear',align_corners=False)[0].T
    return torch.cat((feature[:pad],resized,feature[-pad:]),dim=0),scale

def infer_prepared(body,audio,model,cfg,labels,dot=None):
    rows=copy.deepcopy(body);items=[]
    for i,r in enumerate(rows):
        feature=runner.envelope(extract_character(audio,r),16000,cfg)
        if dot is not None:feature,scale=normalize_feature(feature,dot,cfg);r['feature_time_scale']=scale
        items.append((feature,0,i))
    loader=torch.utils.data.DataLoader(items,batch_size=128,collate_fn=runner.collate)
    with torch.inference_mode():
        for x,lengths,_,ids in loader:
            probs=model(x,lengths).softmax(-1)
            if not torch.isfinite(probs).all():raise ValueError('Non-finite model output')
            values,indices=probs.topk(3,dim=-1)
            for idx,cs,vs in zip(ids.tolist(),indices.tolist(),values.tolist()):
                rows[idx].update(prediction=labels[cs[0]],confidence=vs[0],top_k=[dict(label=labels[c],confidence=v) for c,v in zip(cs,vs)])
    return render_body(rows)

def evaluate(audio,models,cfg,labels,methods=None):
    methods=list(methods or METHODS)
    if not methods or any(m not in METHODS for m in methods):raise ValueError('Unknown experiment method')
    prepared={};outputs={};detectors={}
    for method in methods:
        source='tracking' if method in ('tracking','combined','combined_mode') else ('baseline' if method=='baseline' else 'timing')
        if source not in prepared:
            try:
                track={};wave=audio
                if source=='tracking':wave,track=track_carrier(audio)
                body,meta=(segment_morse(wave) if source=='baseline' else segment_timing(wave))
                for i,r in enumerate(body):r.update(index=i,rule_prediction=REVERSE_TABLE.get(r['pattern'],'?'))
                meta.update(track);prepared[source]=(body,wave,meta,'')
            except (ValueError,RuntimeError) as exc:prepared[source]=([],audio,{},str(exc))
        body,wave,meta,error=prepared[source];detectors[method]=meta
        for name,model in models.items():
            if error:outputs[(method,name)]=('',[],[],error);continue
            try:
                # Share the CNN result when only the final mode policy differs.
                if method=='combined_mode' and ('combined',name) in outputs:
                    previous=outputs[('combined',name)]
                    if previous[3]:outputs[(method,name)]=previous;continue
                    text,segments,warnings=repair_mode(previous[1])
                else:
                    text,segments,warnings=infer_prepared(body,wave,model,cfg,labels,meta['dot_seconds'] if method in ('tempo','combined','combined_mode') else None)
                    if method=='combined_mode':text,segments,warnings=repair_mode(segments)
                if meta.get('timing_ambiguous'):warnings.append('短点推定に複数候補があります。要確認。')
                outputs[(method,name)]=(text,segments,warnings,'')
            except (ValueError,RuntimeError) as exc:outputs[(method,name)]=('',[],[],str(exc))
    return outputs,detectors
