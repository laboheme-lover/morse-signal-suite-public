"""Milestone 5: validated map-style datasets and Windows-safe DataLoaders."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import random
import time
import numpy as np
import soundfile as sf
import torch
from torch.utils.data import Dataset, DataLoader
from audio_preprocessing import PreprocessConfig, wav_to_tensor
from morse_table import MORSE_TABLE

SPLITS = ('train', 'validation', 'test')


class MorseDataset(Dataset):
    def __init__(self, root, split, config=PreprocessConfig()):
        if split not in SPLITS:
            raise ValueError(f'Unknown split: {split}')
        self.root = Path(root).resolve()
        self.split = split
        self.config = config
        manifest = json.loads((self.root/'dataset_config.json').read_text(encoding='utf-8'))
        if manifest['status'] != 'complete':
            raise ValueError('Dataset has not completed validation')
        self.label_to_index = json.loads((self.root/'label_mapping.json').read_text(encoding='utf-8'))
        if self.label_to_index != {label:i for i,label in enumerate(manifest['labels'])}:
            raise ValueError('Label mapping differs from dataset configuration')
        with (self.root/'metadata.csv').open(encoding='utf-8-sig', newline='') as stream:
            all_rows = list(csv.DictReader(stream))
        if len(all_rows) != len(self.label_to_index)*manifest['samples_per_class']:
            raise ValueError('Dataset row count mismatch')
        if any(r['split'] not in SPLITS for r in all_rows):
            raise ValueError('Unknown split in metadata')
        self.rows = [r for r in all_rows if r['split'] == split]
        if not self.rows:
            raise ValueError(f'Empty split: {split}')
        seen = set()
        self.max_frames = 0
        # Read actual WAV headers, not just the previous report, before allowing fixed-size input.
        for row in self.rows:
            label = row['label']
            if (label not in self.label_to_index or row['morse_code'] != MORSE_TABLE[label]
                    or int(row['class_index']) != self.label_to_index[label]):
                raise ValueError('Invalid label metadata')
            path = (self.root/row['filepath']).resolve()
            if not path.is_relative_to(self.root) or path in seen:
                raise ValueError('Unsafe or duplicate audio path')
            seen.add(path)
            info = sf.info(path)
            if (info.samplerate != config.sample_rate or info.channels != 1 or info.frames < 1
                    or info.frames != int(row['samples']) or info.subtype != 'PCM_16'):
                raise ValueError(f'WAV header mismatch: {path}')
            self.max_frames = max(self.max_frames, 1+info.frames//config.hop_length)
        if self.max_frames > config.target_frames:
            raise ValueError(f'{split} requires {self.max_frames} frames; target_frames={config.target_frames}')

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        x = wav_to_tensor(self.root/row['filepath'], self.config)
        y = torch.tensor(self.label_to_index[row['label']], dtype=torch.long)
        return x, y


def seed_worker(worker_id):
    worker_seed = torch.initial_seed() % (2**32)
    np.random.seed(worker_seed)
    random.seed(worker_seed)
    torch.set_num_threads(1)


def create_dataloaders(root, batch_size=32, num_workers=0, seed=20260914, config=PreprocessConfig()):
    if type(batch_size) is not int or batch_size < 1 or type(num_workers) is not int or num_workers < 0:
        raise ValueError('Invalid batch_size or num_workers')
    loaders = {}
    for offset,split in enumerate(SPLITS):
        dataset = MorseDataset(root, split, config)
        kwargs = dict(batch_size=batch_size, shuffle=(split=='train'), num_workers=num_workers,
                      drop_last=False, worker_init_fn=seed_worker,
                      generator=torch.Generator().manual_seed(seed+offset))
        if num_workers:
            kwargs.update(multiprocessing_context='spawn', persistent_workers=False)
        loaders[split] = DataLoader(dataset, **kwargs)
    return loaders


def verify_loaders(root, output_dir, batch_size=32, num_workers=0, max_batches=0):
    if max_batches < 0:
        raise ValueError('max_batches must be >= 0')
    start = time.perf_counter()
    config = PreprocessConfig()
    loaders = create_dataloaders(root, batch_size, num_workers, config=config)
    report = dict(torch_version=torch.__version__, device='cpu', num_workers=num_workers,
                  batch_size=batch_size, preprocessing=config.to_dict(), splits={})
    for split,loader in loaders.items():
        counts = Counter(); sample_count=0; batches=0; first_shape=None; last_shape=None
        for x,y in loader:
            if x.dtype != torch.float32 or y.dtype != torch.int64 or not torch.isfinite(x).all():
                raise ValueError('Invalid batch tensor')
            if tuple(x.shape[1:]) != (1,64,512) or y.shape != (x.shape[0],):
                raise ValueError('Invalid batch shape')
            if int(y.min())<0 or int(y.max())>=len(loader.dataset.label_to_index):
                raise ValueError('Target index out of bounds')
            first_shape = first_shape or list(x.shape)
            last_shape = list(x.shape)
            counts.update(y.tolist()); sample_count+=len(y); batches+=1
            if batches % 100 == 0:
                print(f'{split}: {sample_count}/{len(loader.dataset)} tensors checked',flush=True)
            if max_batches and batches >= max_batches:
                break
        full_pass = sample_count == len(loader.dataset)
        if full_pass:
            expected=Counter(loader.dataset.label_to_index[r['label']] for r in loader.dataset.rows)
            if counts != expected:
                raise ValueError('DataLoader missed or duplicated labels')
        elif not max_batches:
            raise ValueError('Incomplete DataLoader pass')
        report['splits'][split] = dict(dataset_size=len(loader.dataset),samples_checked=sample_count,
                 batches_checked=batches,first_shape=first_shape,last_shape=last_shape,
                 max_source_frames=loader.dataset.max_frames,full_pass=full_pass,
                 label_counts=dict(sorted(counts.items())))
        print(f'{split}: {sample_count} checked; batch={first_shape}; full_pass={full_pass}',flush=True)
    report['elapsed_seconds']=time.perf_counter()-start
    report['metadata_sha256']=hashlib.sha256((Path(root)/'metadata.csv').read_bytes()).hexdigest()
    output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True)
    (output_dir/'preprocessing.json').write_text(json.dumps(config.to_dict(),indent=2),encoding='utf-8')
    (output_dir/'dataloader_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('data/dataset/m4_300'))
    parser.add_argument('--output-dir',type=Path,default=Path('evaluation/m5'))
    parser.add_argument('--batch-size',type=int,default=32)
    parser.add_argument('--num-workers',type=int,default=0)
    parser.add_argument('--max-batches',type=int,default=0,help='0=all; otherwise limit per split')
    args=parser.parse_args()
    # Limit oversubscription from BLAS on Windows during CPU preprocessing.
    from threadpoolctl import threadpool_limits
    torch.set_num_threads(1)
    with threadpool_limits(limits=1):
        report=verify_loaders(args.root,args.output_dir,args.batch_size,args.num_workers,args.max_batches)
    print(f"Verified in {report['elapsed_seconds']:.1f}s")


if __name__=='__main__':
    torch.multiprocessing.freeze_support()
    main()
