"""Make one complete sentence per recording, preserving the legacy corpus."""
from pathlib import Path
import json,copy,subprocess,base64,ast
R=Path(__file__).resolve().parent;A=R.parent/'android-morse'
def first_sentence(text):
 depth=0
 for i,ch in enumerate(text):
  if ch=='「':depth+=1
  elif ch=='」':
   if depth:depth-=1
   else:return text[:i+1],True
  if ch in '。！？' and depth==0:return text[:i+1],True
 return text,False

def main():
 old=json.loads((R/'corpus/batches.json').read_text(encoding='utf-8'));payload=copy.deepcopy(old);batches=[copy.deepcopy(old['batches'][0])];selected=[]
 for batch in old['batches'][1:]:
  for c in batch['cases']:
   c=copy.deepcopy(c);text=c['input'].strip();removed=[]
   if c['id'].startswith('original20'):
    lines=[s.strip() for s in text.splitlines() if s.strip()];n=3 if c['id'] in ('original20_no015','original20_no019') else 2
    removed=lines[:n];text=''.join(lines[n:])
   sentence,has_end=first_sentence(text)
   c.update(parent_id=c['id'],id=c['id']+'_sentence',input=sentence,selected_sentence=sentence,removed_telegram_header_address_name=removed,has_sentence_terminator=has_end,selection_policy='first complete sentence; whole body if no terminator')
   selected.append(c)
 java=Path(json.loads((A/'.toolchain/environment.json').read_text(encoding='utf-8'))['java'])/'bin/java.exe'
 data='\n'.join(base64.b64encode(c['input'].encode()).decode() for c in selected)+'\n'
 res=subprocess.run([str(java),'-cp',str(R/'build'),'Normalize'],input=data,capture_output=True,text=True,encoding='utf-8',check=True)
 prepared=[base64.b64decode(x).decode() for x in res.stdout.splitlines()];assert len(prepared)==64
 table={}
 for n in ast.parse((R.parent/'outputs/morse-ai/morse_table.py').read_text(encoding='utf-8')).body:
  if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('KANA','MARKS','DIGITS','SYMBOLS') for t in n.targets):table.update(ast.literal_eval(n.value))
 for c,preview in zip(selected,prepared):
  labels=' '.join(preview.replace('□','').split());assert labels and all(ch in table or ch==' ' for ch in labels)
  pulses=[]
  for i,ch in enumerate(labels):
   if ch==' ':continue
   for j,symbol in enumerate(table[ch]):
    pulses.append([True,1 if symbol=='.' else 3])
    if j+1<len(table[ch]):pulses.append([False,1])
   if i+1<len(labels):pulses.append([False,7 if labels[i+1]==' ' else 3])
  c.update(labels=labels,prepared_with_boxes=preview,removed_count=preview.count('□'),pulses=pulses,units=sum(u for _,u in pulses),symbols=len(labels.replace(' ','')))
  group='実録音44件' if c['parent_id'].startswith('original44') else '電報形式20件';no=int(c['parent_id'].split('no')[1]);prefix='②' if group.startswith('実') else '③'
  b=dict(id=c['id'],name=f'{prefix} {group} No.{no}／単文'+('（区切点なし・全文）' if not c['has_sentence_terminator'] else ''),cases=[c],duration_seconds={str(ms):round(c['units']*ms/1000+20,2) for ms in (300,450,600)})
  batches.append(b)
 payload.update(batches=batches,profile='sentence-v1',selection_policy='44 separate batches and 20 separate batches; single65 unchanged')
 target=R/'corpus/sentence_batches.json';target.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
 (A/'opticaltest/src/main/assets/batches.json').write_bytes(target.read_bytes())
 lines=['単文送信原稿・予定時間（短点300ms、開始前15秒・終了後5秒の消灯を含む）','単文字65ケースは変更なし。単文は一例文につき一バッチ。区切点がない原稿は全文を維持。','']
 for b in batches[1:]:
  c=b['cases'][0];lines.extend([b['name'],f"{c['symbols']}文字単位／{b['duration_seconds']['300']:.1f}秒",c['selected_sentence'],'送信文字：'+c['labels'],''])
 (R/'corpus/単文送信原稿一覧.txt').write_text('\n'.join(lines),encoding='utf-8-sig')
 print(json.dumps({'batches':len(batches),'single_unchanged':batches[0]==old['batches'][0],'max_seconds_300ms':max(b['duration_seconds']['300'] for b in batches[1:]),'no_terminator':[c['parent_id'] for c in selected if not c['has_sentence_terminator']]},ensure_ascii=False))
if __name__=='__main__':main()
