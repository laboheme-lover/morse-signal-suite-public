"""Compare checkpoints on a fixed validation set; never reads test WAVs."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import torch
from torch.utils.data import DataLoader
from sklearn.metrics import accuracy_score,f1_score
from morse_dataset import MorseDataset
from morse_cnn import load_checkpoint


def compare(root,checkpoints,output_dir):
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    results=[]
    for path in checkpoints:
        model,config,checkpoint=load_checkpoint(path)
        dataset=MorseDataset(root,'validation',config)
        if dataset.label_to_index!=checkpoint['label_to_index']:
            raise ValueError('Mapping mismatch')
        loader=DataLoader(dataset,batch_size=64,shuffle=False,num_workers=0)
        predictions=[];targets=[]
        with torch.inference_mode():
            for x,y in loader:
                predictions.extend(model(x).argmax(1).tolist());targets.extend(y.tolist())
        groups=defaultdict(list)
        for i,row in enumerate(dataset.rows):
            groups['noise:'+row['noise_type']].append(i)
            groups['speed:'+row['speed']].append(i)
            if row['noise_type']!='clean':
                groups['snr:'+row['snr_db']].append(i)
            if row['noise_type']!='clean' and float(row['snr_db']) in (10,20):
                groups['snr:10_or_20'].append(i)
        metrics=dict(checkpoint=str(path),validation_samples=len(dataset),
                     accuracy=accuracy_score(targets,predictions),
                     macro_f1=f1_score(targets,predictions,labels=list(range(len(dataset.label_to_index))),average='macro',zero_division=0),
                     best_epoch=checkpoint['epoch'],test_used=False,conditions={})
        for group,indices in groups.items():
            metrics['conditions'][group]=dict(samples=len(indices),accuracy=sum(targets[i]==predictions[i] for i in indices)/len(indices))
        name=Path(path).parent.name
        (output_dir/f'{name}.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
        with (output_dir/f'{name}_validation_predictions.csv').open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=['filepath','label','target_index','prediction_index','correct','noise_type','snr_db','speed'])
            writer.writeheader()
            for row,target,prediction in zip(dataset.rows,targets,predictions):
                writer.writerow(dict(filepath=row['filepath'],label=row['label'],target_index=target,
                    prediction_index=prediction,correct=target==prediction,noise_type=row['noise_type'],snr_db=row['snr_db'],speed=row['speed']))
        print(json.dumps(metrics,indent=2),flush=True);results.append(metrics)
    (output_dir/'comparison.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('data/dataset/m4_300'))
    parser.add_argument('--checkpoints',nargs='+',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,default=Path('evaluation/improvement'))
    args=parser.parse_args()
    torch.set_num_threads(1)
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=1):
        compare(args.root,args.checkpoints,args.output_dir)
