"""Bounded spectral batches and real FFT Hilbert transform for long recordings.

The fast FFT zero padding changes the finite-record Hilbert boundary convention.
This is a separately evaluated frontend, not a claim of bitwise equivalence.
"""
import numpy as np
from scipy.signal import welch, stft, butter, sosfiltfilt
from scipy.fft import rfft, irfft, next_fast_len
from scipy.ndimage import median_filter

def carrier(x,sr):
    size=min(len(x),16384);hop=size-size//2;count=1+(len(x)-size)//hop
    total=None
    for first in range(0,count,64):
        n=min(64,count-first)
        f,p=welch(x[first*hop:(first+n-1)*hop+size],sr,nperseg=size)
        total=p*n if total is None else total+p*n
    band=(f>=300)&(f<=1500)
    return float(f[band][np.argmax(total[band])])

def ridge_frames(x,sr,anchor):
    size=1024;hop=128
    # Match scipy stft(boundary='zeros', padded=True) frame locations.
    extra=(-len(x))%hop
    padded=np.pad(x,(size//2,size//2+extra))
    count=1+(len(padded)-size)//hop
    strength=np.empty(count);ridge=np.empty(count)
    for first in range(0,count,2048):
        n=min(2048,count-first)
        f,_,z=stft(padded[first*hop:(first+n-1)*hop+size],fs=sr,nperseg=size,noverlap=size-hop,boundary=None,padded=False)
        band=(f>=max(200,anchor-220))&(f<=min(1700,anchor+220))
        power=abs(z[band])**2;peak=power.argmax(axis=0)
        strength[first:first+n]=power[peak,np.arange(n)];ridge[first:first+n]=f[band][peak]
    t=(np.arange(count)*hop+size/2)/sr-(size/2)/sr
    return t,ridge,strength

def fast_analytic(x):
    n=len(x);size=next_fast_len(n,real=True)
    spectrum=rfft(x,n=size);spectrum*=-1j;spectrum[0]=0
    if size%2==0:spectrum[-1]=0
    imaginary=irfft(spectrum,n=size)[:n]
    result=np.empty(n,dtype=np.complex128);result.real=x;result.imag=imaginary
    return result,size

def track_carrier(audio,sr=16000):
    x=np.asarray(audio,dtype=float)
    if x.ndim!=1 or len(x)<sr//2 or not np.isfinite(x).all():raise ValueError('Invalid mono audio')
    anchor=carrier(x,sr);t,ridge,strength=ridge_frames(x,sr,anchor)
    if np.quantile(strength,.95)<1e-12:raise ValueError('No trackable carrier')
    active=strength>=max(float(np.quantile(strength,.95))*.15,1e-12)
    if active.sum()<3:raise ValueError('Too few reliable carrier frames')
    ridge=np.interp(t,t[active],ridge[active]);ridge=median_filter(ridge,size=5,mode='nearest')
    phase=np.interp(np.arange(len(x))/sr,t,ridge)
    np.cumsum(phase,out=phase);phase*=2*np.pi;phase/=sr
    filtered=sosfiltfilt(butter(4,[max(100,anchor-270),min(2000,anchor+270)],fs=sr,btype='bandpass',output='sos'),x)
    analytic,fft_size=fast_analytic(filtered);del filtered,x
    block=65536
    for start in range(0,len(analytic),block):
        end=min(start+block,len(analytic));analytic[start:end]*=np.exp(-1j*phase[start:end])
    del phase
    base=sosfiltfilt(butter(4,70,fs=sr,output='sos'),analytic);del analytic
    output=np.empty(len(base),dtype=np.float32)
    for start in range(0,len(base),block):
        end=min(start+block,len(base));times=np.arange(start,end)/sr
        output[start:end]=np.real(base[start:end]*np.exp(2j*np.pi*700*times))
    meta=dict(anchor_hz=anchor,tracked_min_hz=float(ridge.min()),tracked_max_hz=float(ridge.max()),target_hz=700,
        active_frame_fraction=float(active.mean()),track_seconds=t.tolist(),track_hz=ridge.tolist(),
        implementation='low-memory-v1',hilbert_fft_samples=fft_size,audio_samples=len(audio),spectral_batch_frames=2048)
    return output,meta
