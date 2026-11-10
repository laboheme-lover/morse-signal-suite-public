"""Reuse decoded brightness, keyed by source identity, ROI and extractor revision."""
import hashlib,json,uuid
from pathlib import Path
import numpy as np
import splitter as s

def read_cached(path,roi,progress=None):
 before=s.identity(path)
 revision=hashlib.sha256(Path(s.__file__).read_bytes()).hexdigest()
 key=dict(source=before,roi=list(map(int,roi)),extractor=revision)
 name=hashlib.sha256(json.dumps(key,sort_keys=True).encode()).hexdigest()
 directory=s.ROOT/'cache'/'brightness';directory.mkdir(parents=True,exist_ok=True)
 target=directory/(name+'.npz')
 if target.exists():
  try:
   with np.load(target,allow_pickle=False) as z:
    meta=json.loads(str(z['metadata']));t=z['times'].copy();v=z['values'].copy()
   if s.identity(path)!=before:raise s.SplitError('動画が変更されました。')
   if len(t)!=meta['frames'] or len(t)!=len(v) or not np.isfinite(t).all() or not np.isfinite(v).all() or np.any(np.diff(t)<=0):raise ValueError('invalid cache')
   if progress:progress(1.)
   return dict(meta,brightness_cache_hit=True),t,v
  except (OSError,ValueError,KeyError):pass
 meta,t,v=s.read_trace(path,roi,progress)
 if s.identity(path)!=before:raise s.SplitError('解析中に動画が変更されました。')
 pending=directory/(name+'.'+uuid.uuid4().hex+'.npz')
 try:
  np.savez_compressed(pending,metadata=json.dumps(meta),times=t,values=v)
  pending.replace(target)
 except OSError:
  # A cache write failure does not invalidate a successful video decode.
  if pending.exists():pending.unlink()
 return dict(meta,brightness_cache_hit=False),t,v
