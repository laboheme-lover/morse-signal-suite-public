"""Adopted M3, baseline, Wabun punctuation; original CNN retained."""
from pathlib import Path
from types import SimpleNamespace
import hashlib,json,sys,numpy as np,torch
P=Path(__file__).resolve().parent;sys.path[:0]=[str(P/'phase6_wabun65')]
from common import MODELS,envelope,collate,setup
from audio_preprocessing import PreprocessConfig,compute_mel_db
from predict_sequence import SequencePredictor
RELEASE=P/'models/releases/wabun_parentheses_v1_20260923'
class M3Single:
 def __init__(self):
  self.checkpoint_path=RELEASE/'phase6_wabun65/runs/m3_wabun65_20260922/best.pt'
  manifest=json.loads((RELEASE/'release_manifest.json').read_text(encoding='utf-8'));rel=self.checkpoint_path.relative_to(RELEASE).as_posix()
  self.checkpoint_sha256=hashlib.sha256(self.checkpoint_path.read_bytes()).hexdigest();assert self.checkpoint_sha256==manifest['files'][rel]
  ck=torch.load(self.checkpoint_path,map_location='cpu',weights_only=True);self.model_config=ck['config'];setup(self.model_config)
  self.model=MODELS['M3'](self.model_config).eval();self.model.load_state_dict(ck['state_dict']);self.labels=sorted(ck['labels'],key=ck['labels'].get);self.config=PreprocessConfig()
 def predict_audio(self,audio,top_k=3):
  f=envelope(np.asarray(audio),16000,self.model_config);x,lengths,_,_=collate([(f,0,0)])
  with torch.inference_mode():values,classes=self.model(x,lengths).softmax(-1)[0].topk(top_k)
  candidates=[dict(rank=i+1,label=self.labels[c],probability=v) for i,(c,v) in enumerate(zip(classes.tolist(),values.tolist()))]
  mel=compute_mel_db(audio,self.config)
  return dict(prediction=candidates[0]['label'],confidence=candidates[0]['probability'],top_k=candidates,mel=mel,mel_shape=list(mel.shape))
class M3SequencePredictor(SequencePredictor):
 def __init__(self):self.single=M3Single()
 def predict_audio(self,audio,**kwargs):
  kwargs['mixed_mode']=False;kwargs['frequency_hz']=None;kwargs['target_frequency_hz']=None;kwargs['character_gap_seconds']=None
  result=super().predict_audio(audio,**kwargs);result.update(model='M3',frontend='baseline',preprocessing=self.single.model_config['preprocessing'],text_policy='wabun-parentheses-v1',mel_role='display only; M3 uses envelope features');return result
