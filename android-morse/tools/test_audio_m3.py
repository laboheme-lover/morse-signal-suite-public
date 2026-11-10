from pathlib import Path
import sys,json,struct,subprocess
import numpy as np,torch,soundfile as sf
import librosa
R=Path(__file__).resolve().parents[1];P=R.parent/'outputs/morse-ai';sys.path.insert(0,str(P))
from adopted_m3 import M3Single,envelope
from morse_segmentation import segment_morse,extract_character
from recognition_policy import interpret
torch.set_num_threads(1);single=M3Single();folder=R/'core-tests/audio-build';folder.mkdir(exist_ok=True)
cases=[]
paths=sorted((R/'test-data').glob('*.wav'))[:5]
real=R.parent/'work/audio_m3_android_20261019/real_excerpt_16k.wav'
if real.exists():paths.append(real)
for path in paths:
 x,sr=sf.read(path,dtype='float32');assert sr==16000
 segments,detector=segment_morse(x);rows=[]
 for s in segments:
  f=envelope(extract_character(x,s),16000,single.model_config);logits=single.model(f.T[None],torch.tensor([len(f)])).detach().numpy()[0];label=single.labels[int(logits.argmax())];rows.append(dict(index=len(rows),pattern=s['pattern'],prediction=label,top_k=[]))
 interpret(rows,False);cases.append((x,segments,detector,''.join(r['text_prediction'] for r in rows)))
(R/'test-data/audio_m3_expected.json').write_text(json.dumps([{'file':p.name,'expected':c[3]} for p,c in zip(paths,cases) if p.parent==R/'test-data'],ensure_ascii=False),encoding='utf-8')
with (folder/'fixture.bin').open('wb') as out:
 rng=np.random.default_rng(42);out.write(struct.pack('>i',65))
 for i in range(65):
  n=int(rng.integers(20,500));x=rng.uniform(0,1.2,n).astype('float32');f=torch.from_numpy(x)[None,None]
  with torch.no_grad():logits=single.model(f,torch.tensor([n]))[0].numpy()
  out.write(struct.pack('>i',n)+x.astype('>f4').tobytes()+logits.astype('>f4').tobytes())
 out.write(struct.pack('>i',len(cases)))
 for x,segments,detector,text in cases:
  out.write(struct.pack('>i',len(x))+x.astype('>f8').tobytes());f=envelope(x[:16000],16000,single.model_config).numpy().ravel();out.write(struct.pack('>i',len(f))+f.astype('>f4').tobytes())
  out.write(struct.pack('>ddi',detector['frequency_hz'],detector['dot_seconds'],len(segments)))
  for s in segments:out.write(struct.pack('>ii',s['start_sample'],s['end_sample']))
  b=text.encode('utf-8');out.write(struct.pack('>H',len(b))+b)
 out.write(struct.pack('>i',2))
 for rate in [44100,48000]:
  up=librosa.resample(cases[0][0],orig_sr=16000,target_sr=rate).astype('float32')
  back=librosa.resample(up,orig_sr=rate,target_sr=16000).astype('float32');segments,_=segment_morse(back);rows=[]
  for s in segments:
   f=envelope(extract_character(back,s),16000,single.model_config)
   with torch.no_grad():y=single.model(f.T[None],torch.tensor([len(f)]))[0]
   rows.append(dict(index=len(rows),pattern=s['pattern'],prediction=single.labels[int(y.argmax())],top_k=[]))
  interpret(rows,False);text=''.join(r['text_prediction'] for r in rows);b=text.encode('utf-8')
  out.write(struct.pack('>ii',rate,len(up))+up.astype('>f4').tobytes()+struct.pack('>H',len(b))+b)
cfg=json.loads((R/'.toolchain/environment.json').read_text(encoding='utf-8'));java=Path(cfg['java'])/'bin'
names=['AudioM3','AudioDsp','AudioM3Recognition','AudioM3Live','MorseCodec','JapaneseNumbers','OpticalMath']
subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-d',str(folder),*[str(R/'app/src/main/java/jp/local/wabun'/f'{n}.java') for n in names],str(R/'core-tests/AudioM3Test.java')],check=True)
p=subprocess.run([str(java/'java.exe'),'-Dfile.encoding=UTF-8','-cp',str(folder),'AudioM3Test',str(R/'app/src/main/assets/audio_m3.bin'),str(R/'app/src/main/assets/audio_filters.bin'),str(folder/'fixture.bin')],capture_output=True,text=True,encoding='utf-8')
(folder/'result.txt').write_text(p.stdout+p.stderr,encoding='utf-8');print(p.stdout+p.stderr);sys.exit(p.returncode)
