"""Reproduce an arbitrary persisted dataset item as an augmented MP4."""
import argparse,json
from pathlib import Path
import numpy as np
from dataset import augment,preview_video
from extract import OUT

def main():
 p=argparse.ArgumentParser();p.add_argument('index',type=int);p.add_argument('output');a=p.parse_args()
 if Path(a.output).exists():raise FileExistsError(a.output)
 records=[json.loads(s) for s in (OUT/'dataset/manifest.jsonl').read_text(encoding='utf-8').splitlines()]
 r=records[a.index];z=np.load(OUT/'original_crops'/f'{r["source_id"]}.npz');p=r['parameters']
 frames,_=augment(z['frames'],z['times'],p['condition'],p['seed'],p['stress']);preview_video(frames,Path(a.output))

if __name__=='__main__':main()
