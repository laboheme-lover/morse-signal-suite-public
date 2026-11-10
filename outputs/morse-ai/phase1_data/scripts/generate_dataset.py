import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
from src.common import load_config
from src.generation import generate

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--limit',type=int,help='Optional limit for a small smoke generation')
    args=parser.parse_args()
    generate(load_config(args.config),dry_run=args.dry_run,limit=args.limit)
