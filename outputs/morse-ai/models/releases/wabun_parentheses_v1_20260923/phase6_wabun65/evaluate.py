"""Evaluate all four already-frozen Wabun checkpoints on the original Test."""
from common import *
from src.test_protection import verify_lock
from collections import Counter

def main():
    runs=[ROOT/f'runs/m{i}_wabun65_20260922' for i in range(1,5)]
    # All models must finish and be fixed before any Test inference starts.
    for run in runs:
        done=json.loads((run/'training_complete.json').read_text())
        assert done['checkpoint_sha256']==sha(run/'best.pt')
        history=read_csv(run/'history.csv')
        selected=min(history,key=lambda r:float(r['validation_loss']))
        assert int(selected['epoch'])==done['best_epoch']
        provenance=json.loads((run/'provenance.json').read_text(encoding='utf-8'))
        for name,digest in provenance['inputs'].items():
            assert sha(ROOT/'metadata'/name)==digest,'Training index changed'
        for name,digest in provenance['code_hashes'].items():
            # Test code can be extended during training; executed training/model code cannot.
            if name in ('common.py','train.py') or name.startswith('../'):
                assert sha(ROOT/name)==digest,f'Training source changed: {name}'
    out=ROOT/'reports/comparison';out.mkdir(exist_ok=False)
    frozen=verify_lock(PROJECT/'phase1_data')
    checkpoints=[torch.load(run/'best.pt',weights_only=True,map_location='cpu') for run in runs]
    cfg=checkpoints[0]['config'];setup(cfg)
    def comparable(config):
        config=json.loads(json.dumps(config))
        config.pop('architecture',None)
        for field in ('branch_kernels','attention_size'):config['model'].pop(field,None)
        return config
    assert all(comparable(ck['config'])==comparable(cfg) for ck in checkpoints),'Common settings differ'
    data=PreparedDataset('test',cfg,evaluation=True)
    assert len(data)==2925 and len(data.labels)==65
    labels=sorted(data.labels,key=data.labels.get)
    loader=torch.utils.data.DataLoader(data,batch_size=128,collate_fn=collate)
    write_json(out/'protocol.json',{'checkpoint_hashes':{str(run):sha(run/'best.pt') for run in runs},
        'test_index_sha256':sha(ROOT/'metadata/test.csv'),'samples':len(data),'classes':65,
        'selection':'Minimum validation loss; all four training runs completed before Test',
        'scope':'Existing synthetic Wabun Test; not unseen real audio; no tuning after Test'})
    summary=[];all_predictions=[];groups=[]
    for name,ck,run in zip(MODELS,checkpoints,runs):
        assert ck['labels']==data.labels
        model=MODELS[name](ck['config']);model.load_state_dict(ck['state_dict'])
        result,(targets,pred,probs,ids)=infer(model,loader)
        result.update(samples=len(data),classes=65,checkpoint_sha256=sha(run/'best.pt'))
        folder=run/'evaluation';folder.mkdir(exist_ok=False)
        write_json(folder/'metrics.json',result)
        rows=[{**data.rows[i],'predicted_label':labels[p],'correct':int(t==p),'prediction_probability':v}
              for t,p,v,i in zip(targets,pred,probs,ids)]
        write_csv(folder/'predictions.csv',rows)
        write_csv(folder/'per_class.csv',[{'label':label,'support':result['support'][i],
            'recall':result['recall'][i],'precision':result['precision'][i],'f1':result['f1'][i]} for i,label in enumerate(labels)])
        for field in ('noise_type','snr_db','speed'):
            values=sorted(set(('clean' if field=='snr_db' and r['noise_type']=='clean' else r[field]) for r in rows))
            for value in values:
                subset=[r for r in rows if ('clean' if field=='snr_db' and r['noise_type']=='clean' else r[field])==value]
                groups.append({'model':name,'field':field,'condition':value,'samples':len(subset),'accuracy':sum(r['correct'] for r in subset)/len(subset)})
        done=json.loads((run/'training_complete.json').read_text())
        val=json.loads((run/'validation_metrics.json').read_text())
        summary.append({'model':name,'test_accuracy':result['accuracy'],'macro_f1':result['macro_f1'],
            'errors':sum(t!=p for t,p in zip(targets,pred)),'validation_accuracy':val['accuracy'],
            'best_epoch':done['best_epoch'],'parameters':done['parameters'],'training_seconds':done['elapsed_seconds']})
        all_predictions.append(pred)
        print(f'{name}: {result["accuracy"]:.6%}',flush=True)
    write_csv(out/'metrics.csv',summary);write_csv(out/'conditions.csv',groups)
    paired=[]
    for i in range(4):
        for j in range(i+1,4):
            counts=Counter((a==t,b==t) for a,b,t in zip(all_predictions[i],all_predictions[j],targets))
            paired.append({'left':f'M{i+1}','right':f'M{j+1}','both_correct':counts[True,True],
                'left_only':counts[True,False],'right_only':counts[False,True],'both_wrong':counts[False,False]})
    write_csv(out/'paired_outcomes.csv',paired)
    old=json.loads((PROJECT/'evaluation/independent_test/test_metrics.json').read_text(encoding='utf-8'))
    # Historical score is included only as context, with exact target file-set validation.
    oldrows=read_csv(PROJECT/'evaluation/independent_test/test_predictions.csv')
    oldpaths={str((PROJECT/'data/dataset/m4_300'/r['filepath']).resolve()):r for r in oldrows}
    assert set(oldpaths)=={r['filename'] for r in data.rows}
    assert all(oldpaths[r['filename']]['label']==r['label'] for r in data.rows)
    assert sum(r['correct']=='True' for r in oldrows)==old['correct']
    write_json(out/'historical_baseline.json',{'source':'evaluation/independent_test','checkpoint_sha256':old['checkpoint_sha256'],
        'accuracy':old['accuracy'],'macro_f1':old['macro_f1'],'errors':old['errors'],
        'same_test_files_and_labels':True,'note':'Historical 65-class mel-CNN, not a new rerun; different architecture, frontend and training policy'})
    protected=json.loads((ROOT/'reports/protected_files.json').read_text(encoding='utf-8'))
    assert all(sha(p)==h for p,h in protected.items())
    assert len(verify_lock(PROJECT/'phase1_data'))==len(frozen)
    # Recompute all aggregate metrics from saved predictions.
    for run in runs:
        rows=read_csv(run/'evaluation/predictions.csv')
        recomputed=metrics([data.labels[r['label']] for r in rows],[data.labels[r['predicted_label']] for r in rows],65)
        saved=json.loads((run/'evaluation/metrics.json').read_text())
        assert recomputed['confusion_matrix']==saved['confusion_matrix']
        assert recomputed['accuracy']==saved['accuracy'] and recomputed['macro_f1']==saved['macro_f1']
    write_json(out/'verification.json',{'status':'PASS','frozen_test_files_unchanged':len(frozen),
        'protected_files_unchanged':len(protected),'classes':65,'test_samples':2925,
        'same_test_as_historical':True,'all_saved_metrics_recomputed':True,'all_models_selected_by_validation':True})

if __name__=='__main__':main()
