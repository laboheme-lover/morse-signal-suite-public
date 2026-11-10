from pathlib import Path
import os,json,subprocess,shutil,hashlib
R=Path(__file__).resolve().parent;A=R.parent/'android-morse';T=A/'.toolchain'
cfg=json.loads((T/'environment.json').read_text(encoding='utf-8'))
env=os.environ.copy();env.update(JAVA_HOME=cfg['java'],ANDROID_HOME=cfg['sdk'],ANDROID_USER_HOME=str(T/'android-user'),GRADLE_USER_HOME=str(T/'gradle-home'))
env['PATH']=str(Path(cfg['java'])/'bin')+os.pathsep+env['PATH']
with (R/'android_build.log').open('w',encoding='utf-8') as f:
 result=subprocess.run([cfg['gradle'],'--no-daemon','--offline','--console=plain',':opticaltest:assembleDebug',':opticaltest:lintDebug'],cwd=A,env=env,stdout=f,stderr=subprocess.STDOUT)
if result.returncode:raise SystemExit('Build failed; see android_build.log')
dist=R/'dist';dist.mkdir(exist_ok=True);p=dist/'optical-batch-sender-0.5.0-debug.apk'
shutil.copy2(A/'opticaltest/build/outputs/apk/debug/opticaltest-debug.apk',p)
(dist/'SHA256SUMS.txt').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n',encoding='utf-8')
print(p)
