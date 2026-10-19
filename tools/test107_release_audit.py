#!/usr/bin/env python3
"""Test107: offline, fail-closed release audit of both completed Test106 runs.

No SSH, benchmarks, installs, network or source-code mutation. Python standard library.
Exit code 0: evidence valid, with an explicit CI status (even when pending).
Exit code 2: evidence missing, tampered, inconsistent or release regression.
"""
from __future__ import annotations
import argparse, collections, csv, hashlib, io, json, math, pathlib, statistics, sys, zipfile
from datetime import datetime, timezone

VARS=('OFFICIAL_504','A2_ORIGINAL','VP_STABLE','VP_SIMPLE','VP_NL4')
REQ=('status106.json','machine106.json','builds106.json','results106.csv',
     'conformance106.json','conformance106.csv','public_gate106.json',
     'corpus_manifest106.json','conformance_manifest106.json','inputs106.json')
EXPECTED_RC='513dbf6ea2241d469ade18a354e18a77303d66ce9d6794fb8595ee59e01f0388'
EXPECTED_FORK='fdaea284a48b30ab3e912e1cd3580e920fe186a229faabba97d9b24eed095e16'
EXPECTED_PLAN='7ebd7d2f4606c9ed9db77bcced50371e669698e5278f1afc4e5369fc5b4e7f4e'
EXPECTED_UPSTREAM='3b0b2b53aaffb46208817821dce2cd47a5e6bb2a'
EXPECTED_SUITE='1ef36fa01286573e846ac449e8683f8833c5b26a'
PUBLIC_COMMIT='4197c425e857f0ec38e89822fdd0bd9ea21f4daf'
MAX_UNCOMPRESSED=400_000_000

class AuditError(RuntimeError):pass

def sha_bytes(x):return hashlib.sha256(x).hexdigest()
def sha_file(path):
    h=hashlib.sha256()
    with pathlib.Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def require(ok,msg):
    if not ok:raise AuditError(msg)
def load_json(z,name):return json.loads(z.read(name))
def collect(z,filename):
    infos=z.infolist();names=[i.filename for i in infos]
    require(len(names)==len(set(names)),'Duplicate ZIP entries in '+filename)
    require(set(REQ)<=set(names),'Missing Test106 members in '+filename)
    require(all(not x.is_dir() and not x.flag_bits & 1 and not x.filename.startswith('/') and '..' not in pathlib.PurePosixPath(x.filename).parts for x in infos),'Unsafe ZIP member in '+filename)
    require(sum(i.file_size for i in infos)<MAX_UNCOMPRESSED,'Archive exceeds decompressed size bound')
    require(z.testzip() is None,'ZIP CRC failed: '+filename)

def audit_one(path,expected_machine):
    path=pathlib.Path(path)
    require(path.is_file(),'Missing '+expected_machine+' archive: '+str(path))
    with zipfile.ZipFile(path) as z:
        collect(z,str(path))
        status=load_json(z,'status106.json');machine=load_json(z,'machine106.json')
        builds=load_json(z,'builds106.json');conf=load_json(z,'conformance106.json')
        gate=load_json(z,'public_gate106.json');corpus=load_json(z,'corpus_manifest106.json')
        suite=load_json(z,'conformance_manifest106.json');inputs=load_json(z,'inputs106.json')
        require(machine.get('machine')==expected_machine and machine.get('arch')=='riscv64',expected_machine+': wrong machine or architecture')
        require(status.get('state')=='completed' and status.get('validated') is True,expected_machine+': Test106 not completed/validated')
        require(status.get('machine')==expected_machine,expected_machine+': status machine mismatch')
        require(status.get('rows',0)>0 and status.get('groups',0)>0,expected_machine+': empty run')
        require(builds.get('candidate',{}).get('sha256')==EXPECTED_RC,expected_machine+': unexpected release candidate')
        require(builds.get('original_src_sha256')==EXPECTED_FORK and builds.get('original_plan_sha256')==EXPECTED_PLAN,expected_machine+': unexpected A2 fork')
        require(builds.get('official_commit')==EXPECTED_UPSTREAM,expected_machine+': unexpected upstream baseline')
        bs=builds['builds'];require(set(bs)==set(VARS),expected_machine+': missing build variant')
        require(bs['VP_STABLE']['sha256']==bs['A2_ORIGINAL']['sha256'],expected_machine+': stable binary differs from A2')
        require(all(len(bs[v]['sha256'])==64 for v in VARS),expected_machine+': missing binary sha256')
        require(all(bs[v]['backend']=='rvv' for v in VARS if v!='OFFICIAL_504') and bs['OFFICIAL_504']['backend']=='fallback',expected_machine+': wrong backend')
        require(all(bs[v]['src_simdjson_sha256']==EXPECTED_FORK for v in ('A2_ORIGINAL','VP_STABLE')),expected_machine+': unexpected A2 source')
        require(corpus.get('upstream_commit')==PUBLIC_COMMIT and len(corpus.get('files',[]))==18,expected_machine+': unexpected public corpus')
        require(suite.get('upstream_commit')==EXPECTED_SUITE,expected_machine+': wrong JSONTestSuite commit')
        require(inputs.get('public_count')==18 and inputs.get('valid_jsonsuite_count')==95,expected_machine+': wrong corpus counts')
        require(conf.get('checks')==340 and conf.get('cross_variant_disagreements')==0 and conf.get('expected_mismatches')==0 and conf.get('promotion_eligible') is True,expected_machine+': conformance fails')
        with z.open('conformance106.csv') as f:
            cf=list(csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig',newline='')))
        require(len(cf)==340 and len({r['name'] for r in cf})==340,expected_machine+': conformance CSV mismatch')
        require(all(r['parity']=='True' and r['expectation_pass']=='True' for r in cf),expected_machine+': conformance row failed')
        all_files={x['name']:x for x in corpus['files']}
        rows_by_group=collections.defaultdict(list);counter=collections.Counter();docs=collections.defaultdict(lambda:collections.defaultdict(list))
        with z.open('results106.csv') as f:
            reader=csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig',newline=''))
            for row in reader:
                key=(row['phase'],row['round'],row['group'],row['document'])
                rows_by_group[key].append(row);counter[row['variant']]+=1
                if row['stratum']=='public_original':
                    fn=row['document'].split('/')[-1]
                    require(fn in all_files and row['sha256']==all_files[fn]['sha256'],expected_machine+': corrupt public JSON reference '+fn)
                for field in ('dom_gbps','stage1_gbps','stage2_gbps'):
                    val=float(row[field]);require(math.isfinite(val) and val>0,expected_machine+': nonpositive/NaN throughput')
        require(sum(counter.values())==status['rows'] and len(rows_by_group)==status['groups'],expected_machine+': result row/group count mismatch')
        require(set(counter)==set(VARS) and len(set(counter.values()))==1,expected_machine+': unbalanced variants')
        for key,group in rows_by_group.items():
            require(len(group)==len(VARS) and {r['variant'] for r in group}==set(VARS),expected_machine+': missing/duplicate paired variant '+str(key))
            if key[0]!='confirm' or group[0]['stratum']!='public_original':continue
            lookup={r['variant']:r for r in group}
            for v in ('A2_ORIGINAL','VP_STABLE','VP_SIMPLE','VP_NL4'):
                for reference in (('OFFICIAL_504',) if v=='A2_ORIGINAL' else ('OFFICIAL_504','A2_ORIGINAL')):
                    a=float(lookup[v]['dom_gbps']);b=float(lookup[reference]['dom_gbps'])
                    docs[v,reference][key[3]].append(math.log(a/b))
        public={}
        for (var,ref),d in docs.items():
            require(len(d)==18 and all(len(vals)>0 for vals in d.values()),expected_machine+': missing confirm public file')
            means={name:statistics.mean(vals) for name,vals in d.items()}
            public[var+'/'+ref]={'geomean':math.exp(statistics.mean(means.values())),
                                  'per_doc':{n:math.exp(m) for n,m in sorted(means.items())},
                                  'min_doc':min(math.exp(m) for m in means.values())}
        stable=public['VP_STABLE/A2_ORIGINAL'];official=public['VP_STABLE/OFFICIAL_504']
        require(stable['geomean']>=.995 and stable['min_doc']>=.98,expected_machine+': stable performance release gate failed')
        declared=gate['variants']['VP_STABLE']
        require(abs(declared['geomean_vs_original_a2']-stable['geomean'])<.001,expected_machine+': reported and independently calculated geomeans disagree')
        # Verify individual declared public files using an independent pass over raw rows.
        reported=gate['per_document_ratios']['VP_STABLE']['A2_ORIGINAL']
        require(len(reported)==18 and all(abs(v-stable['per_doc'].get(n,0))<.005 for n,v in reported.items()),expected_machine+': reported/verified per-document ratios diverge')
        return {'path':str(path),'zip_sha256':sha_file(path),'machine':machine,'status':status,'builds':builds,
                'conformance':conf,'public':public,'corpus_fingerprint':sorted((n,r['sha256']) for n,r in all_files.items()),
                'suite_commit':suite['upstream_commit'],'candidate_sha256':builds['candidate']['sha256'],
                'harness_sha256':builds['harness_sha256'],'rows':sum(counter.values())}

def audit_pair(cloud,epcc,vectorpath=None,ci_json=None):
    c=audit_one(cloud,'bpf3-16G-2');e=audit_one(epcc,'rvc02')
    require(c['corpus_fingerprint']==e['corpus_fingerprint'],'Different public JSON across machines')
    require(c['suite_commit']==e['suite_commit'] and c['candidate_sha256']==e['candidate_sha256'],'Different release candidate or conformance commit')
    require(c['harness_sha256']==e['harness_sha256'],'Different benchmark harness source')
    package={'state':'NOT_PROVIDED','sha256':None}
    if vectorpath:
        f=pathlib.Path(vectorpath);require(f.is_file(),'Missing VectorPath release archive')
        with zipfile.ZipFile(f) as z:
            collect_release(z)
            require('src/rvv/engines/engine_plan.h' in z.namelist(),'Not a VectorPath source patch')
            manifest=json.loads(z.read('VECTORPATH_RC_PATCH_MANIFEST.json'))
            require(manifest.get('schema')==1,'Bad VectorPath distribution manifest')
            files={item['path']:item for item in manifest.get('files',[])}
            require(all(x['path'] in z.namelist() and sha_bytes(z.read(x['path']))==x['new_sha256'] for x in manifest['files']),'Distribution payload digests differ from manifest')
            # SHA-256 for the exact five C++ files used by Test106's pinned RC.
            pinned={'include/simdjson/implementation_detection.h':'e174d29e3fa839c48b57b643a2edba422260e47bf0f3d3ad4b65673428db0eb9',
             'src/generic/stage2/stringparsing.h':'2d2c6ea59d34c3c7b5d04078eb51acfee81c986f64b582a14cfe5dfe926decff',
             'src/rvv/engines/engine_plan.h':'d289fbaacc53ce5139b9bc72a9262155b96d23263ab324500d1671192a32785a',
             'src/rvv/engines/structural_writers.h':'8029f462063c97f270de844bbc61299975d5160db0acde97276fe31a07b2ef1f',
             'src/rvv/string_scanner.h':'12ef1804f6a3b26ee915b72ffc979f111698c44b16eb407363186a6992143d22'}
            require(all(files.get(k,{}).get('new_sha256')==v for k,v in pinned.items()),'VectorPath source payload differs from Test106 release candidate')
            package={'state':'DISTRIBUTION_VERIFIED','sha256':sha_file(f),'file_hashes':{k:v['new_sha256'] for k,v in files.items()}}
    ci={'state':'NOT_VERIFIED','note':'GitHub Actions #74 failed and the exact failing step is not independently established. Fuzz/Valgrind not proven green.'}
    if ci_json:
        obj=json.loads(pathlib.Path(ci_json).read_text(encoding='utf8'))
        if (obj.get('conclusion')=='success' and obj.get('status')=='completed' and
            obj.get('name')=='Fuzz and run valgrind' and obj.get('headSha') and obj.get('url')):
            ci={'state':'REPORTED_PASS_UNVERIFIED_SOURCE_COVERAGE','evidence':obj,'note':'GitHub CLI/export evidence reports success; verify repository/commit and relevance to the VectorPath release manually.'}
        else:ci={'state':'NOT_VERIFIED','note':'CI evidence is missing a completed successful fuzz+Valgrind workflow'}
    result={'schema':1,'test':107,'purpose':'release evidence audit; NO NEW NATIVE BENCHMARK',
            'generated_utc':datetime.now(timezone.utc).isoformat(),
            'release_candidate_sha256':EXPECTED_RC,'vectorpath_package':package,
            'machines':{},'sum_rows':c['rows']+e['rows'],'ci':ci,
            'engine_qualification':'PASS','ship_authorization':'HOLD_CI_AND_RELEASE_SIGNOFF'}
    for k,r in [('Cloud-V',c),('EPCC',e)]:
        stable=r['public']['VP_STABLE/OFFICIAL_504']['geomean']
        result['machines'][k]={'machine':r['machine']['machine'],'compiler':r['machine']['compiler'],
          'test106_results_sha256':r['zip_sha256'],'rows':r['rows'],
          'stable_binary_sha256':r['builds']['builds']['VP_STABLE']['sha256'],
          'original_binary_sha256':r['builds']['builds']['A2_ORIGINAL']['sha256'],
          'public_stable_vs_official':stable,'gain_pct':(stable-1)*100,
          'public_stable_vs_original':r['public']['VP_STABLE/A2_ORIGINAL']['geomean'],
          'worst_public_file_ratio':r['public']['VP_STABLE/A2_ORIGINAL']['min_doc'],
          'conformance_checked':r['conformance']['checks']}
    return result

def collect_release(z):
    names=z.namelist();require(len(names)==len(set(names)) and z.testzip() is None,'Bad VectorPath ZIP')
    require(sum(x.file_size for x in z.infolist())<128_000_000,'Oversize VectorPath ZIP')

def report(r):
    lines=['# Test 107 — Formal release qualification (evidence audit)','',
      '**Scope:** An independent audit of completed Test106 evidence. **No native code was executed by Test107.**','',
      '| Target | Stable vs simdjson 5.0.4 fallback | Stable vs original A2 | Worst document vs A2 | Test106 rows | JSONTestSuite |',
      '|---|---:|---:|---:|---:|---:|']
    for name,x in r['machines'].items():
        lines.append(f"| {name} | {x['gain_pct']:+.2f}% | {(x['public_stable_vs_original']-1)*100:+.3f}% | {(x['worst_public_file_ratio']-1)*100:+.2f}% | {x['rows']:,} | {x['conformance_checked']} / 340 |")
    lines += ['',f"**Engine qualification:** {r['engine_qualification']}",
      f"**Release authorization:** {r['ship_authorization']}",
      f"**CI proof:** {r['ci']['state']}",
      f"**VectorPath distribution ZIP:** {r['vectorpath_package']['state']}",'',
      'The A2 original and VectorPath stable binaries are byte-identical on each machine.',
      'The 18 public JSON input digests and harness hashes are identical across targets.',
      f"Test106 paired rows audited: {r['sum_rows']:,}.", '',
      '## CI / safety qualification', '', r['ci']['note'], '',
      'A historical CI failure neither invalidates these completed native benchmarks nor certifies fuzzing/Valgrind.',
      'A green workflow in another repository/commit is **not** proof that the frozen VectorPath sources passed fuzzing and Valgrind.',
      '', '## Release rules', '',
      '1. Keep A2 / 16 KiB / packed OFF, original Stage 2. SIMPLE_RUN and NL4 remain optional.',
      '2. Do not modify the frozen VectorPath source tree unless a correctness defect is found.',
      '3. Verify fuzz/Valgrind or independent equivalent against the actual release candidate before final ship sign-off.',
      '4. Tag the exact git commit and archive SHA256. A code change after this audit requires relevant requalification.',
      '5. Do not reinterpret Test89 (+64.1% vs a different baseline/corpus) as a regression against Test106.', '',
      '## Artifact provenance','',
      f"- Pinned Test106 RC patch SHA256: `{r['release_candidate_sha256']}`",
      f"- VectorPath distribution SHA256: `{r['vectorpath_package']['sha256']}`", '']
    for name,x in r['machines'].items():
        lines.extend([f"- {name}: evidence `{x['test106_results_sha256']}`; stable binary `{x['stable_binary_sha256']}`"])
    return '\n'.join(lines)+'\n'

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cloudv',required=True);p.add_argument('--epcc',required=True)
    p.add_argument('--vectorpath');p.add_argument('--ci-run-json');p.add_argument('--output',required=True)
    a=p.parse_args(argv)
    out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=True)
    try:
        result=audit_pair(a.cloudv,a.epcc,a.vectorpath,a.ci_run_json)
        verdict=report(result)
        (out/'TEST107_RELEASE_AUDIT.md').write_text(verdict,encoding='utf8')
        (out/'TEST107_RELEASE_AUDIT.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf8')
        zpath=out/'test107_release_audit.zip'
        with zipfile.ZipFile(zpath,'w',compression=zipfile.ZIP_DEFLATED) as z:
            z.write(out/'TEST107_RELEASE_AUDIT.md',arcname='TEST107_RELEASE_AUDIT.md')
            z.write(out/'TEST107_RELEASE_AUDIT.json',arcname='TEST107_RELEASE_AUDIT.json')
        print('TEST107 ENGINE PASS; RELEASE HOLD pending independent CI/source coverage; report '+str(zpath))
        return 0
    except (AuditError,OSError,ValueError,KeyError,zipfile.BadZipFile) as exc:
        fail={'state':'EVIDENCE_INVALID','error':str(exc),'release_authorized':False}
        (out/'TEST107_FAILURE.json').write_text(json.dumps(fail,indent=2)+'\n',encoding='utf8')
        print('TEST107 EVIDENCE FAIL: '+str(exc),file=sys.stderr)
        return 2
if __name__=='__main__':sys.exit(main())
