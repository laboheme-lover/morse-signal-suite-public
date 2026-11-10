"""Community Cloud entry point: audio app in its own process."""
import runpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from runtime import configure
configure()
target=Path(__file__).resolve().parents[1]/'outputs/morse-ai/app.py'
sys.path.insert(0,str(target.parent))
runpy.run_path(str(target),run_name='__main__')
