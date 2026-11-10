"""Select checkpoint on augmentation-validation only; evaluate test once afterward."""
import json,time,random,hashlib,csv,sys
from pathlib import Path
import numpy as np,torch
from torch import nn
from model import MODELS
from extract import OUT,ROOT,sha

def rule_predict(f,duration,reverse):
 # Same isolated-character task; known capture rate, dot length estimated from pulses.
 signal=f[:,0]-f[:,2];lo,hi=np.percentile(signal,[5,95])
 if hi-lo<5:return -1
 for _ in range(10):
  a=signal[signal<=(lo+hi)/2];b=signal[signal>(lo+hi)/2]
  if len(a)==0 or len(b)==0:return -1
  lo,hi=float(np.median(a)),float(np.median(b))
 state=signal>(lo+hi)/2;edges=np.r_[0,np.flatnonzero(np.diff(state))+1,len(state)]
 on=[(b-a)/30 for a,b in zip(edges[:-1],edges[1:]) if state[a]]
 gaps=[(b-a)/30 for a,b in zip(edges[:-1],edges[1:]) if not state[a] and a>0 and b<len(state)]
 if not on:return -1
 unit=float(np.median(gaps)) if gaps else .3
 if not .07<=unit<=.9:return -1
 if any(min(abs(d-unit),abs(d-3*unit))>max(2/30,unit*.4) for d in on):return -1
 return reverse.get(''.join('.' if d<2*unit else '-' for d in on),-1)

def main():
 torch.set_num_threads(4);torch.manual_seed(130);np.random.seed(130);random.seed(130)
 config=json.loads((OUT/'dataset/config.json').read_text(encoding='utf-8'));z=np.load(OUT/'dataset/features.npz')
 x=torch.from_numpy(z['x']);y=torch.from_numpy(z['y']).long();split=z['split'];condition=z['condition']
 (OUT/'models').mkdir(exist_ok=True)
 metrics={};histories={};predictions={}
 for name,cls in MODELS.items():
  torch.manual_seed(130)
  model=cls();opt=torch.optim.AdamW(model.parameters(),lr=.002,weight_decay=.001)
  train=torch.utils.data.TensorDataset(x[split==0],y[split==0]);loader=torch.utils.data.DataLoader(train,batch_size=64,shuffle=True,generator=torch.Generator().manual_seed(130))
  best=float('inf');stale=0;history=[];begin=time.time()
  for epoch in range(1,41):
   model.train();loss_sum=0
   for a,b in loader:
    opt.zero_grad(set_to_none=True);loss=nn.functional.cross_entropy(model(a),b);loss.backward();nn.utils.clip_grad_norm_(model.parameters(),5.);opt.step();loss_sum+=loss.item()*len(b)
   model.eval()
   with torch.no_grad():
    logits=torch.cat([model(a) for a in x[split==1].split(128)]);vl=nn.functional.cross_entropy(logits,y[split==1]).item();acc=(logits.argmax(1)==y[split==1]).float().mean().item()
   history.append(dict(epoch=epoch,train_loss=loss_sum/len(train),validation_loss=vl,validation_accuracy=acc))
   if vl<best-1e-5:
    best=vl;stale=0
    torch.save(dict(state_dict=model.state_dict(),model=name,classes=config['classes'],epoch=epoch,seed=130,input_channels=5,input_steps=256,training_scope='augmentation development; same source clips across splits',dataset_sha256=sha(OUT/'dataset/features.npz')),OUT/'models'/f'{name}.pt')
   else:stale+=1
   print(name,epoch,round(vl,4),round(acc,4),flush=True)
   if stale>=8:break
  ckpt=torch.load(OUT/'models'/f'{name}.pt',weights_only=False,map_location='cpu');model.load_state_dict(ckpt['state_dict']);model.eval()
  with torch.no_grad():pred=torch.cat([model(a).argmax(1) for a in x.split(128)]).numpy()
  predictions[name]=pred;histories[name]=history
  metrics[name]=dict(parameters=sum(p.numel() for p in model.parameters()),best_epoch=ckpt['epoch'],seconds=time.time()-begin,validation_accuracy=float(np.mean(pred[split==1]==z['y'][split==1])))
 # Rule baseline consumes the exact same augmented pixels' extracted brightness.
 sys.path.insert(0,str(ROOT/'outputs/morse-ai'));from morse_table import MORSE_TABLE
 reverse={MORSE_TABLE[label]:i for i,label in enumerate(config['classes'])}
 raw=z['raw'];offset=z['offsets'];pred=np.array([rule_predict(raw[a:b],(b-a)/30,reverse) for a,b in zip(offset[:-1],offset[1:])]);predictions['rule']=pred
 rows=[]
 for name,pred in predictions.items():
  for si in (1,2,3):
   for ci in range(-1,len(config['conditions'])):
    mask=(split==si)&((condition==ci) if ci>=0 else True);n=int(mask.sum());correct=int(sum(pred[mask]==z['y'][mask]))
    rows.append(dict(model=name,split=config['split_names'][si],condition='ALL' if ci<0 else config['conditions'][ci],n=n,correct=correct,accuracy=correct/n,rejected=int(sum(pred[mask]<0))))
 with (OUT/'evaluation.csv').open('w',encoding='utf-8-sig',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 np.savez_compressed(OUT/'predictions.npz',truth=z['y'],split=split,condition=condition,**predictions)
 selected=max(metrics,key=lambda n:metrics[n]['validation_accuracy'])
 result=dict(selected_development_model=selected,metrics=metrics,history=histories,results=rows,independent_recording_test=False,real_weather_test=False)
 (OUT/'training_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print('COMPLETE selected',selected,flush=True)

if __name__=='__main__':main()
