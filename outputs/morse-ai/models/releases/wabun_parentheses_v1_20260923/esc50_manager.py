"""ESC-50 catalog validation, fold isolation, and optional official download."""
import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import re
import urllib.request
from functools import lru_cache
import numpy as np
import soundfile as sf
import librosa

ESC50_REVISION = '33c8ce9eb2cf0b1c2f8bcf322eb349b6be34dbb6'
BASE_URL = f'https://raw.githubusercontent.com/karolpiczak/ESC-50/{ESC50_REVISION}/'
SPLIT_FOLDS = {'train': (1, 2, 3), 'validation': (4,), 'test': (5,)}


@dataclass(frozen=True)
class NoiseRecord:
    filename: str
    category: str
    fold: int
    src_file: str


class ESC50Manager:
    def __init__(self, root='data/ESC-50-master', cache_audio=False):
        self.root = Path(root).resolve()
        catalog = self.root / 'meta/esc50.csv'
        self.catalog_sha256 = hashlib.sha256(catalog.read_bytes()).hexdigest()
        with catalog.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            if not {'filename', 'category', 'fold', 'src_file'} <= set(reader.fieldnames or []):
                raise ValueError('ESC-50 metadata is missing required columns')
            self.records = tuple(NoiseRecord(r['filename'], r['category'], int(r['fold']), r['src_file']) for r in reader)
        if not self.records:
            raise ValueError('Empty ESC-50 catalog')
        source_splits = {}
        names = set()
        for record in self.records:
            if not re.fullmatch(r'[1-5]-[A-Za-z0-9_-]+\.wav', record.filename):
                raise ValueError(f'Unsafe/invalid ESC-50 filename: {record.filename}')
            if record.fold not in range(1, 6) or int(record.filename[0]) != record.fold:
                raise ValueError(f'Invalid or conflicting fold: {record.filename}')
            if not record.src_file or not record.category or record.filename in names:
                raise ValueError('Empty metadata or duplicate filename')
            names.add(record.filename)
            split = next(s for s, folds in SPLIT_FOLDS.items() if record.fold in folds)
            source_splits.setdefault(record.src_file, set()).add(split)
        # Official metadata contains a few source IDs spanning validation/test.
        # Quarantine every fragment of such a source; never move a clip to another fold.
        conflicts = {src for src, splits in source_splits.items() if len(splits) > 1}
        self.excluded_records = tuple(r for r in self.records if r.src_file in conflicts)
        self.records = tuple(r for r in self.records if r.src_file not in conflicts)
        # Opt-in immutable snapshot for bulk generation; default retains live file checks.
        if cache_audio:
            self.candidates = lru_cache(maxsize=6)(self.candidates)
            self._load_audio = lru_cache(maxsize=128)(self._load_audio)

    def _load_audio(self, path, sample_rate):
        audio, sr = sf.read(path, dtype='float32', always_2d=True)
        if audio.size == 0 or not np.isfinite(audio).all():
            raise ValueError(f'Empty/nonfinite noise: {path.name}')
        audio = np.mean(audio, axis=1)
        if sr != sample_rate:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=sample_rate)
        return audio, sr, hashlib.sha256(path.read_bytes()).hexdigest()

    def audio_path(self, record):
        path = (self.root / 'audio' / record.filename).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('Audio path escapes dataset root')
        return path

    def candidates(self, split, available_only=False):
        if split not in SPLIT_FOLDS:
            raise ValueError(f'Unknown split: {split}')
        records = tuple(r for r in self.records if r.fold in SPLIT_FOLDS[split])
        missing = [r for r in records if not self.audio_path(r).is_file()]
        if missing and not available_only:
            raise FileNotFoundError(f'{split}: {len(missing)} WAV files missing; download all or explicitly use available_only')
        available = tuple(r for r in records if self.audio_path(r).is_file())
        if not available:
            raise FileNotFoundError(f'No local noise files for {split}')
        return available

    def segment(self, split, length, rng, available_only=False, filename=None, sample_rate=16000):
        if not isinstance(length, int) or length < 1:
            raise ValueError('length must be a positive integer')
        records = self.candidates(split, available_only)
        if filename is None:
            record = records[int(rng.integers(len(records)))]
        else:
            matches = [r for r in records if r.filename == filename]
            if not matches:
                raise ValueError(f'File is not available in {split}: {filename}')
            record = matches[0]
        path = self.audio_path(record)
        audio, sr, audio_hash = self._load_audio(path, sample_rate)
        # Random crop for short requests; circular repeat for requests longer than the source.
        for _ in range(32):
            offset = int(rng.integers(len(audio)-length+1 if length <= len(audio) else len(audio)))
            segment = audio[(np.arange(length)+offset) % len(audio)].astype(np.float64)
            if np.mean(segment**2) > 1e-12:
                break
        else:
            raise ValueError(f'No non-silent crop found in {record.filename}')
        metadata = dict(esc50_filename=record.filename, esc50_category=record.category,
                        esc50_fold=record.fold, esc50_src_file=record.src_file,
                        esc50_offset_samples=offset, esc50_resampled_samples=len(audio),
                        esc50_repeated=length > len(audio), esc50_original_sample_rate=sr,
                        esc50_audio_sha256=audio_hash,
                        esc50_catalog_sha256=self.catalog_sha256)
        return segment, metadata

    def summary(self):
        return {split: {'folds': folds,
                        'catalog': sum(r.fold in folds for r in self.records),
                        'excluded_source_conflicts': sum(r.fold in folds for r in self.excluded_records),
                        'local': sum(r.fold in folds and self.audio_path(r).is_file() for r in self.records)}
                for split, folds in SPLIT_FOLDS.items()}


def download_esc50(root, per_fold=2):
    """0 means full catalog; positive N downloads N files per fold for smoke tests."""
    if per_fold < 0:
        raise ValueError('per_fold must be >= 0')
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / 'download_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {
        'revision': ESC50_REVISION, 'base_url': BASE_URL, 'sha256': {}}
    if manifest['revision'] != ESC50_REVISION:
        raise ValueError('Existing download revision differs')

    def fetch(relative):
        path = root / relative
        if path.exists() and relative in manifest['sha256']:
            if hashlib.sha256(path.read_bytes()).hexdigest() != manifest['sha256'][relative]:
                raise ValueError(f'Local file changed: {relative}')
            return
        request = urllib.request.Request(BASE_URL + relative, headers={'User-Agent': 'morse-ai-milestone3'})
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
        if path.exists() and path.read_bytes() != payload:
            raise ValueError(f'Refusing to overwrite differing local file: {relative}')
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.part')
        temporary.write_bytes(payload)
        temporary.replace(path)
        manifest['sha256'][relative] = hashlib.sha256(payload).hexdigest()
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    for relative in ('meta/esc50.csv', 'LICENSE', 'README.md'):
        fetch(relative)
    manager = ESC50Manager(root)
    for fold in range(1, 6):
        records = sorted((r for r in manager.records if r.fold == fold), key=lambda r: r.filename)
        for record in records[:per_fold or len(records)]:
            fetch('audio/' + record.filename)
            info = sf.info(manager.audio_path(record))
            if info.frames == 0:
                raise ValueError(f'Empty WAV: {record.filename}')
        print(f'fold {fold}: download verified', flush=True)
    return manager.summary()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/ESC-50-master'))
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--per-fold', type=int, default=2, help='0=all; default=2 per fold')
    args = parser.parse_args()
    summary = download_esc50(args.root, args.per_fold) if args.download else ESC50Manager(args.root).summary()
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
