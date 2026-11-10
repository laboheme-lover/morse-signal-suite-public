"""Milestone 1: 固定条件で1文字の16-bit PCM WAVを生成。"""
import argparse
from pathlib import Path
import numpy as np
import soundfile as sf
from morse_table import get_morse_code

SAMPLE_RATE = 16000


def generate_morse_audio(label: str, dot_duration: float = 0.1,
                         frequency_hz: float = 700.0, amplitude: float = 0.7,
                         sample_rate: int = SAMPLE_RATE, padding: float = 0.1,
                         timing_jitter: float = 0.0,
                         rng: np.random.Generator | None = None,
                         timing_samples: list | None = None) -> np.ndarray:
    code = get_morse_code(label)
    if not isinstance(sample_rate, int) or sample_rate < 2:
        raise ValueError('sample_rate must be an integer >= 2')
    values = (dot_duration, frequency_hz, amplitude, padding, timing_jitter)
    if not all(np.isfinite(v) for v in values):
        raise ValueError('Parameters must be finite')
    if dot_duration <= 0 or round(dot_duration * sample_rate) < 2:
        raise ValueError('dot_duration is too short')
    if not 0 < frequency_hz < sample_rate / 2:
        raise ValueError('frequency_hz must be between 0 and Nyquist frequency')
    if not 0 < amplitude <= 1 or padding < 0:
        raise ValueError('amplitude must be in (0, 1]; padding must be >= 0')
    if not 0 <= timing_jitter <= 0.1:
        raise ValueError('timing_jitter must be in [0, 0.1]')
    rng = rng if rng is not None else np.random.default_rng()
    unit = round(dot_duration * sample_rate)
    def duration(kind, units):
        count = (round(dot_duration * sample_rate * units * rng.uniform(1-timing_jitter, 1+timing_jitter))
                 if timing_jitter else unit * units)
        if timing_samples is not None:
            timing_samples.append({'kind': kind, 'samples': count})
        return count
    silence = np.zeros(round(padding * sample_rate), dtype=np.float32)
    pieces = [silence]
    for index, symbol in enumerate(code):
        count = duration(symbol, 1 if symbol == '.' else 3)
        tone = amplitude * np.sin(2 * np.pi * frequency_hz * np.arange(count) / sample_rate)
        # 5 ms raised-cosine edges reduce clicks without changing symbol duration.
        ramp = min(round(0.005 * sample_rate), count // 2)
        if ramp >= 2:
            fade = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, ramp))
            tone[:ramp] *= fade
            tone[-ramp:] *= fade[::-1]
        pieces.append(tone.astype(np.float32))
        if index < len(code) - 1:
            pieces.append(np.zeros(duration('gap', 1), dtype=np.float32))
    pieces.append(silence)
    return np.concatenate(pieces)


def save_wav(path: str | Path, audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, audio, sample_rate, subtype='PCM_16', format='WAV')
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--char', default='イ', help='1符号の文字（例: イ、゛、1）')
    parser.add_argument('--output', type=Path, default=Path('data/clean/i.wav'))
    args = parser.parse_args()
    try:
        audio = generate_morse_audio(args.char)
    except ValueError as exc:
        parser.error(str(exc))
    path = save_wav(args.output, audio)
    print(f'{args.char} = {get_morse_code(args.char)}; {SAMPLE_RATE} Hz; {len(audio)} samples; {len(audio)/SAMPLE_RATE:.3f} s')
    print(path.resolve())


if __name__ == '__main__':
    main()
