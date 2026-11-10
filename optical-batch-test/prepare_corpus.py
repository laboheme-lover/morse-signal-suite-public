"""Create optical test scripts using the existing Android normalization rules."""
from pathlib import Path
import ast,base64,collections,hashlib,json,subprocess,re
ROOT=Path(__file__).resolve().parent;WORK=ROOT.parent;ANDROID=WORK/'android-morse'
OUT=ROOT/'corpus';OUT.mkdir(parents=True,exist_ok=True)
java=Path(json.loads((ANDROID/'.toolchain/environment.json').read_text(encoding='utf-8'))['java'])/'bin'
build=ROOT/'build';build.mkdir(exist_ok=True)
helper=build/'Normalize.java'
helper.write_text('''import jp.local.wabun.*;import java.util.*;import java.nio.charset.StandardCharsets;
public class Normalize {public static void main(String[] args)throws Exception {Scanner sc=new Scanner(System.in,StandardCharsets.UTF_8);while(sc.hasNextLine()){String s=new String(Base64.getDecoder().decode(sc.nextLine()),StandardCharsets.UTF_8);System.out.println(Base64.getEncoder().encodeToString(MorseCodec.previewLabels(s).getBytes(StandardCharsets.UTF_8)));}}}''',encoding='utf-8')
sources=[ANDROID/'app/src/main/java/jp/local/wabun'/f'{name}.java' for name in ('JapaneseNumbers','MorseCodec')]
subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-d',str(build),*[str(p) for p in sources],str(helper)],check=True)
table={}
for node in ast.parse((WORK/'outputs/morse-ai/morse_table.py').read_text(encoding='utf-8')).body:
 if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('KANA','MARKS','DIGITS','SYMBOLS') for t in node.targets):table.update(ast.literal_eval(node.value))
assert len(table)==65
batches=[]
batches.append(dict(id='single65',name='① 単文字65ケース',cases=[dict(id=f'single_{i:02d}',source='morse_table.py',raw=c,input=c) for i,c in enumerate(table,1)]))
for group,folder,name in [('original44','real_audio_augmented_no41plus_20261003','② 実録音44件の原稿'),('original20','telegram_audio_augmented_20261003','③ 電報形式20件の原稿')]:
 cases=[]
 for path in sorted((WORK/'outputs'/folder/'references').glob('*.txt'),key=lambda p:int(p.stem)):
  raw=path.read_text(encoding='utf-8-sig');text=raw;removed_header=''
  if group=='original20':
   lines=raw.splitlines();assert '電気通信術受信練習用原信' in lines[0]
   removed_header=lines[0];text='\n'.join(lines[1:])
  controls=re.findall(r'^\s*HR\s+HR\s*|[<＜]\s*(?:ホレ|ラタ)\s*[>＞]',text)
  text=re.sub(r'^\s*HR\s+HR\s*|[<＜]\s*(?:ホレ|ラタ)\s*[>＞]','',text)
  cases.append(dict(id=f'{group}_no{int(path.stem):03d}',source=str(path),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),raw=raw,input=text,removed_document_heading=removed_header,removed_control_markup=controls))
 assert len(cases)==(44 if group=='original44' else 20)
 batches.append(dict(id=group,name=name,cases=cases))
all_cases=[c for b in batches for c in b['cases']]
stdin='\n'.join(base64.b64encode(c['input'].encode()).decode() for c in all_cases)+'\n'
r=subprocess.run([str(java/'java.exe'),'-cp',str(build),'Normalize'],input=stdin,capture_output=True,text=True,encoding='utf-8',check=True)
prepared=[base64.b64decode(s).decode() for s in r.stdout.splitlines()];assert len(prepared)==129
for c,preview in zip(all_cases,prepared):
 labels=' '.join(preview.replace('□','').split());assert labels and all(x in table or x==' ' for x in labels)
 c.update(prepared_with_boxes=preview,removed_count=preview.count('□'),labels=labels)
 pulses=[]
 for i,ch in enumerate(labels):
  if ch==' ':continue
  code=table[ch]
  for j,symbol in enumerate(code):
   pulses.append([True,1 if symbol=='.' else 3])
   if j+1<len(code):pulses.append([False,1])
  if i+1<len(labels):pulses.append([False,7 if labels[i+1]==' ' else 3])
 c['pulses']=pulses;c['units']=sum(u for _,u in pulses);c['symbols']=len(labels.replace(' ',''))
split_batches=[batches[0]]
for original,parts in ((batches[1],10),(batches[2],2)):
 offset=0
 for i in range(parts):
  size=len(original['cases'])//parts+(i<len(original['cases'])%parts)
  cases=original['cases'][offset:offset+size];offset+=size
  split_batches.append(dict(id=f"{original['id']}_part{i+1:02d}",name=f"{original['name']} {i+1}/{parts}（{size}件）",source_group=original['id'],part=i+1,parts=parts,cases=cases))
batches=split_batches
for batch in batches:
 batch['duration_seconds']={str(ms):round(sum(c['units'] for c in batch['cases'])*ms/1000+10*(len(batch['cases'])-1)+20,2) for ms in (300,450,600)}
payload=dict(schema=1,gap_seconds=10,start_dark_seconds=15,end_dark_seconds=5,unit_ms_options=[300,450,600],mode='wabun_only',normalization='Existing Android MorseCodec.previewLabels; remove □ before sending; preserve supported punctuation; omit document heading for 20 originals',batches=batches,
 normalizer_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
dest=OUT/'batches.json';dest.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
assets=ANDROID/'opticaltest/src/main/assets';assets.mkdir(parents=True,exist_ok=True);(assets/'batches.json').write_bytes(dest.read_bytes())
audit=['光送信原稿の変換・除外記録','元ファイルは変更していません。prepared_with_boxes の□が除外箇所です。全文・変換後全文はbatches.jsonに保持。','']
for b in batches:
 audit += [b['name'],f"件数 {len(b['cases'])}、300ms時 {b['duration_seconds']['300']/3600:.2f}時間"]
 for c in b['cases']:
  if c['removed_count'] or c.get('removed_document_heading') or c.get('removed_control_markup'):
   audit += [f"{c['id']}：送信不能 {c['removed_count']}箇所／資料見出し除去 {bool(c.get('removed_document_heading'))}／手続注記除去 {c.get('removed_control_markup',[])}",c['prepared_with_boxes']]
(OUT/'除去と変換の記録.txt').write_text('\n'.join(audit),encoding='utf-8-sig')
print(json.dumps([dict(batch=b['id'],cases=len(b['cases']),removed=sum(c['removed_count'] for c in b['cases']),hours_at_300ms=b['duration_seconds']['300']/3600) for b in batches],ensure_ascii=False,indent=2))
