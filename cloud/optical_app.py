"""Community Cloud entry point: optical app in a separate deployment."""
import runpy,sys,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from runtime import configure
configure()
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'optical-batch-test/pc'))
import splitter
splitter.FFMPEG=Path(shutil.which('ffmpeg') or 'ffmpeg')
target=root/'optical-ml/app.py'
sys.path.insert(0,str(target.parent))
runpy.run_path(str(target),run_name='__main__')
