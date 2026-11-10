"""Translate a narrowband CW carrier without resampling or changing timing."""
import numpy as np
from scipy.signal import butter,hilbert,sosfiltfilt,welch


def translate_carrier(audio,sample_rate=16000,source_hz=None,target_hz=700.,half_bandwidth=150.):
    x=np.asarray(audio,dtype=np.float64)
    if x.ndim!=1 or len(x)<sample_rate//2 or not np.isfinite(x).all():
        raise ValueError('Expected at least 0.5 seconds of finite mono audio')
    if np.max(np.abs(x))<1e-6:raise ValueError('No signal')
    if source_hz is None:
        f,p=welch(x,sample_rate,nperseg=min(32768,len(x)))
        mask=(f>=200)&(f<=min(5000,sample_rate/2-half_bandwidth-1))
        if not mask.any():raise ValueError('No valid carrier search band')
        source_hz=float(f[mask][np.argmax(p[mask])])
    if not all(np.isfinite(v) for v in (source_hz,target_hz,half_bandwidth)) or half_bandwidth<=0:
        raise ValueError('Invalid frequency parameters')
    if not half_bandwidth<source_hz<sample_rate/2-half_bandwidth or not half_bandwidth<target_hz<sample_rate/2-half_bandwidth:
        raise ValueError('Carrier passband must lie inside (0, Nyquist)')
    filtered=sosfiltfilt(butter(4,[source_hz-half_bandwidth,source_hz+half_bandwidth],
                                btype='bandpass',fs=sample_rate,output='sos'),x)
    analytic=hilbert(filtered)
    shifted=np.real(analytic*np.exp(2j*np.pi*(target_hz-source_hz)*np.arange(len(x))/sample_rate))
    gain=min(1.,.98/max(float(np.max(np.abs(shifted))),1e-12))
    shifted=(shifted*gain).astype(np.float32)
    return shifted,dict(method='bandpass + analytic-signal frequency translation',source_hz=source_hz,
                        target_hz=target_hz,half_bandwidth_hz=half_bandwidth,anti_clip_gain=gain,
                        input_samples=len(x),output_samples=len(shifted),sample_rate=sample_rate,
                        timing_resampled=False)
