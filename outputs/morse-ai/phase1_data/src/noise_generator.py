"""Noise providers share a (length, RNG) interface for future recordings."""
import numpy as np
from .legacy import legacy_mix

mix_at_snr = legacy_mix()  # reuse existing validated RMS/anti-clipping implementation
PROVIDERS = {
    'gaussian': lambda size, rng: rng.standard_normal(size),
    'white': lambda size, rng: rng.uniform(-np.sqrt(3), np.sqrt(3), size),
}


def add_noise(signal, noise_type, snr_db, rng):
    if noise_type == 'none':
        if snr_db is not None: raise ValueError('Clean audio requires null SNR')
        peak = float(np.max(np.abs(signal)))
        gain = min(1.0, .98 / peak) if peak else 1.0
        return signal * gain, signal * gain, {'mix_gain': gain, 'measured_snr_db': None}
    if noise_type not in PROVIDERS or snr_db is None: raise ValueError('Unknown noise or missing SNR')
    mixed, clean_scaled, noise_scaled, gain = mix_at_snr(signal, PROVIDERS[noise_type](len(signal), rng), snr_db)
    measured = float(10 * np.log10(np.mean(clean_scaled**2) / np.mean(noise_scaled**2)))
    return mixed, clean_scaled, {'mix_gain': gain, 'measured_snr_db': measured}
