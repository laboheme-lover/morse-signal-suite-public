"""Freeze adopted weights for Java inference; training and source release unchanged."""
from pathlib import Path
import hashlib,json,struct,sys
import numpy as np
import torch
R=Path(__file__).resolve().parents[1]
release=R.parent/'optical-ml/releases/optical-cnn-adaptive-v2-20261013'
source=release/'cnn.pt'
sha=hashlib.sha256(source.read_bytes()).hexdigest()
assert sha==(release/'cnn.sha256').read_text().strip()
ck=torch.load(source,map_location='cpu',weights_only=False)
assert ck['model']=='cnn' and len(ck['classes'])==65
dest=R/'app/src/main/assets';dest.mkdir(exist_ok=True)
keys=['features.0.weight','features.0.bias','features.2.weight','features.2.bias','head.1.weight','head.1.bias','head.4.weight','head.4.bias']
with (dest/'optical_cnn.bin').open('wb') as f:
 f.write(struct.pack('>ii',0x4f434e31,65))
 for label in ck['classes']:
  b=label.encode('utf-8');f.write(struct.pack('>H',len(b))+b)
 for key in keys:
  a=ck['state_dict'][key].numpy().astype('>f4');f.write(struct.pack('>i',a.size));f.write(a.tobytes())
meta={'source_version':release.name,'source_sha256':sha,'export_sha256':hashlib.sha256((dest/'optical_cnn.bin').read_bytes()).hexdigest(),'parameters':sum(ck['state_dict'][k].numel() for k in keys),'format':'big-endian float32; Java CPU; no quantization','classes':ck['classes'],'input_shape':[5,256],'limitations':'Mobile streaming, camera Y plane, resized ROI and automatic tracking require device accuracy evaluation.'}
(dest/'optical_model.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
print('Exported',meta['parameters'],'parameters;', (dest/'optical_cnn.bin').stat().st_size,'bytes')
