#!/usr/bin/env python3
"""Minimal custom-worker reference: SHA256 evidence; no shell downloads."""
import argparse, datetime as dt, hashlib, json, os, pathlib, platform, subprocess, zipfile, time

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--workdir',required=True)
 a=p.parse_args();root=pathlib.Path(a.workdir);root.mkdir(parents=True,exist_ok=True)
 def cmd(argv):
  x=subprocess.run(argv,capture_output=True,text=True,timeout=10)
  return {'rc':x.returncode,'text':(x.stdout+x.stderr)[:1800]}
 meta={'schema':'rvv-vla.custom.v1','at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
       'host_arch':platform.machine(), 'gcc':cmd(['g++','--version']),
       'source_has_engine_plan':(pathlib.Path(a.source)/'src/rvv/engines/engine_plan.h').is_file()}
 (root/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
 status={'schema':1,'state':'completed' if meta['source_has_engine_plan'] else 'failed',
         'observations':0,'current_candidate':'custom_example',
         'stop_reason':'Custom probe only; no performance claims'}
 (root/'status.json').write_text(json.dumps(status,indent=2)+'\n')
 with zipfile.ZipFile(root/'snapshot.zip','w',zipfile.ZIP_DEFLATED) as z:
  files=[]
  for name in ('status.json','metadata.json'):
   body=(root/name).read_bytes();z.writestr(name,body)
   files.append({'name':name,'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)})
  z.writestr('MANIFEST.json',json.dumps({'files':files},indent=2))
 (root/'snapshot.sha256').write_text(hashlib.sha256((root/'snapshot.zip').read_bytes()).hexdigest()+'\n')
 time.sleep(2)  # launcher confirms detached worker after one second
 return 0 if status['state']=='completed' else 1
if __name__=='__main__':raise SystemExit(main())
