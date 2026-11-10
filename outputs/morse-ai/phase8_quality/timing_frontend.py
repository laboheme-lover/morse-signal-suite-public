"""Experimental timing estimator; retains the deployed ±100 Hz detector."""
import numpy as np
from scipy.signal import butter,sosfiltfilt,welch
from scipy.ndimage import uniform_filter1d

def estimate_unit(lengths,gaps):
    lengths=np.asarray(lengths,dtype=float);gaps=np.asarray(gaps,dtype=float)
    if len(lengths)<2 or not np.isfinite(lengths).all() or np.any(lengths<=0) or not np.isfinite(gaps).all() or np.any(gaps<=0):
        raise ValueError('Positive finite tone and gap durations required')
    # Fit the timing grammar, not any expected letter/transcript. Both marks and
    # gaps contribute, preventing a long-mark majority from defining the dot.
    candidates=np.unique(np.r_[lengths,lengths/3,gaps,gaps/3,gaps/7])
    candidates=candidates[(candidates>=.015)&(candidates<=.5)]
    if not len(candidates):raise ValueError('No timing candidate between 15 and 500 ms')
    def cost(unit):
        mark=np.min(np.abs(np.log(lengths[:,None]/(unit*np.array([1,3])))),axis=1)
        gap=np.min(np.abs(np.log(gaps[:,None]/(unit*np.array([1,3,7])))),axis=1) if len(gaps) else np.array([])
        # Limit a single distorted event, but retain minority short marks.
        return float(np.mean(np.minimum(mark,.8))+(np.mean(np.minimum(gap,.8)) if len(gap) else 0))
    ordered=sorted(((cost(u),float(u)) for u in candidates),key=lambda v:(round(v[0],10),-v[1]))
    score,unit=ordered[0]
    alternatives=[(s,u) for s,u in ordered[1:] if abs(np.log(u/unit))>.4]
    margin=alternatives[0][0]-score if alternatives else None
    return unit,dict(timing_fit_loss=score,timing_ambiguous=margin is not None and margin<.03,timing_margin=margin)

def segment_timing(audio,sample_rate=16000):
    x=np.asarray(audio,dtype=float)
    if x.ndim!=1 or len(x)<sample_rate//2 or not np.isfinite(x).all():raise ValueError('Invalid audio')
    frequencies,power=welch(x,sample_rate,nperseg=min(16384,len(x)))
    band=(frequencies>=300)&(frequencies<=1500);frequency=float(frequencies[band][np.argmax(power[band])])
    filtered=sosfiltfilt(butter(4,[frequency-100,frequency+100],btype='bandpass',fs=sample_rate,output='sos'),x)
    env=np.sqrt(np.maximum(0,uniform_filter1d(filtered**2,size=round(.01*sample_rate))))
    threshold=float(np.quantile(env,.95)*.25)
    if threshold<1e-6:raise ValueError('No sufficiently strong tone')
    edges=np.diff(np.r_[False,env>threshold,False].astype(int));starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)
    valid=ends-starts>=round(.02*sample_rate);starts=starts[valid];ends=ends[valid]
    lengths=(ends-starts)/sample_rate;gaps=(starts[1:]-ends[:-1])/sample_rate
    unit,meta=estimate_unit(lengths,gaps);first=0;rows=[]
    for end in list(np.flatnonzero(gaps>2*unit)+1)+[len(starts)]:
        rows.append(dict(start_sample=int(starts[first]),end_sample=int(ends[end-1]),start_seconds=float(starts[first]/sample_rate),
            end_seconds=float(ends[end-1]/sample_rate),pattern=''.join('.' if x<2*unit else '-' for x in lengths[first:end])))
        first=end
    return rows,dict(frequency_hz=frequency,dot_seconds=unit,threshold=threshold,segments=len(rows),**meta)
