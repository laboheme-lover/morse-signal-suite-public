"""WAVの波形とメルスペクトログラムを保存（--show でウィンドウ表示）。"""
import argparse
import os
from pathlib import Path
import numpy as np
from audio_preprocessing import (SAMPLE_RATE, N_MELS, N_FFT, HOP_LENGTH,
                                 load_audio, compute_mel_db)


def visualize(path: str | Path, output_dir: str | Path, show: bool = False) -> tuple[Path, Path]:
    # Keep the default font cache inside this project, including sandboxed Windows use.
    cache_dir = Path(__file__).resolve().parent / '.cache' / 'matplotlib'
    if 'MPLCONFIGDIR' not in os.environ:
        cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ['MPLCONFIGDIR'] = str(cache_dir)
    import matplotlib
    if not show:
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import librosa.display
    audio = load_audio(path)
    mel = compute_mel_db(audio)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(path).stem
    image_path = output_dir / f'{stem}_waveform_mel.png'
    array_path = output_dir / f'{stem}_mel.npy'
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), layout='constrained')
    axes[0].plot(np.arange(len(audio)) / SAMPLE_RATE, audio, linewidth=0.6)
    axes[0].set(xlabel='Time (s)', ylabel='Amplitude', title='Waveform (16 kHz mono)', xlim=(0, len(audio)/SAMPLE_RATE))
    mesh = librosa.display.specshow(mel, sr=SAMPLE_RATE, hop_length=HOP_LENGTH,
                                    x_axis='time', y_axis='mel', ax=axes[1])
    axes[1].set_title('Mel spectrogram (64 bands, no time truncation)')
    fig.colorbar(mesh, ax=axes[1], format='%+2.0f dB')
    fig.savefig(image_path, dpi=150)
    np.save(array_path, mel, allow_pickle=False)
    if show:
        plt.show()
    plt.close(fig)
    print(f'mel shape={mel.shape}; finite={bool(np.isfinite(mel).all())}')
    print(image_path.resolve())
    print(array_path.resolve())
    return image_path, array_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wav', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path('evaluation'))
    parser.add_argument('--show', action='store_true')
    args = parser.parse_args()
    visualize(args.wav, args.output_dir, args.show)


if __name__ == '__main__':
    main()
