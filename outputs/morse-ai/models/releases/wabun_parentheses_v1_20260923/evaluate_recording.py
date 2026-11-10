"""Fixed-model recording evaluation; rule decoding is a separately labelled diagnostic."""
import argparse
import csv
import hashlib
import json
import unicodedata
from pathlib import Path
import torch
from audio_preprocessing import load_audio,audio_to_tensor
from morse_cnn import load_checkpoint
from morse_segmentation import segment_morse,extract_character
from morse_table import MORSE_TABLE,REVERSE_TABLE


def canonical_reference(text):
    text=unicodedata.normalize('NFD',unicodedata.normalize('NFKC',text))
    small=dict(zip('ァィゥェォッャュョヮヵヶ','アイウエオツヤユヨワカケ'))
    result=[]
    for char in text:
        if '\u3041'<=char<='\u3096':char=chr(ord(char)+0x60)
        char={'\u3099':'゛','\u309a':'゜','(':'（',')':'）'}.get(char,char)
        char=small.get(char,char)
        if char.isspace() or char in '。、，,.、':continue
        if char not in MORSE_TABLE:raise ValueError(f'Unsupported reference character: {char}')
        result.append(char)
    return ''.join(result)


def edit_alignment(reference,hypothesis):
    n,m=len(reference),len(hypothesis)
    d=[[0]*(m+1) for _ in range(n+1)]
    for i in range(n+1):d[i][0]=i
    for j in range(m+1):d[0][j]=j
    for i in range(1,n+1):
        for j in range(1,m+1):
            d[i][j]=min(d[i-1][j]+1,d[i][j-1]+1,d[i-1][j-1]+(reference[i-1]!=hypothesis[j-1]))
    rows=[];i=n;j=m;counts={'substitutions':0,'insertions':0,'deletions':0,'matches':0}
    while i or j:
        if i and j and d[i][j]==d[i-1][j-1]+(reference[i-1]!=hypothesis[j-1]):
            kind='matches' if reference[i-1]==hypothesis[j-1] else 'substitutions'
            counts[kind]+=1;rows.append(dict(reference_index=i-1,hypothesis_index=j-1,reference=reference[i-1],prediction=hypothesis[j-1],operation=kind));i-=1;j-=1
        elif j and d[i][j]==d[i][j-1]+1:
            counts['insertions']+=1;rows.append(dict(reference_index='',hypothesis_index=j-1,reference='',prediction=hypothesis[j-1],operation='insertions'));j-=1
        else:
            counts['deletions']+=1;rows.append(dict(reference_index=i-1,hypothesis_index='',reference=reference[i-1],prediction='',operation='deletions'));i-=1
    return dict(reference_units=n,predicted_units=m,edit_distance=d[n][m],cer=d[n][m]/n if n else None,**counts),list(reversed(rows))


def evaluate_recording(audio_path,reference_path,checkpoint_path,output_dir,frequency_hz=None,target_frequency_hz=None):
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=False)
    model,config,checkpoint=load_checkpoint(checkpoint_path)
    audio=load_audio(audio_path,config)
    carrier_processing=None
    cnn_audio=audio
    if target_frequency_hz is not None:
        from carrier_preprocessing import translate_carrier
        import soundfile as sf
        cnn_audio,carrier_processing=translate_carrier(audio,config.sample_rate,frequency_hz,target_frequency_hz)
        frequency_hz=carrier_processing['source_hz']
        sf.write(output_dir/'carrier_normalized.wav',cnn_audio,config.sample_rate,subtype='PCM_16')
    # Use original-audio boundaries so the frequency-translation comparison isolates CNN preprocessing.
    segments,detector=segment_morse(audio,config.sample_rate,frequency_hz=frequency_hz)
    mapping={v:k for k,v in checkpoint['label_to_index'].items()}
    rows=[]
    with torch.inference_mode():
        for index,segment in enumerate(segments):
            clip=extract_character(cnn_audio,segment,config.sample_rate)
            try:
                x=audio_to_tensor(clip,config).unsqueeze(0)
                values,indices=model(x).softmax(1).topk(3,dim=1)
                prediction=mapping[int(indices[0,0])];confidence=float(values[0,0]);error=''
                top3=[{'label':mapping[int(i)],'probability':float(v)} for i,v in zip(indices[0],values[0])]
            except ValueError as exc:
                prediction='?';confidence=0.;top3=[];error=str(exc)
            rows.append(dict(index=index,**segment,prediction=prediction,confidence=confidence,
                             top3=json.dumps(top3,ensure_ascii=False),rule_prediction=REVERSE_TABLE.get(segment['pattern'],'?'),error=error))
    reference_text=Path(reference_path).read_text(encoding='utf-8') if reference_path is not None else None
    reference=canonical_reference(reference_text) if reference_text is not None else None
    # Punctuation is excluded consistently; never replace CNN outputs with rule-decoded characters.
    cnn=''.join(row['prediction'] for row in rows if row['prediction'] not in '、。')
    rule=''.join(row['rule_prediction'] for row in rows if row['rule_prediction'] not in '、。')
    cnn_metrics,alignment=edit_alignment(reference,cnn) if reference is not None else (None,[])
    rule_metrics=edit_alignment(reference,rule)[0] if reference is not None else None
    with (output_dir/'segments.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    if alignment:
        with (output_dir/'cnn_alignment.csv').open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(alignment[0]));writer.writeheader();writer.writerows(alignment)
    if reference is not None:
        (output_dir/'reference_original.txt').write_text(reference_text,encoding='utf-8')
        (output_dir/'reference_normalized.txt').write_text(reference,encoding='utf-8')
    (output_dir/'cnn_transcript.txt').write_text(cnn,encoding='utf-8')
    (output_dir/'rule_transcript_diagnostic.txt').write_text(rule,encoding='utf-8')
    result=dict(audio_path=str(audio_path),audio_sha256=hashlib.sha256(Path(audio_path).read_bytes()).hexdigest(),
                checkpoint_sha256=hashlib.sha256(Path(checkpoint_path).read_bytes()).hexdigest(),
                duration_seconds=len(audio)/config.sample_rate,detector=detector,cnn=cnn_metrics,
                rule_diagnostic=rule_metrics,mean_confidence=sum(row['confidence'] for row in rows)/len(rows),
                normalization='NFKC; small kana to full-size; dakuten separate; whitespace/comma/period ignored',
                model_updated=False,reference_available=reference is not None,carrier_processing=carrier_processing,
                cnn_rule_segment_agreement=sum(r['prediction']==r['rule_prediction'] for r in rows)/len(rows),
                agreement_is_accuracy=False,
                unknown_rule_segments=sum(r['rule_prediction']=='?' for r in rows))
    (output_dir/'recording_metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    print('CNN:',cnn);print('Rule diagnostic:',rule)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audio',type=Path)
    parser.add_argument('--reference',type=Path,help='Optional ground truth; omit for unscored transcription')
    parser.add_argument('--frequency-hz',type=float,help='Optional source/detector carrier override')
    parser.add_argument('--target-frequency-hz',type=float,help='Translate CNN input carrier, preserving timing; e.g. 700')
    parser.add_argument('--checkpoint',type=Path,default=Path('models/improved_best.pt'))
    parser.add_argument('--output-dir',type=Path,default=Path('evaluation/real_recording'))
    args=parser.parse_args()
    torch.set_num_threads(1)
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=1):
        evaluate_recording(args.audio,args.reference,args.checkpoint,args.output_dir,args.frequency_hz,args.target_frequency_hz)
