from pathlib import Path
import urllib.request,json,hashlib,zipfile,concurrent.futures,os,subprocess
ROOT=Path(__file__).resolve().parents[1]
T=ROOT/'.toolchain';D=T/'downloads';D.mkdir(parents=True,exist_ok=True)
def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'WabunDevelopment/0.1'}),timeout=90)
def download(name,url,digest,kind='sha256'):
    dst=D/name
    if not dst.exists() or hashlib.new(kind,dst.read_bytes()).hexdigest()!=digest:
        print('Downloading '+name,flush=True)
        with fetch(url) as r,open(dst,'wb') as f:
            while b:=r.read(1024*1024):f.write(b)
    assert hashlib.new(kind,dst.read_bytes()).hexdigest()==digest,name+' checksum mismatch'
    return dst
meta=json.load(fetch('https://api.adoptium.net/v3/assets/latest/17/hotspot?architecture=x64&image_type=jdk&os=windows&vendor=eclipse'))[0]
j=meta['binary']['package']
gsha=fetch('https://services.gradle.org/distributions/gradle-8.11.1-bin.zip.sha256').read().decode().strip()
jobs=[('jdk.zip',j['link'],j['checksum']),('gradle.zip','https://services.gradle.org/distributions/gradle-8.11.1-bin.zip',gsha),('cmdline.zip','https://dl.google.com/android/repository/commandlinetools-win-15859902_latest.zip','90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a')]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    archives=list(pool.map(lambda a:download(*a),jobs))
for archive,dest in zip(archives,[T/'java',T/'gradle',T/'sdk/cmdline-tools']):
    dest.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        rootname=z.namelist()[0].split('/')[0]
        if not (dest/rootname).exists():z.extractall(dest)
java=next((T/'java').glob('*/bin/java.exe')).parent.parent
sdk=T/'sdk';manager=sdk/'cmdline-tools/cmdline-tools/bin/sdkmanager.bat'
env=os.environ.copy();env.update(JAVA_HOME=str(java),ANDROID_HOME=str(sdk),ANDROID_USER_HOME=str(T/'android-user'),GRADLE_USER_HOME=str(T/'gradle-home'))
env['PATH']=str(java/'bin')+os.pathsep+env['PATH']
(T/'environment.json').write_text(json.dumps({'java':str(java),'sdk':str(sdk),'gradle':str(T/'gradle/gradle-8.11.1/bin/gradle.bat'),'source':j['link'],'jdk_version':meta['version']['semver']},ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'local.properties').write_text('sdk.dir='+str(sdk).replace('\\','/')+'\n',encoding='utf-8')
for args in [['--licenses'],['platform-tools','platforms;android-35','build-tools;35.0.0']]:
    print('SDK manager: '+str(args),flush=True)
    r=subprocess.run([str(manager),'--sdk_root='+str(sdk),*args],input='y\n'*100,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (T/('licenses.log' if args[0]=='--licenses' else 'sdk-install.log')).write_text(r.stdout,encoding='utf-8')
    if r.returncode:raise RuntimeError(r.stdout[-5000:])
print('Environment ready',flush=True)
