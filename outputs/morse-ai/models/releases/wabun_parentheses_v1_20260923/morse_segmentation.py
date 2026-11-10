"""Tone-envelope segmentation for recordings with clear character gaps."""
import numpy as np
from scipy.signal import butter,sosfiltfilt,welch
from scipy.ndimage import uniform_filter1d


def segment_morse(audio,sample_rate=16000,frequency_hz=None,character_gap_seconds=None):
    audio=np.asarray(audio,dtype=float)
    if audio.ndim!=1 or len(audio)<sample_rate//2 or not np.isfinite(audio).all():
        raise ValueError('Expected at least 0.5 s of finite mono audio')
    if frequency_hz is None:
        frequencies,power=welch(audio,sample_rate,nperseg=min(16384,len(audio)))
        band=(frequencies>=300)&(frequencies<=1500)
        frequency_hz=float(frequencies[band][np.argmax(power[band])])
    filtered=sosfiltfilt(butter(4,[frequency_hz-100,frequency_hz+100],btype='bandpass',fs=sample_rate,output='sos'),audio)
    envelope=np.sqrt(np.maximum(0,uniform_filter1d(filtered**2,size=round(.01*sample_rate))))
    threshold=float(np.quantile(envelope,.95)*.25)
    if threshold<1e-6:
        raise ValueError('No sufficiently strong tone found')
    mask=envelope>threshold
    edges=np.diff(np.r_[False,mask,False].astype(int))
    starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)
    valid=ends-starts>=round(.02*sample_rate)
    starts=starts[valid];ends=ends[valid]
    if len(starts)<2:
        raise ValueError('Not enough tone events to estimate timing')
    lengths=(ends-starts)/sample_rate
    dot=float(np.median(lengths[lengths<=np.quantile(lengths,.4)]))
    if character_gap_seconds is not None and (not np.isfinite(character_gap_seconds) or character_gap_seconds<=0):
        raise ValueError('character_gap_seconds must be positive and finite')
    gap_threshold=2*dot if character_gap_seconds is None else float(character_gap_seconds)
    groups=[];first=0
    boundaries=np.flatnonzero((starts[1:]-ends[:-1])/sample_rate>gap_threshold)+1
    for end_index in list(boundaries)+[len(starts)]:
        pattern=''.join('.' if length<2*dot else '-' for length in lengths[first:end_index])
        groups.append(dict(start_sample=int(starts[first]),end_sample=int(ends[end_index-1]),
                           start_seconds=float(starts[first]/sample_rate),end_seconds=float(ends[end_index-1]/sample_rate),
                           pattern=pattern))
        first=end_index
    return groups,dict(frequency_hz=frequency_hz,dot_seconds=dot,threshold=threshold,
                      character_gap_seconds=gap_threshold,tone_events=len(starts),segments=len(groups))


def extract_character(audio,segment,sample_rate=16000):
    # Retain 5 ms around threshold crossings, then match training's 100 ms leading/trailing silence.
    margin=round(.005*sample_rate)
    clip=audio[max(0,segment['start_sample']-margin):min(len(audio),segment['end_sample']+margin)]
    return np.pad(clip,(round(.095*sample_rate),round(.095*sample_rate))).astype(np.float32)
