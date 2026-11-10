"""Separate, immutable evaluation of the already-selected checkpoint."""
from pathlib import Path
import argparse
import json
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT.parent/"phase2_m1"))
import torch
from m1.data import PreparedDataset, collate, PHASE1
from m4.model import M4
from m1.utils import sha, setup, write_json, write_csv, infer, metrics
from src.test_protection import verify_lock


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', type=Path, required=True)
    args = ap.parse_args()
    run = args.run.resolve()
    completed = json.loads((run/'training_complete.json').read_text(encoding='utf-8'))
    if completed['checkpoint_sha256'] != sha(run/'best.pt'):
        raise ValueError('Selected checkpoint changed')
    if (run/'evaluation').exists():
        raise FileExistsError('Evaluation already exists; do not overwrite')
    frozen = verify_lock(PHASE1)
    checkpoint = torch.load(run/'best.pt', map_location='cpu', weights_only=True)
    cfg = checkpoint['config']
    setup(cfg)
    data = PreparedDataset('test', cfg, evaluation=True)
    if data.labels != checkpoint['labels']:
        raise ValueError('Evaluation labels differ from checkpoint')
    model = M4(cfg)
    model.load_state_dict(checkpoint['state_dict'])
    loader = torch.utils.data.DataLoader(data, batch_size=cfg['training']['batch_size'], collate_fn=collate)
    started = time.perf_counter()
    result, (targets, guesses, confidence, indices) = infer(model, loader)
    result.update({'samples': len(data), 'frozen_test_files_verified': len(frozen),
        'checkpoint_sha256': sha(run/'best.pt'), 'test_index_sha256': sha(PHASE1/'metadata/test.csv'),
        'test_manifest_sha256': sha(PHASE1/'reports/test_manifest.csv'),
        'inference_seconds': time.perf_counter()-started, 'scope': 'Existing synthetic single-symbol 36-class Test; not unseen real recordings'})
    labels = sorted(data.labels, key=data.labels.get)
    rows = []
    for true, pred, prob, i in zip(targets, guesses, confidence, indices):
        meta = data.rows[i]
        rows.append({'sample_id': meta['sample_id'], 'filename': meta['filename'], 'true_label': labels[true],
                     'predicted_label': labels[pred], 'correct': int(true == pred), 'prediction_probability': prob,
                     'noise_type': meta['noise_type'], 'snr_db': meta['snr_db'], 'frequency': meta['frequency']})
    groups = []
    for field in ('noise_type', 'snr_db'):
        for value in sorted({r[field] for r in rows}):
            selected = [i for i, r in enumerate(rows) if r[field] == value]
            groups.append({'field': field, 'value': value or 'clean', 'samples': len(selected),
                'accuracy': sum(targets[i] == guesses[i] for i in selected)/len(selected)})
    verify_lock(PHASE1)
    out = run/'evaluation'
    out.mkdir(exist_ok=False)
    write_json(out/'metrics.json', result)
    write_csv(out/'predictions.csv', rows)
    write_csv(out/'by_condition.csv', groups)
    write_csv(out/'per_class.csv', [{'label': label, **{key:result[key][i] for key in ('precision','recall','f1','support')}} for i,label in enumerate(labels)])
    write_csv(out/'confusion_matrix.csv', [{'true_label':label, **dict(zip(labels,result['confusion_matrix'][i]))} for i,label in enumerate(labels)])
    print(json.dumps({k:v for k,v in result.items() if not isinstance(v,list)}, indent=2), flush=True)


if __name__ == '__main__':
    main()
