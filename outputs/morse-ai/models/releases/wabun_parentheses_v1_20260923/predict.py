"""Milestone 8: one Morse character -> CNN top-k, probabilities, and Mel."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import torch
from audio_preprocessing import load_audio,compute_mel_db,mel_to_tensor
from morse_cnn import load_checkpoint

DEFAULT_CHECKPOINT=Path(__file__).resolve().parent/'models/saved_wabun_cnn_20260914/best_model.pt'


class MorsePredictor:
    """Load once and reuse. Inputs must already contain exactly one Morse character."""
    def __init__(self,checkpoint_path=DEFAULT_CHECKPOINT):
        self.checkpoint_path=Path(checkpoint_path).resolve()
        self.model,self.config,state=load_checkpoint(self.checkpoint_path)
        self.labels={v:k for k,v in state['label_to_index'].items()}
        self.checkpoint_sha256=hashlib.sha256(self.checkpoint_path.read_bytes()).hexdigest()

    def predict_audio(self,audio,top_k=3):
        if type(top_k) is not int or not 1<=top_k<=len(self.labels):
            raise ValueError(f'top_k must be between 1 and {len(self.labels)}')
        audio=np.asarray(audio,dtype=np.float32)
        if audio.ndim!=1 or not audio.size or not np.isfinite(audio).all():
            raise ValueError('Finite nonempty mono audio is required')
        if np.max(np.abs(audio))<1e-7:
            raise ValueError('Silent audio has no Morse character to classify')
        mel=compute_mel_db(audio,self.config)
        # Never truncate a symbol to fit the model.
        tensor=mel_to_tensor(mel,self.config)
        with torch.inference_mode():
            probabilities=self.model(tensor.unsqueeze(0)).softmax(dim=1)[0]
            if not torch.isfinite(probabilities).all():raise ValueError('Nonfinite model probabilities')
            values,indices=probabilities.topk(top_k)
        candidates=[dict(rank=rank+1,label=self.labels[int(i)],probability=float(v))
                    for rank,(i,v) in enumerate(zip(indices,values))]
        return dict(prediction=candidates[0]['label'],confidence=candidates[0]['probability'],
                    top_k=candidates,mel=mel,mel_shape=list(mel.shape),input_shape=list(tensor.shape),
                    duration_seconds=len(audio)/self.config.sample_rate,sample_rate=self.config.sample_rate,
                    checkpoint=str(self.checkpoint_path),checkpoint_sha256=self.checkpoint_sha256,
                    preprocessing=self.config.to_dict(),confidence_calibrated=False,
                    input_scope='single character; no segmentation or language-mode switching')

    def predict_file(self,audio_path,top_k=3):
        path=Path(audio_path).resolve()
        if not path.is_file():raise FileNotFoundError(path)
        result=self.predict_audio(load_audio(path,self.config),top_k)
        result.update(audio_path=str(path),audio_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        return result


def predict(audio_path,checkpoint_path=DEFAULT_CHECKPOINT,top_k=3):
    return MorsePredictor(checkpoint_path).predict_file(audio_path,top_k)


def save_prediction(result,output_dir):
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=False)
    mel=result['mel']
    np.save(output_dir/'mel.npy',mel,allow_pickle=False)
    metadata={k:v for k,v in result.items() if k!='mel'}
    metadata['artifacts']={'mel_array':'mel.npy','mel_image':'mel.png'}
    (output_dir/'prediction.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parent/'.cache/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import librosa.display
    fig,ax=plt.subplots(figsize=(8,3),layout='constrained')
    mesh=librosa.display.specshow(mel,sr=result['sample_rate'],hop_length=result['preprocessing']['hop_length'],
                               x_axis='time',y_axis='mel',ax=ax)
    ax.set_title('Single-character Mel spectrogram (before right padding)')
    fig.colorbar(mesh,ax=ax,format='%+2.0f dB')
    fig.savefig(output_dir/'mel.png',dpi=150);plt.close(fig)
    return metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audio',type=Path,help='A single-character WAV (other decodable audio accepted)')
    parser.add_argument('--checkpoint',type=Path,default=DEFAULT_CHECKPOINT)
    parser.add_argument('--top-k',type=int,default=3)
    parser.add_argument('--output-dir',type=Path,help='New directory for JSON, Mel NPY and PNG')
    args=parser.parse_args()
    torch.set_num_threads(1)
    from threadpoolctl import threadpool_limits
    try:
        with threadpool_limits(limits=1):
            result=predict(args.audio,args.checkpoint,args.top_k)
            metadata=save_prediction(result,args.output_dir) if args.output_dir else {k:v for k,v in result.items() if k!='mel'}
        print(json.dumps(metadata,ensure_ascii=False,indent=2))
    except (ValueError,FileNotFoundError,FileExistsError) as exc:
        parser.exit(2,f'Prediction failed: {exc}\n')


if __name__=='__main__':main()
