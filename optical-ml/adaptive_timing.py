"""Experimental timing frontend, separate from frozen baseline inference.

No reference labels, augmentation parameters, or classifier confidence are used
to choose a period. A single stable dot period is assumed per recording.
"""
import numpy as np
from predict import classify_features, splitter

def estimate_unit(times, features):
    times=np.asarray(times);features=np.asarray(features)
    if len(times)<10 or features.shape!=(len(times),4):
        raise ValueError('周期推定に必要な時系列が不足しています。')
    if not np.isfinite(times).all() or not np.isfinite(features).all() or np.any(np.diff(times)<=0):
        raise ValueError('時刻または輝度が不正です。')
    dt=float(np.median(np.diff(times)))
    signal=features[:,0]-features[:,2]
    low,high=np.percentile(signal,[5,95])
    if high-low<5:low,high=np.percentile(signal,[1,99])
    if high-low<5:raise ValueError('光の変化が小さく、周期推定を保留します。')
    for _ in range(15):
        threshold=(low+high)/2
        a=signal[signal<=threshold];b=signal[signal>threshold]
        if min(len(a),len(b))<2:raise ValueError('点灯と消灯を分離できません。')
        low,high=np.median(a),np.median(b)
    runs=splitter.runs(signal>(low+high)/2,times,dt)
    # Edge darkness may be recording margins, not transmitted Morse intervals.
    on=np.array([r['end']-r['start'] for r in runs if r['on']])
    off=np.array([r['end']-r['start'] for r in runs[1:-1] if not r['on']])
    if len(on)<6 or len(off)<5:raise ValueError('周期を確定するだけの点滅数がありません。')
    candidates=np.arange(max(.1,2.5*dt),1.0001,.001)
    if not len(candidates):raise ValueError('フレーム間隔が長すぎます。')
    losses=[]
    for u in candidates:
        a=np.min(abs(on[:,None]/u-np.array([1.,3.])),axis=1)
        b=np.min(abs(off[:,None]/u-np.array([1.,3.,7.])),axis=1)
        # Clip large outliers, but retain all observations when scoring.
        losses.append(float((np.minimum(a,2).mean()+np.minimum(b,2).mean())/2))
    index=int(np.argmin(losses));unit=float(candidates[index]);loss=float(losses[index])
    a=np.min(abs(on[:,None]/unit-np.array([1.,3.])),axis=1)
    b=np.min(abs(off[:,None]/unit-np.array([1.,3.,7.])),axis=1)
    tolerance=max(.3,2*dt/unit)
    fit=float(np.mean(np.r_[a,b]<=tolerance))
    on_dot=int(np.sum(abs(on/unit-1)<=tolerance))
    on_dash=int(np.sum(abs(on/unit-3)<=tolerance))
    off_short=int(np.sum(abs(off/unit-1)<=tolerance))
    alternative=min((v for u,v in zip(candidates,losses) if abs(u-unit)>.2*unit),default=float('inf'))
    if loss>.35 or fit<.8 or (on_dot==0 and off_short==0) or alternative-loss<.08:
        raise ValueError('点滅周期の整合性が不足しています。手動設定または動画確認が必要です。')
    if np.diff(times).max()>unit*.4:raise ValueError('推定した短点に対してフレーム欠落が大きすぎます。')
    return dict(unit_seconds=unit,fit_fraction=fit,mean_unit_residual=loss,
                alternative_loss_margin=float(alternative-loss),on_count=len(on),
                off_count=len(off),dot_support=on_dot,dash_support=on_dash,
                short_gap_support=off_short,assumption='One stable dot duration for the entire clip')

def classify_adaptive(times,features,checkpoint,normalize_input=True):
    timing=estimate_unit(times,features);unit=timing['unit_seconds']
    if normalize_input:
        # Convert observed time into the 300 ms reference clock. This rescales
        # character margins, sample spacing and duration feature together.
        scale=.3/unit
        result=classify_features((np.asarray(times)-times[0])*scale,features,checkpoint,unit=.3,isolated=False)
        for char in result['characters']:
            char['start']=char['start']/scale+float(times[0]);char['end']=char['end']/scale+float(times[0])
    else:
        scale=1.
        result=classify_features(times,features,checkpoint,unit=unit,isolated=False)
    result.update(timing=timing,normalize_input=normalize_input,clock_scale=scale,
                  status='DEVELOPMENT_REVIEW',warning='No.41–50を用いた開発評価用の周期補正。独立評価未実施。')
    return result
