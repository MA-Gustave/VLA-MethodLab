#!/usr/bin/env python3
"""Read-only Test97 recovery; no job submission."""
import importlib.util
from pathlib import Path

def execute(ctx,params):
    ctx.ensure_connected()
    if getattr(ctx.studio,'active_profile',None)!='EPCC':raise RuntimeError('Choose EPCC')
    from rvvlab_epcc_results import discover_epcc_runs,select_test_run,sync_epcc_run
    rows=discover_epcc_runs(ctx.ssh,ctx.remote_name)
    run=select_test_run(rows,'test97')
    if not run:raise RuntimeError('No Test97 runs on EPCC yet')
    ctx.log('Test97 '+run['id']+' state='+run['state'])
    if run['packet']:
        folder=sync_epcc_run(ctx.ssh,ctx.remote_name,run['id'],ctx.results_root)
        return {'state':run['state'],'run_id':run['id'],'packet':str(folder/'test97_results.zip')}
    with ctx.ssh.client.open_sftp() as sftp:
        for name in ('status97.json','slurm97-exit.json','studio97-build.log','builds97.json'):
            try:sftp.get(run['workdir']+'/'+name,str(ctx.output_dir/name))
            except OSError:pass
    return {'state':run['state'],'run_id':run['id'],'rows':run['rows'],'packet':None}
