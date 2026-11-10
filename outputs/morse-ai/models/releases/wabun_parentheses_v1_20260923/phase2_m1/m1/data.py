from pathlib import Path
import sys
import numpy as np
import torch
from scipy.signal import butter, sosfiltfilt
from torch.nn.utils.rnn import pad_sequence

ROOT = Path(__file__).resolve().parents[1]
PHASE1 = ROOT.parent / 'phase1_data'
if str(PHASE1) not in sys.path:
    sys.path.insert(0, str(PHASE1))
from src.dataset_manager import WaveformDataset


def envelope(audio, sample_rate, config):
    """No labels, thresholds learned from the corpus, or symbol decoding."""
    x = np.asarray(audio, dtype=np.float64)
    if sample_rate != config['sample_rate']:
        raise ValueError('Sample rate mismatch; explicit resampling is required')
    if x.ndim != 1 or len(x) < 64 or not np.isfinite(x).all():
        raise ValueError('Expected finite mono audio of at least 64 samples')
    p = config['preprocessing']
    low, high = p['band_hz']
    if not 0 < low < high < sample_rate / 2:
        raise ValueError('Invalid filter band')
    sos = butter(p['filter_order'], [low, high], btype='bandpass', fs=sample_rate, output='sos')
    x = sosfiltfilt(sos, x)
    frame = round(sample_rate * p['frame_ms'] / 1000)
    hop = round(sample_rate * p['hop_ms'] / 1000)
    if not 0 < hop <= frame:
        raise ValueError('Invalid frame/hop')
    x = np.pad(x, (frame // 2, frame - frame // 2))
    energy = np.concatenate(([0.], np.cumsum(x * x)))
    starts = np.arange(0, len(x) - frame + 1, hop)
    rms = np.sqrt(np.maximum((energy[starts + frame] - energy[starts]) / frame, 0))
    lo, hi = np.quantile(rms, [p['floor_quantile'], p['ceiling_quantile']])
    feature = np.clip((rms - lo) / max(hi - lo, 1e-6), 0, 2).astype(np.float32)
    return torch.from_numpy(feature).unsqueeze(-1)


class PreparedDataset(torch.utils.data.Dataset):
    def __init__(self, split, config, root=PHASE1, evaluation=False):
        if split == 'test' and not evaluation:
            raise ValueError('Test is evaluation-only')
        base = WaveformDataset(split, root=root, purpose='evaluation' if evaluation else 'training')
        self.labels, self.rows = base.labels, base.rows
        self.items = []
        for i in range(len(base)):
            sample = base[i]  # checks the original waveform hash before preprocessing
            self.items.append((envelope(sample['audio'], sample['sample_rate'], config), sample['label_index'], i))
            if (i + 1) % 5000 == 0:
                print(f'Prepared {split}: {i+1}/{len(base)}', flush=True)

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]


def collate(items):
    xs, ys, indices = zip(*items)
    lengths = torch.tensor([len(x) for x in xs], dtype=torch.long)
    return pad_sequence(xs, batch_first=True).transpose(1, 2), lengths, torch.tensor(ys), torch.tensor(indices)
