"""Milestone 3: mix ESC-50 noise into single-character Morse at a requested SNR."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from augment_audio import generate_sample, mix_at_snr, SNR_LEVELS
from esc50_manager import ESC50Manager, SPLIT_FOLDS
from generate_morse_audio import save_wav


def generate_esc50_sample(manager, label, speed, split, snr_db, seed=0, noise_seed=1,
                          available_only=False, filename=None):
    if snr_db not in SNR_LEVELS:
        raise ValueError('SNR must be 20, 10, 5, 0, or -5')
    clean, metadata = generate_sample(label, speed, seed=seed)
    noise, provenance = manager.segment(split, len(clean), np.random.default_rng(noise_seed),
                                         available_only=available_only, filename=filename)
    audio, signal, scaled_noise, gain = mix_at_snr(clean, noise, snr_db)
    metadata.update(provenance)
    metadata.update(split=split, noise_type='esc50', snr_db=snr_db, noise_seed=noise_seed,
                    mix_gain=gain, measured_snr_db=float(10*np.log10(np.mean(signal**2)/np.mean(scaled_noise**2))),
                    generator_version='m3-v1', esc50_available_only=available_only)
    return audio, metadata


def generate_demo(manager, output_dir, available_only=False, seed=20260914):
    # Preflight all splits before creating the output directory.
    candidates = {split: manager.candidates(split, available_only) for split in SPLIT_FOLDS}
    # Bound the demo to two clips per fold, even if the full dataset is installed.
    records = [(split, record) for split, pool in candidates.items()
               for fold in SPLIT_FOLDS[split] for record in [r for r in pool if r.fold == fold][:2]]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    rows = []
    for index, (split, record) in enumerate(records):
        for snr in SNR_LEVELS:
            audio, metadata = generate_esc50_sample(manager, 'イ', 'normal', split, snr,
                                                    seed+index, seed+1000+index,
                                                    available_only, record.filename)
            path = save_wav(output_dir/split/f'{index:03d}_{snr}dB.wav', audio)
            metadata.update(filepath=path.relative_to(output_dir).as_posix(),
                            base_sample_id=f'{split}-{index:03d}',
                            wav_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            metadata['timing_samples'] = json.dumps(metadata['timing_samples'], separators=(',', ':'))
            rows.append(metadata)
    with (output_dir/'metadata.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['filepath']+[k for k in rows[0] if k != 'filepath'])
        writer.writeheader()
        writer.writerows(rows)
    print(f'Generated {len(rows)} WAV files: {output_dir.resolve()}')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--esc50-root', type=Path, default=Path('data/ESC-50-master'))
    parser.add_argument('--output-dir', type=Path, default=Path('data/esc50_demo'))
    parser.add_argument('--available-only', action='store_true', help='Explicitly allow a partial local ESC-50 download')
    parser.add_argument('--seed', type=int, default=20260914)
    args = parser.parse_args()
    generate_demo(ESC50Manager(args.esc50_root), args.output_dir, args.available_only, args.seed)


if __name__ == '__main__':
    main()
