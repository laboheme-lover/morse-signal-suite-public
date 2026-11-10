"""Frozen-model diagnostic on reference-confirmed, shared-code real segments.

Selection is fixed before any M1--M4 prediction. This is deliberately a
rule-assisted subset, not an independent end-to-end Wabun benchmark.
"""
from pathlib import Path
import csv
import json
import sys
import numpy as np
import torch

PROJECT = Path(__file__).resolve().parents[2]
for folder in ('', 'phase1_data', 'phase2_m1', 'phase3_m2', 'phase4_m3', 'phase5_m4'):
    sys.path.insert(0, str(PROJECT / folder))
from m1.model import M1
from m2.model import M2
from m3.model import M3
from m4.model import M4
from m1.data import envelope, collate
from m1.utils import sha, write_json, write_csv, infer, setup
from src.test_protection import verify_lock
from audio_preprocessing import load_audio
from morse_segmentation import extract_character
from morse_table import MORSE_TABLE
from analyze_recording_body import select_body


def select_shared(rows, reference, reverse):
    body = select_body(rows)
    expected = [MORSE_TABLE[c] for c in reference]
    if [r['pattern'] for r in body] != expected:
        raise ValueError('Full body rule-code sequence does not exactly match reference')
    return [(r, c, reverse[code]) for r, c, code in zip(body, reference, expected) if code in reverse], len(body)


def main():
    out = PROJECT/'phase5_m4/reports/real_shared_20260922'
    out.mkdir(exist_ok=False)
    phase1 = PROJECT/'phase1_data'
    frozen = verify_lock(phase1)
    roots = ['phase2_m1', 'phase3_m2', 'phase4_m3', 'phase5_m4']
    models = [M1, M2, M3, M4]
    runs = [PROJECT/root/'runs'/f'm{i}_baseline_20260922' for i, root in enumerate(roots, 1)]
    checkpoints = [torch.load(p/'best.pt', map_location='cpu', weights_only=True) for p in runs]
    cfg = checkpoints[0]['config']
    setup(cfg)
    assert all(c['labels'] == checkpoints[0]['labels'] and c['config']['preprocessing'] == cfg['preprocessing'] for c in checkpoints)
    labels = checkpoints[0]['labels']
    ordered = sorted(labels, key=labels.get)
    table = json.loads((phase1/'config/morse_table.json').read_text(encoding='utf-8'))['entries']
    reverse = {v:k for k,v in table.items() if k in labels}
    baseline = PROJECT/'evaluation/real_collection_baseline'
    old = json.loads((baseline/'results.json').read_text(encoding='utf-8'))
    protected = [p/'best.pt' for p in runs] + [baseline/'results.json', phase1/'metadata/test.csv']
    selection, inventory, provenance = [], [], []
    # Make and save the complete selection before evaluating any model.
    for record in old:
        number = record['number']
        row = {'recording':number, 'status':'excluded', 'reason':'', 'body_units':0, 'shared_units':0}
        try:
            if record['status'] != 'scored':
                raise ValueError('Prior reference/body requires review')
            folder = baseline/f'{number:03d}'
            meta = json.loads((folder/'recording_metrics.json').read_text(encoding='utf-8'))
            audio = Path(meta['audio_path'])
            if sha(audio) != meta['audio_sha256']:
                raise ValueError('Audio changed since boundary extraction')
            with (folder/'segments.csv').open(encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f))
            ref = (folder/'reference_body.txt').read_text(encoding='utf-8')
            shared, count = select_shared(rows, ref, reverse)
            if not shared:
                raise ValueError('No shared symbols')
            row.update(status='included', body_units=count, shared_units=len(shared))
            selection.append((number, audio, shared))
            protected.extend([audio, folder/'segments.csv', folder/'reference_body.txt', folder/'reference_original.txt'])
            provenance.append({'recording':number, 'audio':str(audio), 'audio_sha256':sha(audio),
                               'reference_sha256':sha(folder/'reference_body.txt'), 'segments_sha256':sha(folder/'segments.csv')})
        except ValueError as exc:
            row['reason'] = str(exc)
        inventory.append(row)
    if not selection:
        raise ValueError('No eligible recordings')
    before = {str(p):sha(p) for p in protected}
    write_csv(out/'recording_selection.csv', inventory)
    write_json(out/'protocol.json', {'selection':'Before inference: previously scored body; exact full rule-code/reference sequence match; shared international A-Z/0-9 codes only',
        'limitations':['Rule-assisted selection favors recordings with successful segmentation.', 'Not unseen: this collection was used in earlier development.',
        'Not full-text Wabun accuracy or CER.', 'Same recording source and uneven class balance limit generalization.',
        'Saved reference normalization omits punctuation and separates dakuten. Unsupported Wabun codes excluded.',
        'No model retraining, carrier translation, threshold tuning, or checkpoint reselection.'], 'sources':provenance, 'protected_hashes':before})
    items, sample_rows = [], []
    for number, path, selected in selection:
        audio = load_audio(path)
        for row, kana, latin in selected:
            segment = {k:int(row[k]) for k in ('start_sample','end_sample')}
            feature = envelope(extract_character(audio, segment), 16000, cfg)
            items.append((feature, labels[latin], len(items)))
            sample_rows.append({'recording':number, 'segment_index':int(row['index']), 'start_seconds':row['start_seconds'],
                'end_seconds':row['end_seconds'], 'reference_wabun':kana, 'reference_code':MORSE_TABLE[kana], 'true_label':latin})
        print(f'Prepared real recording {number}: {len(selected)} shared symbols', flush=True)
    write_csv(out/'samples.csv', sample_rows)
    loader = torch.utils.data.DataLoader(items, batch_size=128, collate_fn=collate)
    results = []
    for i, (cls, ck, run) in enumerate(zip(models, checkpoints, runs), 1):
        model = cls(ck['config']); model.load_state_dict(ck['state_dict'])
        metrics, (target, pred, probability, ids) = infer(model, loader)
        metrics.update(model=f'M{i}', samples=len(items), recordings=len(selection), checkpoint_sha256=sha(run/'best.pt'))
        write_json(out/f'm{i}_metrics.json', metrics)
        predictions = [{**sample_rows[j], 'predicted_label':ordered[p], 'correct':int(t==p), 'probability':v}
            for t,p,v,j in zip(target,pred,probability,ids)]
        write_csv(out/f'm{i}_predictions.csv', predictions)
        per_record = []
        for number, _, _ in selection:
            subset = [r for r in predictions if r['recording']==number]
            per_record.append({'recording':number,'samples':len(subset),'accuracy':sum(r['correct'] for r in subset)/len(subset)})
        write_csv(out/f'm{i}_per_recording.csv', per_record)
        synthetic = json.loads((run/'evaluation/metrics.json').read_text(encoding='utf-8'))
        results.append({'model':f'M{i}', 'synthetic_accuracy':synthetic['accuracy'], 'real_shared_accuracy':metrics['accuracy'],
            'real_errors':sum(t!=p for t,p in zip(target,pred)), 'real_samples':len(items),
            'recording_macro_accuracy':float(np.mean([r['accuracy'] for r in per_record])),
            'observed_classes':sum(n>0 for n in metrics['support'])})
        print(f'M{i}: real shared accuracy={metrics["accuracy"]:.6%}', flush=True)
    assert all(sha(p)==value for p,value in before.items()), 'Protected input changed'
    assert len(verify_lock(phase1)) == len(frozen)
    write_json(out/'verification.json', {'status':'PASS', 'protected_files_unchanged':len(before), 'frozen_test_files_unchanged':len(frozen), 'model_updated':False})
    write_json(out/'summary.json', {'models':results, 'recordings':len(selection), 'excluded_recordings':len(old)-len(selection),
        'samples':len(items), 'selected_body_units':sum(r['body_units'] for r in inventory),
        'unsupported_body_units':sum(r['body_units']-r['shared_units'] for r in inventory)})
    write_csv(out/'comparison.csv', results)
    lines = ['# M1〜M4：実録音の共通符号による補助評価', '',
        f'採用録音 {len(selection)}件、共通符号 {len(items):,}区間。候補44件から、正解文と既存ルール検出の本文符号列が完全一致する録音を、M1〜M4の推論前に選択しました。', '',
        '|モデル|合成Test（1,620件）|実録音・共通符号の正解率|実録音の誤分類|', '|---|---:|---:|---:|']
    for r in results:
        lines.append(f'|{r["model"]}|{r["synthetic_accuracy"]:.2%}|{r["real_shared_accuracy"]:.2%}|{r["real_errors"]}|')
    lines += ['', '## 比較の意味と限界', '',
        '両方とも1符号の分類正解率ですが、母集団・クラス比率・ノイズ・速度・抽出条件が異なります。差をそのまま実環境での性能向上・低下とは解釈できません。',
        '和文「イ」の .- は国際モールスの A と同じ信号です。このように符号が完全に一致する区間だけを、正解文から英数字ラベルへ対応付けました。モデルの予測で正解ラベルを作っていません。',
        'ただし録音の選別と区間抽出にルールを使用しています。区間検出が失敗する難しい録音を除くため、全実録音より良い成績になり得ます。手作業で全境界を確認した評価ではありません。',
        '英数字36クラスに存在しない和文符号、未整理の正解文、全文の区間対応を確認できない録音は採点対象外です。除外理由と区間一覧はCSVに保存しています。和文全文の正解率やCERではありません。',
        '提供済みTaman録音は過去の開発で参照済みです。今回のM1〜M4は追加学習せず固定していますが、開発全体から独立した未見Testとは呼べません。',
        'モデルの再選択、学習、周波数変換、閾値調整はしていません。既存モデル・参照元・旧Testのハッシュ不変を確認しました。', '',
        '次の本評価では、開発で未使用の録音を別途用意し、1文字の境界と正解を確認してから固定します。和文全文の評価には、対応クラスの拡張と区間検出・モード処理を含む別の評価が必要です。']
    (out/'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
