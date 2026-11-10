"""Milestone 6: train on train split and select best model using validation only."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import random
import time
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader,TensorDataset
from audio_preprocessing import PreprocessConfig
from morse_dataset import MorseDataset
from morse_cnn import MorseCNN,load_checkpoint


def run_epoch(model,loader,criterion,optimizer=None):
    training=optimizer is not None
    model.train(training)
    loss_sum=0.; correct=0; count=0
    with torch.set_grad_enabled(training):
        for x,y in loader:
            if training:
                optimizer.zero_grad(set_to_none=True)
            logits=model(x)
            loss=criterion(logits,y)
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite loss')
            if training:
                loss.backward()
                optimizer.step()
            loss_sum+=float(loss.detach())*len(y)
            correct+=int((logits.argmax(1)==y).sum())
            count+=len(y)
    if count==0:
        raise ValueError('Empty epoch')
    return {'loss':loss_sum/count,'accuracy':correct/count,'samples':count}


def cache_dataset(dataset):
    samples=[dataset[i] for i in range(len(dataset))]
    return TensorDataset(torch.stack([x for x,_ in samples]),torch.stack([y for _,y in samples]))


def train(root,output_dir,epochs=20,batch_size=32,learning_rate=1e-3,seed=20260914,cache=False,
          variant='classic',temporal_bins=16,dropout=0.3,init_checkpoint=None):
    if type(epochs) is not int or epochs<1 or type(batch_size) is not int or batch_size<1:
        raise ValueError('epochs and batch_size must be positive integers')
    if not np.isfinite(learning_rate) or learning_rate<=0:
        raise ValueError('learning_rate must be finite and positive')
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    root=Path(root).resolve();output_dir=Path(output_dir)
    config=PreprocessConfig()
    # Deliberately never construct a test Dataset or DataLoader here.
    training=MorseDataset(root,'train',config)
    validation=MorseDataset(root,'validation',config)
    if training.label_to_index!=validation.label_to_index:
        raise ValueError('train/validation label mapping mismatch')
    mapping=training.label_to_index
    initialized_model=None
    if init_checkpoint is not None:
        initialized_model,initial_config,initial_state=load_checkpoint(init_checkpoint)
        if initial_state['label_to_index']!=mapping or initial_config!=config:
            raise ValueError('Initialization checkpoint data/preprocessing mismatch')
        expected=dict(num_classes=len(mapping),variant=variant,temporal_bins=temporal_bins,dropout=dropout)
        if initialized_model.model_config!=expected:
            raise ValueError('Initialization checkpoint model configuration differs from requested options')
    output_dir.mkdir(parents=True,exist_ok=False)
    spec=dict(epochs=epochs,batch_size=batch_size,learning_rate=learning_rate,seed=seed,
              variant=variant,temporal_bins=temporal_bins,dropout=dropout,
              init_checkpoint=str(Path(init_checkpoint).resolve()) if init_checkpoint else None,
              init_checkpoint_sha256=hashlib.sha256(Path(init_checkpoint).read_bytes()).hexdigest() if init_checkpoint else None,
              cache=cache,device='cpu',num_workers=0,torch_threads=torch.get_num_threads(),
              dataset_root=str(root),torch_version=str(torch.__version__),
              metadata_sha256=hashlib.sha256((root/'metadata.csv').read_bytes()).hexdigest(),
              train_samples=len(training),validation_samples=len(validation),test_used=False,
              preprocessing=config.to_dict(),label_to_index=mapping,
              source_sha256={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                             for name in ('train.py','morse_cnn.py','morse_dataset.py','audio_preprocessing.py')})
    (output_dir/'run_config.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8')
    (output_dir/'label_mapping.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2),encoding='utf-8')
    (output_dir/'preprocessing.json').write_text(json.dumps(config.to_dict(),indent=2),encoding='utf-8')
    started=time.perf_counter()
    if cache:
        print('Caching train/validation tensors (no test data)',flush=True)
        training=cache_dataset(training);validation=cache_dataset(validation)
    shuffle_generator=torch.Generator().manual_seed(seed)
    train_loader=DataLoader(training,batch_size=batch_size,shuffle=True,generator=shuffle_generator,num_workers=0)
    train_eval_loader=DataLoader(training,batch_size=batch_size,shuffle=False,num_workers=0)
    val_loader=DataLoader(validation,batch_size=batch_size,shuffle=False,num_workers=0)
    model=initialized_model if initialized_model is not None else MorseCNN(len(mapping),temporal_bins,dropout,variant)
    criterion=nn.CrossEntropyLoss()
    optimizer=torch.optim.Adam(model.parameters(),lr=learning_rate)
    baseline={'train':run_epoch(model,train_eval_loader,criterion),'validation':run_epoch(model,val_loader,criterion)}
    print(f'Baseline: {baseline}',flush=True)
    best_accuracy=-1.;best_epoch=None;history=[]
    with (output_dir/'history.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['epoch','train_loss','train_accuracy','validation_loss','validation_accuracy','epoch_seconds'])
        writer.writeheader()
        for epoch in range(1,epochs+1):
            epoch_start=time.perf_counter()
            train_metrics=run_epoch(model,train_loader,criterion,optimizer)
            val_metrics=run_epoch(model,val_loader,criterion)
            row=dict(epoch=epoch,train_loss=train_metrics['loss'],train_accuracy=train_metrics['accuracy'],
                     validation_loss=val_metrics['loss'],validation_accuracy=val_metrics['accuracy'],
                     epoch_seconds=time.perf_counter()-epoch_start)
            writer.writerow(row);stream.flush();history.append(row)
            if val_metrics['accuracy']>best_accuracy:
                best_accuracy=val_metrics['accuracy'];best_epoch=epoch
                checkpoint=dict(format_version='m6-v1',model_config=model.model_config,
                    model_state_dict=model.state_dict(),optimizer_state_dict=optimizer.state_dict(),
                    epoch=epoch,validation_metrics=val_metrics,label_to_index=mapping,
                    preprocessing=config.to_dict(),run_config=spec)
                temporary=output_dir/'best_model.pt.tmp'
                torch.save(checkpoint,temporary);temporary.replace(output_dir/'best_model.pt')
            print(f"Epoch {epoch:02d}/{epochs}: loss={row['train_loss']:.4f} acc={row['train_accuracy']:.3%}; "
                  f"val_loss={row['validation_loss']:.4f} val_acc={row['validation_accuracy']:.3%}; best={best_epoch}",flush=True)
    final_train=run_epoch(model,train_eval_loader,criterion)
    best_model,loaded_config,checkpoint=load_checkpoint(output_dir/'best_model.pt')
    reloaded_metrics=run_epoch(best_model,val_loader,criterion)
    if checkpoint['epoch']!=best_epoch or abs(reloaded_metrics['accuracy']-best_accuracy)>1e-12 or loaded_config!=config:
        raise ValueError('Checkpoint round-trip verification failed')
    summary=dict(status='complete',baseline=baseline,final_train_eval=final_train,
                 best_epoch=best_epoch,best_validation=reloaded_metrics,
                 train_loss_decreased=final_train['loss']<baseline['train']['loss'],
                 train_accuracy_increased=final_train['accuracy']>baseline['train']['accuracy'],
                 parameter_count=sum(p.numel() for p in model.parameters()),
                 checkpoint_reload_verified=True,test_used=False,elapsed_seconds=time.perf_counter()-started)
    (output_dir/'training_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('data/dataset/m4_smoke'))
    parser.add_argument('--output-dir',type=Path,default=Path('models/m6_smoke'))
    parser.add_argument('--epochs',type=int,default=20)
    parser.add_argument('--batch-size',type=int,default=32)
    parser.add_argument('--lr',type=float,default=1e-3)
    parser.add_argument('--seed',type=int,default=20260914)
    parser.add_argument('--threads',type=int,default=4)
    parser.add_argument('--cache',action='store_true',help='Cache train/validation tensors in RAM; useful for small datasets')
    parser.add_argument('--variant',choices=['classic','temporal'],default='classic')
    parser.add_argument('--temporal-bins',type=int,default=16)
    parser.add_argument('--dropout',type=float,default=0.3)
    parser.add_argument('--init-checkpoint',type=Path,help='Fine-tune saved weights with a fresh Adam optimizer')
    args=parser.parse_args()
    if args.threads<1:
        parser.error('--threads must be >= 1')
    torch.set_num_threads(args.threads)
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=args.threads):
        train(args.root,args.output_dir,args.epochs,args.batch_size,args.lr,args.seed,args.cache,
              args.variant,args.temporal_bins,args.dropout,args.init_checkpoint)


if __name__=='__main__':
    main()
