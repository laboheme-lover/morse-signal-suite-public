"""Deterministic noise mixing building block; not an accuracy evaluation."""
from pathlib import Path
import hashlib,json
import numpy as np
import soundfile as sf

def mix_at_snr(clean,noise,snr_db,*,offset=0):
    clean=np.asarray(clean,dtype=np.float64);noise=np.asarray(noise,dtype=np.float64)
    if clean.ndim!=1 or noise.ndim!=1 or not len(clean) or not np.isfinite(clean).all() or not np.isfinite(noise).all():raise ValueError('Finite mono arrays required')
    if type(offset) is not int or offset<0 or offset+len(clean)>len(noise):raise ValueError('Noise must cover the requested interval; no looping')
    if not np.isfinite(snr_db):raise ValueError('Finite SNR required')
    segment=noise[offset:offset+len(clean)].copy();segment-=segment.mean()
    signal_rms=float(np.sqrt(np.mean(clean**2)));noise_rms=float(np.sqrt(np.mean(segment**2)))
    if min(signal_rms,noise_rms)<1e-12:raise ValueError('Silent clean/noise')
    gain=signal_rms/(noise_rms*10**(snr_db/20));scaled=segment*gain
    peak=float(np.max(np.abs(clean+scaled)));common_gain=min(1.,.95/peak) if peak else 1.
    signal=clean*common_gain;interference=scaled*common_gain;mixed=signal+interference
    measured=float(10*np.log10(np.mean(signal**2)/np.mean(interference**2)))
    return mixed.astype(np.float32),dict(snr_definition='RMS over the complete clean interval including silence; noise DC removed',
        requested_snr_db=snr_db,measured_snr_db=measured,noise_offset_samples=offset,noise_gain=gain,common_gain=common_gain,
        clean_rms=signal_rms,noise_rms=noise_rms,peak=float(np.max(np.abs(mixed))))

def rehearsal(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    from generate_morse_audio import generate_morse_audio
    clean=generate_morse_audio('イ');noise=np.random.default_rng(20260922).normal(0,.1,len(clean)+1000)
    rows=[]
    for snr in (20,10,5,0,-5):
        mixed,meta=mix_at_snr(clean,noise,snr,offset=123);path=output/f'snr_{snr}.wav';sf.write(path,mixed,16000,subtype='FLOAT')
        read,sr=sf.read(path,dtype='float32');assert sr==16000 and np.array_equal(read,mixed)
        assert abs(meta['measured_snr_db']-snr)<1e-8 and meta['peak']<=.950001
        repeat,_=mix_at_snr(clean,noise,snr,offset=123);assert np.array_equal(repeat,mixed)
        rows.append(dict(file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),**meta))
    (output/'verification.json').write_text(json.dumps(dict(status='PASS',scope='Synthetic mixing rehearsal only; not unknown-noise/model evaluation',seed=20260922,rows=rows),indent=2),encoding='utf-8')
    print('PASS: five SNRs, deterministic arrays, no clipping, FLOAT WAV roundtrip')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('output');rehearsal(p.parse_args().output)
