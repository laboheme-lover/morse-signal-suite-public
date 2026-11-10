"""Conservative missing-signal warning. Never modifies states or decoded text."""
import numpy as np

VERSION='optical-video-v2-diagnostics'

def missed_signal_windows(times,signal,states,fps,dot_seconds,threshold_on,global_contrast):
    window=max(6,int(round(max(2.,12*dot_seconds)*fps)))
    stride=max(1,window//2)
    minimum=max(8.,.08*global_contrast)
    findings=[]
    for start in range(0,len(signal),stride):
        stop=min(start+window,len(signal))
        if stop-start<max(6,int(round(6*dot_seconds*fps))):continue
        chunk=signal[start:stop];lo,hi=np.percentile(chunk,[10,90])
        fraction=float(np.mean(states[start:stop]))
        # A long OFF interval with substantial changes below the ON threshold
        # could contain missed weak flashes. Quiet pauses do not meet this condition.
        if hi-lo>=minimum and hi<threshold_on and fraction<.05:
            findings.append(dict(start_seconds=float(times[start]),end_seconds=float(times[stop-1]+1/fps),
                local_low=float(lo),local_high=float(hi),local_contrast=float(hi-lo),on_fraction=fraction,
                reason='点灯判定されない区間にも明暗の変化があります。露出低下・光源の移動などによる信号の見落としが疑われます。'))
    # Merge overlapping intervals for readable review, retaining window evidence.
    merged=[]
    for item in findings:
        if merged and item['start_seconds']<=merged[-1]['end_seconds']:
            merged[-1]['end_seconds']=max(merged[-1]['end_seconds'],item['end_seconds']);merged[-1]['windows'].append(item)
        else:merged.append(dict(start_seconds=item['start_seconds'],end_seconds=item['end_seconds'],reason=item['reason'],windows=[item]))
    return merged
