"""Inference for one mono 16 kHz single-symbol WAV, using saved settings."""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import soundfile as sf
import torch
from m1.data import envelope
from m1.model import M1
from m1.utils import setup


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--checkpoint',type=Path,required=True)
    ap.add_argument('--wav',type=Path,required=True)
    args=ap.parse_args()
    ck=torch.load(args.checkpoint,map_location='cpu',weights_only=True)
    setup(ck['config'])
    audio,sr=sf.read(args.wav,dtype='float32')
    feature=envelope(audio,sr,ck['config'])
    model=M1(ck['config']).eval();model.load_state_dict(ck['state_dict'])
    with torch.inference_mode():
        prob=model(feature.T.unsqueeze(0),torch.tensor([len(feature)])).softmax(-1)[0]
    labels=sorted(ck['labels'],key=ck['labels'].get)
    values,ids=prob.topk(5)
    print(json.dumps({'wav':str(args.wav),'candidates':[{'label':labels[i],'probability':v} for v,i in zip(values.tolist(),ids.tolist())],
                      'note':'Single-symbol 36-class classifier. Probability is not accuracy.'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
