"""Generate labelled smoke fixtures plus a manifest referencing known recording 57."""
from intake import PROJECT,digest
from pathlib import Path
import json
import numpy as np
import soundfile as sf
from generate_morse_audio import generate_morse_audio

root=Path(__file__).resolve().parent
out=root/'runner_rehearsal_inputs';out.mkdir(exist_ok=False)
entries=[]
for name,signals,reference in [('clean','イロハ','イロハ'),('mixed','イ（ヤチツ）ロ','イWFPロ'),('silent','','アイウ')]:
    audio=np.concatenate([generate_morse_audio(c,.1,700,.7,padding=.15) for c in signals]) if signals else np.zeros(16000,dtype=np.float32)
    sf.write(out/f'{name}.wav',audio,16000)
    (out/f'{name}.txt').write_text(reference,encoding='utf-8')
    entries.append(dict(id=name,audio=f'{name}.wav',reference=f'{name}.txt',group_id='synthetic_smoke',declared_unseen=False,body={'mode':'full'}))
meta=json.loads((PROJECT/'evaluation/real_collection_baseline/057/recording_metrics.json').read_text(encoding='utf-8'))
entries.append(dict(id='known057',audio=meta['audio_path'],reference=str(PROJECT/'evaluation/real_collection_baseline/057/reference_original.txt'),group_id='known_taman',declared_unseen=False,body={'mode':'protocol'}))
(out/'manifest.json').write_text(json.dumps({'source_review_completed':False,'purpose':'Known/synthetic rehearsal only; includes intentional silence failure','recordings':entries},ensure_ascii=False,indent=2),encoding='utf-8')
print(out/'manifest.json')
