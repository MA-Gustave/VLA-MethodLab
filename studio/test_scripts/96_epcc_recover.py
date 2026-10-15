#!/usr/bin/env python3
"""Read-only EPCC Test96 status / recovery, with remote-only fallback.

A past Studio installation might not have a local launch96.json. In that case
find EPCC Test96 by its strict run ID and fetch the SHA256-verified archive.
Never submit or cancel a Slurm job.
"""
import importlib.util
import json
from pathlib import Path


def execute(ctx,params):
    if getattr(ctx.studio,'active_profile',None)!='EPCC':
        raise RuntimeError('Choose EPCC before recovering Test96')
    ctx.ensure_connected()
    root=ctx.output_dir.parent.parent
    files=sorted(root.glob('test96-epcc-8h/*/launch96.json'),reverse=True)
    path=Path(__file__).with_name('96_epcc_8h.py')
    spec=importlib.util.spec_from_file_location('epcc_test96_launcher',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for f in files:
        try:
            launch=json.loads(f.read_text(encoding='utf8'))
            if launch.get('mode')!='EPCC':continue
            outcome=module.recover(ctx,launch)
            (ctx.output_dir/'recovered_from.txt').write_text(str(f)+'\n',encoding='utf8')
            return outcome
        except (OSError,ValueError,json.JSONDecodeError):continue
    # Old launches may belong to a different PC or another Studio installation.
    # Discover the actual EPCC folder, without relying on local metadata.
    from rvvlab_epcc_results import discover_epcc_runs,select_test_run,sync_epcc_run
    runs=discover_epcc_runs(ctx.ssh,ctx.remote_name)
    chosen=select_test_run(runs,'test96')
    if chosen is None:raise RuntimeError('No remote EPCC Test96 found (test96-epcc-runs is empty)')
    ctx.log('EPCC Test96 run found on server: '+chosen['id']+
            ' state='+chosen['state']+', measurements='+str(chosen['rows']))
    if chosen['packet']:
        dest=sync_epcc_run(ctx.ssh,ctx.remote_name,chosen['id'],ctx.results_root)
        ctx.log('EPCC Test96 recovered with SHA256: '+str(dest))
        (ctx.output_dir/'recovered_from.txt').write_text('EPCC remote: '+chosen['id']+'\n',encoding='utf8')
        return {'state':chosen['state'],'run_id':chosen['id'],'packet':str(dest/'test96_results.zip')}
    # No packet yet: retrieve non-destructive evidence, never invent a result.
    with ctx.ssh.client.open_sftp() as sftp:
        for name in ('status96.json','slurm96-exit.json','studio96-build.log','builds96.json'):
            try:sftp.get(chosen['workdir']+'/'+name,str(ctx.output_dir/name))
            except OSError:pass
    ctx.log('No test96_results.zip on EPCC: downloaded available status/build logs only.')
    return {'state':chosen['state'],'run_id':chosen['id'],'packet':None,'rows':chosen['rows']}
