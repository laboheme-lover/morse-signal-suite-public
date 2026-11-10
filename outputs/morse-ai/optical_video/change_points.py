"""Two-level exposure-change evidence; never uses Morse labels/reference text."""
import numpy as np
from optical_video.adaptive import local_thresholds

VERSION='optical-video-v5-ambiguous-warning'

def detect_changes(signal,fps,window_seconds=3.,*,ambiguous_only=False):
    signal=np.asarray(signal,dtype=float);span=float(np.percentile(signal,95)-np.percentile(signal,5))
    w=max(6,round(window_seconds*fps));minimum=max(2.,span*.04)
    candidates=np.flatnonzero(np.abs(np.diff(signal))>=max(5.,span*.08))+1
    found=[]
    for i in candidates:
        left=signal[max(0,i-w):i];right=signal[i:min(len(signal),i+w)]
        if min(len(left),len(right))<w//2:continue
        l0,l1=np.percentile(left,[10,90]);r0,r1=np.percentile(right,[10,90])
        if min(l1-l0,r1-r0)<15:continue
        if abs(r1-l1)<max(15.,span*.2):continue
        if ambiguous_only:
            if abs(r0-l0)>=minimum:continue
        elif (r0-l0)*(r1-l1)<=0 or abs(r0-l0)<minimum:continue
        errors=[]
        for values,a,b in ((left,l0,l1),(right,r0,r1)):
            residual=np.minimum((values-a)**2,(values-b)**2)/(b-a)**2
            errors.append(float(np.mean(residual)))
        if max(errors)>.015:continue
        found.append(dict(frame=int(i),time_seconds=float(i/fps),fit_error=sum(errors),left_low=float(l0),left_high=float(l1),right_low=float(r0),right_high=float(r1)))
    # Among nearby candidates use the split with the strongest two-level fit.
    selected=[]
    for item in sorted(found,key=lambda x:x['fit_error']):
        if all(abs(item['frame']-s['frame'])>w for s in selected):selected.append(item)
    return sorted(selected,key=lambda x:x['frame'])

def change_aware_thresholds(signal,fps,window_seconds,global_off,global_on):
    changes=detect_changes(signal,fps,window_seconds)
    boundaries=[0]+[c['frame'] for c in changes]+[len(signal)]
    off=np.empty(len(signal));on=np.empty(len(signal));valid=np.zeros(len(signal),dtype=bool)
    for a,b in zip(boundaries[:-1],boundaries[1:]):
        chunk=signal[a:b];lo,hi=np.percentile(chunk,[5,95])
        fallback_off=lo+.35*(hi-lo) if hi-lo>=15 else global_off
        fallback_on=lo+.65*(hi-lo) if hi-lo>=15 else global_on
        off[a:b],on[a:b],valid[a:b]=local_thresholds(chunk,fps,window_seconds,fallback_off,fallback_on)
    return off,on,valid,changes
