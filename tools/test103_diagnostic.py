#!/usr/bin/env python3
"""Fail-safe Test103 diagnostic packet writer; never invent measurements/success."""
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,zipfile,datetime

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--reason',default='Worker failed; inspect logs')
    a=p.parse_args();root=pathlib.Path(a.output);root.mkdir(parents=True,exist_ok=True)
    status=root/'status103.json'
    try:s=json.loads(status.read_text()) if status.exists() else {}
    except (ValueError,OSError):s={}
    if s.get('state')=='completed':return
    s.update(state='failed',phase=s.get('phase') or 'startup',reason=s.get('reason') or a.reason,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    s.setdefault('rows',0);s.setdefault('validated',False)
    t=status.with_suffix('.json.tmp');t.write_text(json.dumps(s,indent=2)+'\n');os.replace(t,status)
    report=root/'REPORT_103.md'
    if not report.exists():report.write_text('# Test103 diagnostic — no successful result\n\n'+str(s['reason'])+'\n')
    # Always refresh failure packet: native worker may have packaged before
    # SLURM flushed stderr or before its EXIT trap recorded the exit code.
    archive=root/'test103_results.zip'
    allowed={'status103.json','REPORT_103.md','builds103.json','machine103.json',
        'results103.csv','summary103.json','corpus_manifest103.json','inputs103.json',
        'studio103-build.log','slurm103-exit.json','slurm103-runtime.log','studio103-cloudv.log'}
    files=[x for x in sorted(root.iterdir()) if x.is_file() and x.name in allowed and x.stat().st_size<=200_000_000]
    temp=archive.with_suffix('.zip.partial')
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
        for f in files:z.write(f,f.name)
    with zipfile.ZipFile(temp) as z:
        if z.testzip():raise RuntimeError('Diagnostic CRC failure')
    os.replace(temp,archive)
    h=hashlib.sha256(archive.read_bytes()).hexdigest()
    (root/'test103_results.sha256').write_text(h+'  '+archive.name+'\n')
    print('TEST103_DIAGNOSTIC_ZIP',archive)
if __name__=='__main__':main()
