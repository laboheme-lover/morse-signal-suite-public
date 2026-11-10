from pathlib import Path
import concurrent.futures,hashlib,json,urllib.request,zipfile
BASE=Path(__file__).parent/'external_noise/DEMAND'
SOURCES={'DKITCHEN':'7ffbf52d7f4699f96927846103dc8788','STRAFFIC':'2efa87262f272bbf9ba578088e81939c'}
def fetch(item):
    name,expected=item;BASE.mkdir(exist_ok=True,parents=True);p=BASE/(name+'_16k.zip')
    url=f'https://zenodo.org/records/1227121/files/{p.name}?download=1'
    if not p.exists():
        with urllib.request.urlopen(url,timeout=60) as response,p.with_suffix('.part').open('wb') as f:
            total=0
            while True:
                block=response.read(1024**2)
                if not block:break
                f.write(block);total+=len(block)
                if total%(16*1024**2)==0:print(name,str(total//1024**2)+' MiB',flush=True)
        p.with_suffix('.part').rename(p)
    with p.open('rb') as f:md5=hashlib.file_digest(f,'md5').hexdigest()
    if md5!=expected:raise ValueError('Archive checksum mismatch: '+name)
    target=BASE/(name+'_ch01.wav')
    with zipfile.ZipFile(p) as z:
        member=next(n for n in z.namelist() if Path(n).name.lower()=='ch01.wav');raw=z.read(member)
        if target.exists() and target.read_bytes()!=raw:raise ValueError('Existing channel changed')
        if not target.exists():target.write_bytes(raw)
    with p.open('rb') as f:checksum=hashlib.file_digest(f,'sha256').hexdigest()
    record=dict(source='https://zenodo.org/records/1227121',download_url=url,authors=['Joachim Thiemann','Nobutaka Ito','Emmanuel Vincent'],
        license_in_description='CC BY-SA 3.0',archive=p.name,archive_md5=md5,archive_sha256=checksum,selected_member=member,selected_sha256=hashlib.sha256(raw).hexdigest())
    (BASE/(name+'_provenance.json')).write_text(json.dumps(record,indent=2),encoding='utf-8');print(name+' verified',flush=True)
if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(fetch,SOURCES.items()))
