"""Create a traceable listening excerpt without changing audio sources or references."""
from policy import PROJECT,render_body
from intake import digest
from pathlib import Path
import csv,json
import soundfile as sf
from audio_preprocessing import load_audio
from morse_segmentation import segment_morse

root=Path(__file__).resolve().parent
out=root/'review077';out.mkdir(exist_ok=False)
source=PROJECT/'evaluation/real_collection_baseline/077'
meta=json.loads((source/'recording_metrics.json').read_text(encoding='utf-8'))
audio_path=Path(meta['audio_path'])
assert digest(audio_path)==meta['audio_sha256']
prediction=PROJECT/'phase7_real/results/077/M4_segments.csv'
with prediction.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
text,interpreted,_=render_body(rows)
visible=[r for r in interpreted if r['kind']=='character' and r['rule_prediction'] not in '、」']
assert ''.join(r['text_prediction'] for r in visible)==text
phrase='ソウコナイノカンキヨウシ゛ヨウケンヲイシ゛スル'
assert text.count(phrase)==1
offset=text.index(phrase)
assert all(len(r['text_prediction'])==1 for r in visible)
selected=visible[offset:offset+len(phrase)]
audio=load_audio(audio_path)
start=max(0,int(selected[0]['start_sample'])-8000)
end=min(len(audio),int(selected[-1]['end_sample'])+8000)
sf.write(out/'review077_excerpt.wav',audio[start:end],16000,subtype='PCM_16')
detected,info=segment_morse(audio)
lookup={(r['start_sample'],r['end_sample']):r['pattern'] for r in detected}
assert all(lookup.get((int(r['start_sample']),int(r['end_sample'])))==r['pattern'] for r in selected)
export=[]
for r in selected:
    export.append({'index':r['index'],'source_start_seconds':int(r['start_sample'])/16000,'source_end_seconds':int(r['end_sample'])/16000,
        'excerpt_start_seconds':(int(r['start_sample'])-start)/16000,'pattern':r['pattern'],'CNN_M4':r['text_prediction'],'rule':r['rule_prediction']})
with (out/'symbol_evidence.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(export[0]));w.writeheader();w.writerows(export)
evidence={'status':'NEEDS_HUMAN_ADJUDICATION','source_audio':str(audio_path),'source_sha256':digest(audio_path),
    'reference_sha256':digest(source/'reference_original.txt'),'prediction_sha256':digest(prediction),
    'start_seconds':start/16000,'end_seconds':end/16000,'excerpt_sha256':digest(out/'review077_excerpt.wav'),
    'processing':'mono 16000 Hz decode, excerpt with 0.5 second margins, PCM16; no pitch/time change',
    'fresh_detection_matches_saved_local_boundaries':True,'reference_changed':False,'ground_truth_confirmed':False}
(out/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
report=f'''# 77番：原稿と録音の照合資料

## 確認する箇所

- 原稿の該当部分：ソウコナイノカンキョウジョウケン **オンドトシツド** ヲイジスル
- M1〜M4・ルール復号の該当部分：ソウコナイノカンキョウジョウケン ヲイジスル
- 正規化後は9文字の削除として採点されています。濁点を別文字で数えます。編集距離の対応付けは同じ「ン」の位置などで揺れがあります。

元録音の **{start/16000:.3f}〜{end/16000:.3f}秒** を `review077_excerpt.wav` に保存しました。元音声・正解文は変更していません。

全録音を改めて区間検出したところ、この抜粋に対応する境界と符号パターンは保存済みデータと一致しました。各符号の時刻・短点長点・M4とルールの文字は `symbol_evidence.csv` にあります。

自動検出器が同じ結果になることは、原稿が誤っている証明にはなりません。人が原音を聴いて、「温度と湿度」に相当する信号が送られているかを確認するための資料です。音声の脱落か、原稿の注釈か、検出漏れかは未確定です。採点結果と正解文は据え置いています。

確認後は、判断者・日付・元動画の表示等の根拠・判断内容を別記録として保存し、正解を改訂する場合も旧版を残してください。
'''
(out/'README.md').write_text(report,encoding='utf-8')
assert digest(audio_path)==meta['audio_sha256']
print(json.dumps(evidence,ensure_ascii=False,indent=2))
