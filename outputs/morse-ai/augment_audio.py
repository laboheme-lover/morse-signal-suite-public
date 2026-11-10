"""Milestone 2: reproducible synthesis and whole-recording RMS SNR mixing."""
import numpy as np
from generate_morse_audio import SAMPLE_RATE, generate_morse_audio
from morse_table import get_morse_code, normalize_text

SPEED_RANGES = {'slow': (0.13, 0.17), 'normal': (0.09, 0.11), 'fast': (0.05, 0.07)}
FREQUENCY_RANGE = (600, 800)
AMPLITUDE_RANGE = (0.4, 0.9)
TIMING_JITTER = 0.10
SNR_LEVELS = (20, 10, 5, 0, -5)


def mix_at_snr(signal, noise, snr_db):
    """Return mixed audio, scaled signal, scaled noise, and common anti-clipping gain.

    SNR uses all samples, including intra-symbol and leading/trailing silence.
    Joint scaling preserves SNR; amplitude metadata describes the pre-mix signal.
    """
    signal = np.asarray(signal, dtype=np.float64)
    noise = np.asarray(noise, dtype=np.float64)
    if (signal.ndim != 1 or signal.size == 0 or signal.shape != noise.shape
            or not np.isfinite(signal).all() or not np.isfinite(noise).all()
            or not np.isfinite(snr_db) or not -100 <= snr_db <= 100):
        raise ValueError('Finite equal-length mono signals and SNR in [-100, 100] required')
    signal_rms = np.sqrt(np.mean(signal ** 2))
    noise_rms = np.sqrt(np.mean(noise ** 2))
    if signal_rms == 0 or noise_rms == 0:
        raise ValueError('Signal and noise must have nonzero RMS')
    noise = noise * (signal_rms / noise_rms) * 10 ** (-snr_db / 20)
    gain = min(1.0, 0.98 / np.max(np.abs(signal + noise)))
    return (signal + noise) * gain, signal * gain, noise * gain, gain


def generate_sample(label, speed, noise_type='clean', snr_db=None, seed=0):
    """Same seed/speed/label gives the same underlying signal for every noise condition."""
    code = get_morse_code(label)
    label = normalize_text(label)
    if speed not in SPEED_RANGES:
        raise ValueError(f'Unknown speed: {speed}')
    if noise_type not in ('clean', 'white'):
        raise ValueError('noise_type must be clean or white')
    if (noise_type == 'clean' and snr_db is not None) or (noise_type == 'white' and snr_db not in SNR_LEVELS):
        raise ValueError('clean requires no SNR; white requires one of 20, 10, 5, 0, -5')
    rng = np.random.default_rng(seed)
    dot = float(rng.uniform(*SPEED_RANGES[speed]))
    frequency = float(rng.uniform(*FREQUENCY_RANGE))
    amplitude = float(rng.uniform(*AMPLITUDE_RANGE))
    timings = []
    clean = generate_morse_audio(label, dot, frequency, amplitude,
                                 timing_jitter=TIMING_JITTER, rng=rng, timing_samples=timings)
    gain = 1.0
    audio = clean
    measured = None
    if noise_type == 'white':
        audio, signal, noise, gain = mix_at_snr(clean, rng.standard_normal(len(clean)), snr_db)
        measured = float(10 * np.log10(np.mean(signal**2) / np.mean(noise**2)))
    metadata = dict(label=label, morse_code=code, speed=speed, dot_duration=dot,
                    frequency_hz=frequency, amplitude=amplitude, noise_type=noise_type,
                    snr_db=snr_db, seed=int(seed), sample_rate=SAMPLE_RATE,
                    timing_jitter=TIMING_JITTER, timing_samples=timings, padding_seconds=0.1,
                    samples=len(audio), duration_seconds=len(audio)/SAMPLE_RATE,
                    mix_gain=gain, measured_snr_db=measured, snr_reference='whole_recording_rms',
                    generator_version='m2-v1', numpy_version=np.__version__)
    return audio, metadata
