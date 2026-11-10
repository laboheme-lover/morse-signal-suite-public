"""Experimental front end; never used by the deployed app automatically."""
import copy
import numpy as np
from scipy.signal import butter,sosfiltfilt,welch
from scipy.ndimage import uniform_filter1d,binary_closing,binary_opening
from morse_table import MORSE_TABLE,REVERSE_TABLE
from policy import render_body

def segment_candidate(audio,sample_rate=16000):
    x=np.asarray(audio,dtype=float)
    if x.ndim!=1 or len(x)<sample_rate//2 or not np.isfinite(x).all():raise ValueError('Invalid audio')
    freq,power=welch(x,sample_rate,nperseg=min(16384,len(x)))
    band=(freq>=300)&(freq<=1500);carrier=float(freq[band][np.argmax(power[band])])
    filtered=sosfiltfilt(butter(4,[carrier-45,carrier+45],btype='bandpass',fs=sample_rate,output='sos'),x)
    env=np.sqrt(np.maximum(0,uniform_filter1d(filtered**2,size=round(.01*sample_rate))))
    low,high=np.quantile(env,[.15,.95]);threshold=float(low+.35*(high-low))
    if high<1e-6 or high<=low:raise ValueError('No sufficient tone contrast')
    mask=binary_closing(env>threshold,structure=np.ones(round(.008*sample_rate)))
    mask=binary_opening(mask,structure=np.ones(round(.015*sample_rate)))
    edges=np.diff(np.r_[False,mask,False].astype(int));starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)
    lengths=(ends-starts)/sample_rate
    if len(starts)<2:raise ValueError('Not enough events')
    dot=float(np.median(lengths[lengths<=np.quantile(lengths,.4)]));groups=[];first=0
    boundaries=np.flatnonzero((starts[1:]-ends[:-1])/sample_rate>2*dot)+1
    for end in list(boundaries)+[len(starts)]:
        groups.append(dict(start_sample=int(starts[first]),end_sample=int(ends[end-1]),start_seconds=float(starts[first]/sample_rate),
                           end_seconds=float(ends[end-1]/sample_rate),pattern=''.join('.' if n<2*dot else '-' for n in lengths[first:end])))
        first=end
    return groups,dict(frequency_hz=carrier,dot_seconds=dot,threshold=threshold,segments=len(groups),method='narrow-band-noise-floor-v1')

def edit_one(a,b):
    if abs(len(a)-len(b))>1:return False
    if len(a)==len(b):return sum(x!=y for x,y in zip(a,b))==1
    if len(a)>len(b):a,b=b,a
    return any(b[:i]+b[i+1:]==a for i in range(len(b)))

def repair_mode(source):
    """Only CNN top-1 >= .98, observed unsupported code, one edit, legal state.
    Does not infer repairs from a transcript/reference; keeps an audit trail.
    """
    rows=copy.deepcopy(source);inside=False;repairs=[]
    for r in rows:
        p=r['pattern'];target=r['prediction']
        if p==MORSE_TABLE['（']:inside=True
        elif p==MORSE_TABLE['）']:inside=False
        elif target in ('（','）') and p not in REVERSE_TABLE and r['confidence']>=.98 and edit_one(p,MORSE_TABLE[target]) and ((target=='（')!=inside):
            r['observed_pattern']=p;r['pattern']=MORSE_TABLE[target];inside=target=='（';repairs.append(r['index'])
        r['rule_prediction']=REVERSE_TABLE.get(r['pattern'],'?')
    text,rows,warnings=render_body(rows)
    for r in rows:
        if r['index'] in repairs:r['review_reason']='実験的なモード符号補正。元符号を要確認。'
    if repairs:warnings.append('Experimental mode repairs: '+','.join(map(str,repairs)))
    return text,rows,warnings
