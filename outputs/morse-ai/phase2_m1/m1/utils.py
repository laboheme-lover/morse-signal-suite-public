from pathlib import Path
import csv
import hashlib
import json
import random
import numpy as np
import torch


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def write_csv(path, rows):
    with Path(path).open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def setup(config):
    random.seed(config['seed'])
    np.random.seed(config['seed'])
    torch.manual_seed(config['seed'])
    torch.set_num_threads(config['training']['threads'])
    torch.use_deterministic_algorithms(True)


def metrics(target, predicted, classes=36):
    matrix = np.zeros((classes, classes), dtype=np.int64)
    np.add.at(matrix, (target, predicted), 1)
    tp = np.diag(matrix)
    precision = np.divide(tp, matrix.sum(0), out=np.zeros(classes), where=matrix.sum(0) > 0)
    recall = np.divide(tp, matrix.sum(1), out=np.zeros(classes), where=matrix.sum(1) > 0)
    f1 = np.divide(2 * precision * recall, precision + recall, out=np.zeros(classes), where=(precision + recall) > 0)
    return {'accuracy': float(tp.sum()/matrix.sum()), 'macro_f1': float(f1.mean()),
            'precision': precision.tolist(), 'recall': recall.tolist(), 'f1': f1.tolist(),
            'support': matrix.sum(1).tolist(), 'confusion_matrix': matrix.tolist()}


def infer(model, loader):
    model.eval()
    total_loss, targets, guesses, probabilities, indices = 0., [], [], [], []
    with torch.inference_mode():
        for x, lengths, y, ids in loader:
            logits = model(x, lengths)
            total_loss += torch.nn.functional.cross_entropy(logits, y, reduction='sum').item()
            prob = logits.softmax(-1)
            targets.extend(y.tolist())
            guesses.extend(prob.argmax(-1).tolist())
            probabilities.extend(prob.max(-1).values.tolist())
            indices.extend(ids.tolist())
    result = metrics(targets, guesses)
    result['loss'] = total_loss / len(targets)
    return result, (targets, guesses, probabilities, indices)
