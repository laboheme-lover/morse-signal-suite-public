"""OB1 optical metadata protocol; fail closed, never guess corrupted selections."""
import hashlib,zlib,re
import numpy as np
import splitter as s
ALPHABET='0123456789ABCDEFOM'
CODES=['-----','.----','..---','...--','....-','.....','-....','--...','---..','----.','.-','-...','-.-.','-..','.','..-.','---','--']
TABLE=dict(zip(ALPHABET,CODES));REVERSE={v:k for k,v in TABLE.items()}

def encode(digest,unit_ms,indices):
 if unit_ms not in (300,450,600) or not 1<=len(indices)<=65 or len(set(indices))!=len(indices) or any(i<0 or i>=65 for i in indices):raise s.SplitError('連携情報の範囲が不正です。')
 body='OB1'+digest[:8].upper()+str((300,450,600).index(unit_ms))+f'{len(indices):02d}'+''.join(f'{i:02d}' for i in indices)
 return body+f'{zlib.crc32(body.encode("ascii")):08X}'

def pulses(text):
 result=[]
 for i,c in enumerate(text):
  for j,ch in enumerate(TABLE[c]):
   result.append([True,1 if ch=='.' else 3])
   if j+1<len(TABLE[c]):result.append([False,1])
  if i+1<len(text):result.append([False,3])
 return result

def parse(text):
 if not re.fullmatch(r'OB1[0-9A-F]{8}[012][0-9]{2}[0-9]+[0-9A-F]{8}',text):raise s.SplitError('開始前の連携信号の形式が不正です。')
 body=text[:-8]
 if f'{zlib.crc32(body.encode("ascii")):08X}'!=text[-8:]:raise s.SplitError('連携信号の誤読チェックに失敗しました。手動指定で確認してください。')
 digest=hashlib.sha256(s.corpus_path('sentence').read_bytes()).hexdigest()
 if text[3:11]!=digest[:8].upper():raise s.SplitError('送信側とPC側の原稿版が異なります。自動連携できません。')
 count=int(text[12:14]);indices=[int(text[i:i+2]) for i in range(14,len(body),2)]
 batches=s.corpus('sentence')['batches']
 if not 1<=count<=65 or len(body)!=14+2*count or len(indices)!=count or len(set(indices))!=count or any(i>=len(batches) for i in indices):raise s.SplitError('連携信号の送信範囲が不正です。')
 return dict(protocol='OB1',batch_ids=[batches[i]['id'] for i in indices],unit_ms=(300,450,600)[int(text[11])],text=text,corpus_hash_prefix=text[3:11])

def decode(times,values,minimum_contrast=20):
 if len(times)<3:raise s.SplitError('連携信号の映像が不足しています。')
 dt=float(np.median(np.diff(times)))
 low,high=np.percentile(values,[1,99])
 for _ in range(20):
  off=values[values<=(low+high)/2];on=values[values>(low+high)/2]
  if len(off)<2 or len(on)<2:raise s.SplitError('連携信号の点灯と消灯を区別できません。')
  low,high=float(np.median(off)),float(np.median(on))
 if high-low<minimum_contrast:raise s.SplitError('連携信号の輝度差が不足しています。')
 rs=s.runs(values>(low+high)/2,times,dt);group=[];separator=None
 for r in rs:
  if not r['on'] and r['end']-r['start']>=8:
   if group:separator=r;break
  elif r['on'] or group:group.append(r)
 if not group or separator is None or not 8<=separator['end']-separator['start']<=12:raise s.SplitError('連携信号後の10秒消灯が見つかりません。')
 if np.max(np.diff(times[(times>=group[0]['start'])&(times<=separator['start'])]))>.12:raise s.SplitError('連携信号中にフレーム欠落があります。')
 error=None
 for unit in (.3,.45,.6):
  try:
   chars=[];code=''
   for r in group:
    duration=r['end']-r['start'];n=1 if duration<unit*2 else 3
    if abs(duration-n*unit)>max(dt*2.5,unit*.35):raise ValueError()
    if r['on']:code+='.' if n==1 else '-'
    elif n==3:chars.append(REVERSE[code]);code=''
   if code:chars.append(REVERSE[code])
   result=parse(''.join(chars))
   if result['unit_ms']!=round(unit*1000):raise ValueError()
   result.update(header_start=group[0]['start'],header_end=separator['start'],body_from=separator['start']+1.)
   return result
  except (ValueError,KeyError) as e:error=e
 raise s.SplitError('連携信号を確定できません。自動で原稿を割り当てません。'+str(error))
