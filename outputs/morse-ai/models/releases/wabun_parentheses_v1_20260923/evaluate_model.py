"""One fixed-checkpoint evaluation on the independent test split."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import DataLoader
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
from morse_dataset import MorseDataset
from morse_cnn import load_checkpoint


def metrics(targets,predictions,class_count):
    if not targets or len(targets)!=len(predictions):
        raise ValueError('Expected nonempty, aligned predictions')
    return dict(samples=len(targets),correct=sum(t==p for t,p in zip(targets,predictions)),
                accuracy=float(accuracy_score(targets,predictions)),
                macro_f1=float(f1_score(targets,predictions,labels=list(range(class_count)),average='macro',zero_division=0)))


def write_csv(path,rows,fields):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def evaluate(root,checkpoint_path,output_dir,selection_path):
    root=Path(root);checkpoint_path=Path(checkpoint_path);output_dir=Path(output_dir)
    selection=json.loads(Path(selection_path).read_text(encoding='utf-8'))
    model_hash=hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
    metadata_hash=hashlib.sha256((root/'metadata.csv').read_bytes()).hexdigest()
    if model_hash!=selection['sha256'] or metadata_hash!=selection['dataset_metadata_sha256']:
        raise ValueError('Model or dataset differs from frozen validation selection')
    model,config,checkpoint=load_checkpoint(checkpoint_path)
    dataset=MorseDataset(root,'test',config)
    if dataset.label_to_index!=checkpoint['label_to_index']:
        raise ValueError('Class mapping mismatch')
    output_dir.mkdir(parents=True,exist_ok=False)
    protocol=dict(split='test',checkpoint_sha256=model_hash,metadata_sha256=metadata_hash,
                  checkpoint=str(checkpoint_path),selection_split='validation',
                  frozen_validation_accuracy=selection['validation_accuracy'],
                  training_or_tuning_performed=False,preprocessing=config.to_dict())
    (output_dir/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    labels={index:label for label,index in dataset.label_to_index.items()}
    targets=[];predictions=[];confidence=[]
    with torch.inference_mode():
        for x,y in DataLoader(dataset,batch_size=64,shuffle=False,num_workers=0):
            probability=model(x).softmax(1)
            value,index=probability.max(1)
            targets.extend(y.tolist());predictions.extend(index.tolist());confidence.extend(value.tolist())
    result=metrics(targets,predictions,len(labels))
    result.update(protocol)
    rows=[];groups={name:defaultdict(list) for name in ('snr','noise','speed')}
    for i,(row,target,prediction,probability) in enumerate(zip(dataset.rows,targets,predictions,confidence)):
        rows.append(dict(filepath=row['filepath'],label=row['label'],prediction=labels[prediction],
                         correct=target==prediction,confidence=probability,snr_db=row['snr_db'],
                         noise_type=row['noise_type'],speed=row['speed'],
                         esc50_filename=row['esc50_filename'],esc50_src_file=row['esc50_src_file']))
        groups['snr'][row['snr_db'] if row['noise_type']!='clean' else 'clean'].append(i)
        groups['noise'][row['noise_type']].append(i)
        groups['speed'][row['speed']].append(i)
    write_csv(output_dir/'test_predictions.csv',rows,list(rows[0]))
    condition_tables={}
    for kind,group in groups.items():
        table=[]
        for condition,indices in group.items():
            scores=metrics([targets[i] for i in indices],[predictions[i] for i in indices],len(labels))
            table.append(dict(condition=condition,**scores))
        condition_tables[kind]=table
        write_csv(output_dir/f'{kind}_metrics.csv',table,list(table[0]))
    result['conditions']=condition_tables
    high_snr=[i for i,row in enumerate(dataset.rows) if row['noise_type']!='clean' and float(row['snr_db']) in (10,20)]
    result['snr_10_20']=metrics([targets[i] for i in high_snr],[predictions[i] for i in high_snr],len(labels))
    pairs=Counter((labels[t],labels[p]) for t,p in zip(targets,predictions) if t!=p)
    errors=[dict(label=t,prediction=p,count=count) for (t,p),count in pairs.most_common()]
    write_csv(output_dir/'common_errors.csv',errors,['label','prediction','count'])
    matrix=confusion_matrix(targets,predictions,labels=list(range(len(labels))))
    np.save(output_dir/'confusion_matrix.npy',matrix,allow_pickle=False)
    write_csv(output_dir/'class_mapping.csv',[dict(index=i,label=labels[i]) for i in range(len(labels))],['index','label'])
    plot_results(output_dir,matrix,condition_tables['snr'])
    result['errors']=len(targets)-result['correct']
    result['top_errors']=errors[:10]
    (output_dir/'test_metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    return result


def plot_results(output_dir,matrix,snr_rows):
    os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parent/'.cache/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(11,10),layout='constrained')
    mesh=ax.imshow(matrix,cmap='Blues',vmin=0)
    ax.set(xlabel='Predicted class index',ylabel='True class index',
           title='Independent test confusion matrix (class_mapping.csv contains labels)',
           xticks=np.arange(len(matrix)),yticks=np.arange(len(matrix)))
    ax.tick_params(labelsize=6)
    fig.colorbar(mesh,ax=ax,label='Count')
    fig.savefig(output_dir/'confusion_matrix.png',dpi=150);plt.close(fig)
    ordered=sorted((row for row in snr_rows if row['condition']!='clean'),key=lambda row:float(row['condition']),reverse=True)
    fig,ax=plt.subplots(figsize=(8,4),layout='constrained')
    ax.plot([row['condition'] for row in ordered],[100*row['accuracy'] for row in ordered],marker='o',label='Accuracy')
    ax.plot([row['condition'] for row in ordered],[100*row['macro_f1'] for row in ordered],marker='s',label='Macro F1 x 100')
    ax.set(xlabel='SNR (dB)',ylabel='Percent',ylim=(0,102),title='Independent test: white + ESC-50 noise')
    ax.legend();fig.savefig(output_dir/'performance_by_snr.png',dpi=150);plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('data/dataset/m4_300'))
    parser.add_argument('--checkpoint',type=Path,default=Path('models/improved_best.pt'))
    parser.add_argument('--selection',type=Path,default=Path('models/recommended_model.json'))
    parser.add_argument('--output-dir',type=Path,default=Path('evaluation/independent_test'))
    args=parser.parse_args()
    torch.set_num_threads(1)
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=1):
        evaluate(args.root,args.checkpoint,args.output_dir,args.selection)
