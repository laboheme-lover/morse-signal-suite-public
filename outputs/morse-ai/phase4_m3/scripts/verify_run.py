"""Verify saved results without reopening or retuning on Test audio."""
from pathlib import Path
import argparse
import csv
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.append(str(ROOT.parent/"phase2_m1"))
import numpy as np
import torch
from m1.utils import sha,metrics,write_json
from m1.data import PHASE1


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);args=ap.parse_args()
    run=args.run.resolve()
    def j(name):return json.loads((run/name).read_text(encoding='utf-8'))
    def c(name):
        with (run/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    done=j('training_complete.json');eval=j('evaluation/metrics.json');labels=j('labels.json');provenance=j('provenance.json')
    ck=torch.load(run/'best.pt',map_location='cpu',weights_only=True)
    history=c('history.csv');pred=c('evaluation/predictions.csv')
    best=min(history,key=lambda r:float(r['validation_loss']))
    assert int(best['epoch'])==done['best_epoch']==ck['epoch'],'Checkpoint selection mismatch'
    assert sha(run/'best.pt')==done['checkpoint_sha256']==eval['checkpoint_sha256'],'Model hash mismatch'
    assert ck['labels']==labels and ck['config']==j('config.json'),'Saved configuration mismatch'
    assert abs(ck['validation_loss']-j('validation_metrics.json')['loss'])<1e-8,'Validation replay mismatch'
    for name,expected in provenance['inputs'].items():
        assert sha(PHASE1/'metadata'/name)==expected,f'Input index changed: {name}'
    for name,expected in provenance['code_hashes'].items():
        assert sha(ROOT/name)==expected,f'Training code changed: {name}'
    assert sha(PHASE1/'metadata/test.csv')==eval['test_index_sha256'],'Test index changed'
    assert sha(PHASE1/'reports/test_manifest.csv')==eval['test_manifest_sha256'],'Test manifest changed'
    targets=[labels[r['true_label']] for r in pred];guesses=[labels[r['predicted_label']] for r in pred]
    recomputed=metrics(targets,guesses)
    assert recomputed['confusion_matrix']==eval['confusion_matrix'],'Prediction/matrix mismatch'
    for key in ('accuracy','macro_f1'):assert abs(recomputed[key]-eval[key])<1e-12,key
    assert len(pred)==eval['samples']==1620,'Incomplete evaluation'
    assert len({r['sample_id'] for r in pred})==len(pred),'Duplicate predictions'
    assert all(int(r['correct'])==int(r['true_label']==r['predicted_label']) for r in pred),'Incorrect flags'
    assert all(0<=float(r['prediction_probability'])<=1 for r in pred),'Invalid probabilities'
    result={'status':'PASS','best_epoch':ck['epoch'],'samples':len(pred),
            'checkpoint_and_indices_unchanged':True,'metrics_recomputed_from_predictions':True,
            'selection_is_minimum_validation_loss':True,'training_source_hashes_unchanged':True}
    write_json(run/'artifact_verification.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
