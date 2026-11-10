"""Bounded local upload decoding for the experiment UI."""
from pathlib import Path
import tempfile
import librosa
import numpy as np

def load_upload(data,suffix):
    if suffix not in ('.wav','.mp3','.flac'):raise ValueError('WAV / MP3 / FLACを指定してください。')
    if not data or len(data)>20_000_000:raise ValueError('空でない20 MB以下のファイルを指定してください。')
    with tempfile.TemporaryDirectory(prefix='morse_experiment_') as folder:
        path=Path(folder)/('audio'+suffix);path.write_bytes(data)
        duration=librosa.get_duration(path=path)
        if not np.isfinite(duration) or not .5<=duration<=120:raise ValueError('音声は0.5〜120秒にしてください。')
        audio,_=librosa.load(path,sr=16000,mono=True)
        if not 8000<=len(audio)<=120*16000 or not np.isfinite(audio).all():raise ValueError('読み込んだ音声の長さまたは数値が不正です。')
        return audio
