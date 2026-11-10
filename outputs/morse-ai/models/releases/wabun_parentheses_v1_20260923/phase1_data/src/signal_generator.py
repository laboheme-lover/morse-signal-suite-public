"""ITU 1/3/1/3/7 timing, one symbol or explicit space-separated words."""
import numpy as np
from .morse_table import TABLE


def generate_signal(text, sample_rate=16000, frequency=700, amplitude=.8, dot_duration=.1,
                    jitter=(-.1, .1), padding_seconds=.1, edge_ramp_ms=5, rng=None):
    if not text or text.startswith(' ') or text.endswith(' ') or '  ' in text or any(c not in TABLE and c != ' ' for c in text):
        raise ValueError('Use canonical A-Z/0-9, single ASCII spaces between words')
    values = (frequency, amplitude, dot_duration, *jitter, padding_seconds, edge_ramp_ms)
    if not all(np.isfinite(v) for v in values) or not 0 < frequency < sample_rate / 2 or not 0 < amplitude <= 1:
        raise ValueError('Invalid signal parameters')
    if dot_duration <= 0 or not -1 < jitter[0] <= jitter[1] < 1 or min(padding_seconds, edge_ramp_ms) < 0:
        raise ValueError('Invalid timing parameters')
    rng = rng if rng is not None else np.random.default_rng()
    pieces, intervals = [], []
    cursor = 0
    def add(kind, units, on=False, token_index=None, fixed=None):
        nonlocal cursor
        factor = 1 + float(rng.uniform(*jitter)) if fixed is None and jitter != (0, 0) else 1.0
        count = round(fixed * sample_rate) if fixed is not None else max(1, round(units * dot_duration * sample_rate * factor))
        if count == 0: return
        if on:
            part = amplitude * np.sin(2 * np.pi * frequency * np.arange(count) / sample_rate)
            ramp = min(round(edge_ramp_ms * sample_rate / 1000), count // 2)
            if ramp >= 2:
                fade = .5 - .5 * np.cos(np.linspace(0, np.pi, ramp))
                part[:ramp] *= fade; part[-ramp:] *= fade[::-1]
        else: part = np.zeros(count)
        pieces.append(part)
        intervals.append({'kind': kind, 'start_sample': cursor, 'end_sample': cursor + count,
                          'on': on, 'units': units, 'jitter_factor': factor, 'token_index': token_index})
        cursor += count
    add('padding', 0, fixed=padding_seconds)
    token_index = 0
    for wi, word in enumerate(text.split(' ')):
        if wi: add('word_gap', 7)
        for li, label in enumerate(word):
            if li: add('character_gap', 3)
            for si, symbol in enumerate(TABLE[label]):
                if si: add('intra_symbol_gap', 1, token_index=token_index)
                add('dot' if symbol == '.' else 'dash', 1 if symbol == '.' else 3, True, token_index)
            token_index += 1
    add('padding', 0, fixed=padding_seconds)
    return np.concatenate(pieces), intervals
