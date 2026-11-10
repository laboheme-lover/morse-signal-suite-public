"""Milestone 9: continuous audio -> timestamped CNN predictions and text."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from predict import MorsePredictor,DEFAULT_CHECKPOINT
from audio_preprocessing import load_audio
from morse_segmentation import segment_morse,extract_character
from morse_table import MORSE_TABLE,REVERSE_TABLE
from mixed_morse import INTERNATIONAL_REVERSE


def interpret_segments(rows,mixed_mode=True):
    from recognition_policy import interpret
    return interpret(rows,mixed_mode)


class SequencePredictor:
    def __init__(self,checkpoint_path=DEFAULT_CHECKPOINT):
        self.single=MorsePredictor(checkpoint_path)

    def predict_audio(self,audio,*,top_k=3,low_confidence=.8,frequency_hz=None,
                      target_frequency_hz=None,character_gap_seconds=None,mixed_mode=True,include_details=False):
        if type(top_k) is not int or not 1<=top_k<=len(self.single.labels):raise ValueError('Invalid top_k')
        if not np.isfinite(low_confidence) or not 0<=low_confidence<=1:raise ValueError('low_confidence must be in [0,1]')
        audio=np.asarray(audio,dtype=np.float32);sr=self.single.config.sample_rate
        processed=audio;carrier=None
        if target_frequency_hz is not None:
            from carrier_preprocessing import translate_carrier
            processed,carrier=translate_carrier(audio,sr,frequency_hz,target_frequency_hz)
            frequency_hz=carrier['source_hz']
        segments,detector=segment_morse(audio,sr,frequency_hz,character_gap_seconds)
        rows=[]
        for index,segment in enumerate(segments):
            clip=extract_character(processed,segment,sr)
            row=dict(index=index,**segment)
            try:
                result=self.single.predict_audio(clip,top_k)
                row.update(prediction=result['prediction'],confidence=result['confidence'],top_k=result['top_k'],
                           mel_shape=result['mel_shape'],error=None)
                if include_details:row.update(audio=clip,mel=result['mel'])
            except ValueError as exc:
                row.update(prediction='?',confidence=0.,top_k=[],error=str(exc))
                if include_details:row['audio']=clip
            row['low_confidence']=row['confidence']<low_confidence
            rows.append(row)
        warnings=interpret_segments(rows,mixed_mode)
        chars=[r for r in rows if r['kind']=='character']
        for row in rows:
            row['needs_review']=bool(row.get('review_reason')) or (row['kind']=='character' and (row['low_confidence'] or row['disagrees_with_rule'] or row['text_prediction'] in ('?','□') or row['error'] is not None))
        return dict(text=''.join(r['text_prediction'] for r in rows),raw_cnn_text=''.join(r['prediction'] for r in rows),
                    rule_text=''.join(r['rule_prediction'] for r in rows),segments=rows,warnings=warnings,
                    segment_count=len(rows),character_count=len(chars),review_count=sum(r['needs_review'] for r in rows),
                    mean_confidence=float(np.mean([r['confidence'] for r in chars])) if chars else None,
                    duration_seconds=len(audio)/sr,sample_rate=sr,detector=detector,carrier_processing=carrier,
                    low_confidence_threshold=low_confidence,mixed_mode=mixed_mode,
                    checkpoint=str(self.single.checkpoint_path),checkpoint_sha256=self.single.checkpoint_sha256,
                    preprocessing=self.single.config.to_dict(),confidence_calibrated=False,
                    text_policy='v2: CNN characters; mode controls hidden; unsupported observed codes use □; raw candidates preserved; no reference text')

    def predict_file(self,path,**kwargs):
        path=Path(path).resolve()
        result=self.predict_audio(load_audio(path,self.single.config),**kwargs)
        result.update(audio_path=str(path),audio_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        return result


def save_sequence(result,output_dir):
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=False)
    metadata={k:v for k,v in result.items() if k!='segments'};metadata['segments']=[]
    for r in result['segments']:
        row={k:v for k,v in r.items() if k not in ('audio','mel')}
        for kind in ('audio','mel'):
            if kind not in r:continue
            folder=output_dir/'details';folder.mkdir(exist_ok=True)
            if kind=='audio':
                import soundfile as sf
                path=folder/f"{r['index']:05d}.wav";sf.write(path,r[kind],result['sample_rate'],subtype='PCM_16')
            else:
                path=folder/f"{r['index']:05d}_mel.npy";np.save(path,r[kind],allow_pickle=False)
            row[kind+'_file']=path.relative_to(output_dir).as_posix()
        metadata['segments'].append(row)
    (output_dir/'sequence.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    for key in ('text','raw_cnn_text','rule_text'):(output_dir/(key+'.txt')).write_text(result[key],encoding='utf-8')
    return metadata


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('audio',type=Path);p.add_argument('--checkpoint',type=Path,default=DEFAULT_CHECKPOINT)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--top-k',type=int,default=3)
    p.add_argument('--low-confidence',type=float,default=.8);p.add_argument('--frequency-hz',type=float)
    p.add_argument('--target-frequency-hz',type=float);p.add_argument('--character-gap-seconds',type=float)
    p.add_argument('--wabun-only',action='store_true');p.add_argument('--save-details',action='store_true')
    a=p.parse_args();torch.set_num_threads(1)
    from threadpoolctl import threadpool_limits
    try:
        with threadpool_limits(limits=1):
            result=SequencePredictor(a.checkpoint).predict_file(a.audio,top_k=a.top_k,low_confidence=a.low_confidence,
                frequency_hz=a.frequency_hz,target_frequency_hz=a.target_frequency_hz,character_gap_seconds=a.character_gap_seconds,
                mixed_mode=not a.wabun_only,include_details=a.save_details)
            save_sequence(result,a.output_dir)
        print(json.dumps({k:result[k] for k in ('text','rule_text','segment_count','review_count','warnings')},ensure_ascii=False,indent=2))
    except (ValueError,FileNotFoundError,FileExistsError) as exc:p.exit(2,f'Sequence prediction failed: {exc}\n')


if __name__=='__main__':main()
