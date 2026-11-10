"""Train/validation only. Test data and manifests are never opened here."""
from pathlib import Path
import argparse
import json
import platform
import sys
import time
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT.parent/"phase2_m1"))
import numpy as np
import scipy
import soundfile
import torch
from m1.data import PreparedDataset, collate, PHASE1
from m4.model import M4
from m1.utils import setup, sha, write_json, write_csv, infer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', type=Path, default=ROOT/'config/m4.json')
    ap.add_argument('--run-name', default=datetime.now().strftime('m4_%Y%m%d_%H%M%S'))
    args = ap.parse_args()
    if Path(args.run_name).name != args.run_name or args.run_name in ('.', '..'):
        raise ValueError('Run name must be a simple directory name')
    cfg = json.loads(args.config.read_text(encoding='utf-8'))
    setup(cfg)
    run = ROOT/'runs'/args.run_name
    run.mkdir(parents=True, exist_ok=False)
    write_json(run/'config.json', cfg)
    provenance = {'started_at': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(),
                  'torch': str(torch.__version__), 'numpy': np.__version__, 'scipy': scipy.__version__,
                  'soundfile': soundfile.__version__, 'device': 'cpu', 'selection': cfg['selection'],
                  'inputs': {name: sha(PHASE1/'metadata'/name) for name in ('train.csv','validation.csv','label_mapping.json')},
                  'code_hashes': {str(p.relative_to(ROOT)): sha(p) for d in ('m4','scripts') for p in (ROOT/d).glob('*.py')}}
    provenance['code_hashes'].update({f'../phase2_m1/m1/{p.name}':sha(p) for p in (ROOT.parent/'phase2_m1/m1').glob('*.py')})
    provenance['code_hashes'].update({f'../phase4_m3/m3/{p.name}':sha(p) for p in (ROOT.parent/'phase4_m3/m3').glob('*.py')})
    write_json(run/'provenance.json', provenance)
    started = time.perf_counter()
    train = PreparedDataset('train', cfg)
    val = PreparedDataset('validation', cfg)
    if len(train.labels) != cfg['model']['classes'] or train.labels != val.labels:
        raise ValueError('Class mapping mismatch')
    write_json(run/'labels.json', train.labels)
    generator = torch.Generator().manual_seed(cfg['seed'])
    train_loader = torch.utils.data.DataLoader(train, batch_size=cfg['training']['batch_size'], shuffle=True,
        generator=generator, num_workers=0, collate_fn=collate)
    val_loader = torch.utils.data.DataLoader(val, batch_size=cfg['training']['batch_size'], collate_fn=collate)
    model = M4(cfg)
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg['training']['learning_rate'], weight_decay=cfg['training']['weight_decay'])
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=.5, patience=2)
    print(f'Run {run.name}: train={len(train)}, validation={len(val)}, parameters={sum(p.numel() for p in model.parameters())}', flush=True)
    history, best_loss, stale, best_epoch = [], float('inf'), 0, 0
    for epoch in range(1, cfg['training']['epochs'] + 1):
        ep_start = time.perf_counter()
        model.train()
        total_loss = total_correct = 0
        for x, lengths, y, _ in train_loader:
            optimizer.zero_grad(set_to_none=True)
            logits = model(x, lengths)
            loss = torch.nn.functional.cross_entropy(logits, y)
            if not torch.isfinite(loss):
                raise ValueError('Non-finite training loss')
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg['training']['gradient_clip'])
            optimizer.step()
            total_loss += loss.item()*len(y)
            total_correct += (logits.argmax(-1) == y).sum().item()
        result, _ = infer(model, val_loader)
        row = {'epoch': epoch, 'train_loss': total_loss/len(train), 'train_accuracy': total_correct/len(train),
               'validation_loss': result['loss'], 'validation_accuracy': result['accuracy'],
               'validation_macro_f1': result['macro_f1'], 'lr': optimizer.param_groups[0]['lr'],
               'seconds': time.perf_counter()-ep_start}
        history.append(row)
        write_csv(run/'history.csv', history)
        if result['loss'] < best_loss:
            best_loss, best_epoch, stale = result['loss'], epoch, 0
            checkpoint = {'model_type':'M4', 'state_dict': model.state_dict(), 'config': cfg, 'labels': train.labels, 'epoch': epoch,
                          'validation_loss': best_loss, 'validation_accuracy': result['accuracy'],
                          'train_index_sha256': provenance['inputs']['train.csv'],
                          'validation_index_sha256': provenance['inputs']['validation.csv']}
            torch.save(checkpoint, run/'best.pt')
        else:
            stale += 1
        scheduler.step(result['loss'])
        print(json.dumps(row), flush=True)
        if stale >= cfg['training']['patience']:
            break
    # Restore the model selected exclusively by validation loss.
    checkpoint = torch.load(run/'best.pt', map_location='cpu', weights_only=True)
    model.load_state_dict(checkpoint['state_dict'])
    val_result, _ = infer(model, val_loader)
    write_json(run/'validation_metrics.json', val_result)
    write_json(run/'training_complete.json', {'status': 'complete', 'best_epoch': best_epoch,
        'epochs_completed': len(history), 'elapsed_seconds': time.perf_counter()-started,
        'train_samples': len(train), 'validation_samples': len(val), 'parameters': sum(p.numel() for p in model.parameters()),
        'checkpoint_sha256': sha(run/'best.pt'), 'selection': cfg['selection']})
    print(f'TRAINING COMPLETE: {run}', flush=True)


if __name__ == '__main__':
    main()
