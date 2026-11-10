import numpy as np
from .common import digest
from .signal_generator import generate_signal
from .noise_generator import add_noise
from .morse_table import TABLE
from . import VERSION


def synthesis_config(cfg):
    keys = ('sample_rate', 'frequency', 'dot_duration_ms', 'amplitude', 'timing_jitter',
            'noise_types', 'snr_db', 'padding_seconds', 'edge_ramp_ms', 'random_seed')
    return {k: cfg[k] for k in keys} | {'table': TABLE, 'version': VERSION}


def sample_seed(cfg, split, label, index):
    return int(digest([synthesis_config(cfg), split, label, index])[:16], 16)


def synthesize(label, cfg, seed):
    rng = np.random.default_rng(seed)
    draw = lambda key: float(rng.uniform(cfg[key]['min'], cfg[key]['max']))
    frequency, dot, amplitude = draw('frequency'), draw('dot_duration_ms') / 1000, draw('amplitude')
    noise_type = str(rng.choice(cfg['noise_types']))
    snr = None if noise_type == 'none' else float(rng.choice(cfg['snr_db']))
    jitter = (cfg['timing_jitter']['min'], cfg['timing_jitter']['max'])
    clean, timings = generate_signal(label, cfg['sample_rate'], frequency, amplitude, dot, jitter,
                                    cfg['padding_seconds'], cfg['edge_ramp_ms'], rng)
    mixed, clean_scaled, noise = add_noise(clean, noise_type, snr, rng)
    return mixed, clean_scaled, {'sample_rate': cfg['sample_rate'], 'frequency': frequency,
        'amplitude': amplitude, 'dot_duration': dot, 'timing_jitter': jitter,
        'noise_type': noise_type, 'snr_db': snr, 'random_seed': seed, 'timing_samples': timings,
        'snr_reference': 'whole_recording_rms', **noise}
