"""Generate a small augmentation experiment; not a train/validation/test dataset."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from augment_audio import SPEED_RANGES, SNR_LEVELS, generate_sample
from generate_morse_audio import save_wav
from morse_table import get_morse_code, normalize_text


def generate_variations(output_dir, labels=('イ', 'モ', '゜'), repeats=1, seed=20260914):
    if not isinstance(repeats, int) or repeats < 1:
        raise ValueError('repeats must be a positive integer')
    labels = list(labels)
    if not labels:
        raise ValueError('At least one label is required')
    for label in labels:
        get_morse_code(label)
    labels = list(dict.fromkeys(normalize_text(label) for label in labels))
    seeds = np.random.SeedSequence(seed).spawn(len(labels) * len(SPEED_RANGES) * repeats)
    output_dir = Path(output_dir)
    # A run owns its directory. Never overwrite an earlier experiment.
    output_dir.mkdir(parents=True, exist_ok=False)
    rows = []
    group_index = 0
    for label in labels:
        for speed in SPEED_RANGES:
            for repeat in range(repeats):
                sample_seed = int(seeds[group_index].generate_state(1, dtype=np.uint64)[0])
                group_index += 1
                for snr in (None, *SNR_LEVELS):
                    noise_type = 'clean' if snr is None else 'white'
                    audio, row = generate_sample(label, speed, noise_type, snr, sample_seed)
                    name = f'{group_index:04d}_{noise_type}' + ('' if snr is None else f'_{snr}dB') + '.wav'
                    path = save_wav(output_dir / noise_type / name, audio)
                    row.update(filepath=path.relative_to(output_dir).as_posix(), split='unassigned',
                               base_sample_id=f'{group_index:04d}', repeat=repeat, master_seed=seed,
                               esc50_filename='', esc50_category='', esc50_fold='', esc50_src_file='',
                               wav_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                    row['timing_samples'] = json.dumps(row['timing_samples'], separators=(',', ':'))
                    rows.append(row)
    with (output_dir / 'metadata.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['filepath', 'split'] + [k for k in rows[0] if k not in ('filepath', 'split')])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path('data/variations/m2_demo'))
    parser.add_argument('--labels', nargs='+', default=['イ', 'モ', '゜'])
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--seed', type=int, default=20260914)
    args = parser.parse_args()
    try:
        rows = generate_variations(args.output_dir, args.labels, args.repeats, args.seed)
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    print(f'Generated {len(rows)} WAV files: {args.output_dir.resolve()}')
    print((args.output_dir / 'metadata.csv').resolve())


if __name__ == '__main__':
    main()
