"""Start a private headless emulator, run integration tests, then stop it."""
from pathlib import Path
import os,json,subprocess,sys,time
r=Path(__file__).resolve().parents[1];t=r/'.toolchain';c=json.loads((t/'environment.json').read_text(encoding='utf-8'))
env=os.environ.copy();env.update(ANDROID_HOME=c['sdk'],ANDROID_USER_HOME=str(t/'android-user'),ANDROID_AVD_HOME=str(t/'avd'),ANDROID_EMULATOR_HOME=str(t/'android-user'))
adb=str(Path(c['sdk'])/'platform-tools/adb.exe');serial='emulator-5580'
listing=subprocess.check_output([adb,'devices'],text=True)
if serial in listing:raise SystemExit('Test emulator port already in use; no changes made.')
with (t/'emulator-test.log').open('w',encoding='utf-8') as log:
 p=subprocess.Popen([str(Path(c['sdk'])/'emulator/emulator.exe'),'-avd','Wabun_API35','-port','5580',*(['-accel','off','-cores','2','-feature','-Vulkan'] if os.environ.get('WABUN_EMULATOR_SOFTWARE')=='1' else []),'-no-window','-no-audio','-no-boot-anim','-gpu','software','-no-snapshot','-camera-back','none','-camera-front','none','-memory','2048'],env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
 try:
  for i in range(180):
   if p.poll() is not None:raise RuntimeError(f'Emulator exited: {p.returncode}; see emulator-test.log')
   q=subprocess.run([adb,'-s',serial,'shell','getprop','sys.boot_completed'],capture_output=True,text=True,timeout=5)
   if q.stdout.strip()=='1':break
   time.sleep(2)
  else:raise RuntimeError('Emulator boot timed out')
  subprocess.run([sys.executable,str(r/'tools/deploy.py'),'--serial',serial,'--test'],check=True)
 finally:
  if p.poll() is None:
   subprocess.run([adb,'-s',serial,'emu','kill'],capture_output=True,timeout=10)
   try:p.wait(timeout=15)
   except subprocess.TimeoutExpired:p.terminate()
