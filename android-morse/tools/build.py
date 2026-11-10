from pathlib import Path
import os,json,subprocess,sys,shutil,hashlib
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
R=Path(__file__).resolve().parents[1];T=R/'.toolchain'
cfg=json.loads((T/'environment.json').read_text(encoding='utf-8'))
env=os.environ.copy();env.update(JAVA_HOME=cfg['java'],ANDROID_HOME=cfg['sdk'],ANDROID_USER_HOME=str(T/'android-user'),GRADLE_USER_HOME=str(T/'gradle-home'))
env['PATH']=str(Path(cfg['java'])/'bin')+os.pathsep+env['PATH']
tasks=sys.argv[1:] or ['assembleDebug','lintDebug']
log=R/'build.log'
with log.open('w',encoding='utf-8') as f:
    p=subprocess.Popen([cfg['gradle'],'--no-daemon','--console=plain',*tasks],cwd=R,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
    for line in p.stdout:f.write(line);f.flush();print(line,end='',flush=True)
    rc=p.wait()
if rc:raise SystemExit(rc)
apk=R/'app/build/outputs/apk/debug/app-debug.apk'
if apk.exists():
    (R/'dist').mkdir(exist_ok=True);shutil.copy2(apk,R/'dist/wabun-signal-0.5.0-debug.apk')
    (R/'dist/SHA256SUMS.txt').write_text(hashlib.sha256(apk.read_bytes()).hexdigest()+'  wabun-signal-0.5.0-debug.apk\n',encoding='utf-8')
print('Build finished')



