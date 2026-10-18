#!/usr/bin/env python3
"""Fail-safe Test105 diagnostic packet writer; never invent measurements/success."""
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,zipfile,datetime

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--reason',default='Worker failed; inspect logs')
    a=p.parse_args();root=pathlib.Path(a.output);root.mkdir(parents=True,exist_ok=True)
    status=root/'status105.json'
    try:s=json.loads(status.read_text()) if status.exists() else {}
    except (ValueError,OSError):s={}
    if s.get('state')=='completed':return
    s.update(state='failed',phase=s.get('phase') or 'startup',reason=s.get('reason') or a.reason,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    s.setdefault('rows',0);s.setdefault('validated',False)
    t=status.with_suffix('.json.tmp');t.write_text(json.dumps(s,indent=2)+'\n');os.replace(t,status)
    report=root/'REPORT_105.md'
    if not report.exists():report.write_text('# Test105 diagnostic — no successful result\n\n'+str(s['reason'])+'\n')
    # Always refresh failure packet: native worker may have packaged before
    # SLURM flushed stderr or before its EXIT trap recorded the exit code.
    archive=root/'test105_results.zip'
    allowed={'status105.json','REPORT_105.md','builds105.json','compilers105.json','probe105_gcc.log','probe105_llvm.log','machine105.json',
        'results105.csv','summary105.json','corpus_manifest105.json','inputs105.json',
        'conformance105.csv','conformance105.json','conformance_manifest105.json',
        'studio105-build.log','slurm105-exit.json','slurm105-runtime.log','studio105-cloudv.log'}
    files=[x for x in sorted(root.iterdir()) if x.is_file() and x.name in allowed and x.stat().st_size<=200_000_000]
    temp=archive.with_suffix('.zip.partial')
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
        for f in files:z.write(f,f.name)
    with zipfile.ZipFile(temp) as z:
        if z.testzip():raise RuntimeError('Diagnostic CRC failure')
    os.replace(temp,archive)
    h=hashlib.sha256(archive.read_bytes()).hexdigest()
    (root/'test105_results.sha256').write_text(h+'  '+archive.name+'\n')
    print('TEST105_DIAGNOSTIC_ZIP',archive)
if __name__=='__main__':main()
