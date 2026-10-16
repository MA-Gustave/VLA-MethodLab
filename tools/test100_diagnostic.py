#!/usr/bin/env python3
"""Fail-safe Test100 diagnostic packet writer; never invent measurements/success."""
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,zipfile,datetime

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--reason',default='Worker failed; inspect logs')
    a=p.parse_args();root=pathlib.Path(a.output);root.mkdir(parents=True,exist_ok=True)
    status=root/'status100.json'
    try:s=json.loads(status.read_text()) if status.exists() else {}
    except (ValueError,OSError):s={}
    if s.get('state')=='completed':return
    s.update(state='failed',phase=s.get('phase') or 'startup',reason=s.get('reason') or a.reason,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    s.setdefault('rows',0);s.setdefault('validated',False)
    t=status.with_suffix('.json.tmp');t.write_text(json.dumps(s,indent=2)+'\n');os.replace(t,status)
    report=root/'REPORT_100.md'
    if not report.exists():report.write_text('# Test100 diagnostic — no successful result\n\n'+str(s['reason'])+'\n')
    # Do not replace a packet written by the native worker.
    archive=root/'test100_results.zip'
    if archive.is_file():return
    allowed={'status100.json','REPORT_100.md','builds100.json','machine100.json',
        'results100.csv','summary100.json','corpus_manifest100.json','inputs100.json',
        'studio100-build.log','slurm100-exit.json','slurm100-runtime.log'}
    files=[x for x in sorted(root.iterdir()) if x.is_file() and x.name in allowed and x.stat().st_size<=200_000_000]
    temp=archive.with_suffix('.zip.partial')
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
        for f in files:z.write(f,f.name)
    with zipfile.ZipFile(temp) as z:
        if z.testzip():raise RuntimeError('Diagnostic CRC failure')
    os.replace(temp,archive)
    h=hashlib.sha256(archive.read_bytes()).hexdigest()
    (root/'test100_results.sha256').write_text(h+'  '+archive.name+'\n')
    print('TEST100_DIAGNOSTIC_ZIP',archive)
if __name__=='__main__':main()
