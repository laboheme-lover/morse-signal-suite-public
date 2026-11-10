"""Shared WAV/Mel/Tensor preprocessing for datasets and future inference."""
from dataclasses import asdict, dataclass
from pathlib import Path
import warnings
import librosa
import numpy as np

SAMPLE_RATE = 16000
N_MELS = 64
N_FFT = 512
HOP_LENGTH = 128


@dataclass(frozen=True)
class PreprocessConfig:
    sample_rate: int = SAMPLE_RATE
    n_mels: int = N_MELS
    n_fft: int = N_FFT
    hop_length: int = HOP_LENGTH
    target_frames: int = 512
    pad_db: float = -100.0

    def __post_init__(self):
        for name in ('sample_rate', 'n_mels', 'n_fft', 'hop_length', 'target_frames'):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f'{name} must be a positive integer')
        if not np.isfinite(self.pad_db):
            raise ValueError('pad_db must be finite')

    def to_dict(self):
        return dict(asdict(self), version='m5-v1', center=True, power=2.0,
                    db_ref=1.0, top_db=80.0, normalization='none', channel_order='CHW')


def load_audio(path: str | Path, config: PreprocessConfig = PreprocessConfig()) -> np.ndarray:
    audio, _ = librosa.load(path, sr=config.sample_rate, mono=True)
    if audio.size == 0 or not np.isfinite(audio).all():
        raise ValueError('音声が空、または不正な数値を含みます。')
    return audio


def compute_mel_db(audio: np.ndarray, config: PreprocessConfig = PreprocessConfig()) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim != 1 or audio.size == 0 or not np.isfinite(audio).all():
        raise ValueError('有限の数値を持つ空でないモノラル音声が必要です。')
    mel = librosa.feature.melspectrogram(y=audio, sr=config.sample_rate,
        n_mels=config.n_mels, n_fft=config.n_fft, hop_length=config.hop_length,
        power=2.0, center=True, pad_mode='constant')
    return librosa.power_to_db(mel, ref=1.0, top_db=80).astype(np.float32)


def mel_to_tensor(mel, config: PreprocessConfig = PreprocessConfig(), *, allow_truncate=False):
    import torch
    mel = np.asarray(mel, dtype=np.float32)
    if mel.ndim != 2 or mel.shape[0] != config.n_mels or mel.shape[1] < 1 or not np.isfinite(mel).all():
        raise ValueError('Invalid Mel array')
    if mel.shape[1] > config.target_frames:
        if not allow_truncate:
            raise ValueError(f'{mel.shape[1]} frames exceed target_frames={config.target_frames}; increase input length')
        warnings.warn('Explicit truncation discards the end of the Morse signal', UserWarning, stacklevel=2)
    result = np.full((1, config.n_mels, config.target_frames), config.pad_db, dtype=np.float32)
    frames = min(mel.shape[1], config.target_frames)
    result[0, :, :frames] = mel[:, :frames]
    return torch.from_numpy(result)


def audio_to_tensor(audio, config: PreprocessConfig = PreprocessConfig(), *, allow_truncate=False):
    return mel_to_tensor(compute_mel_db(audio, config), config, allow_truncate=allow_truncate)


def wav_to_tensor(path, config: PreprocessConfig = PreprocessConfig(), *, allow_truncate=False):
    return audio_to_tensor(load_audio(path, config), config, allow_truncate=allow_truncate)
