#!/usr/bin/env python3
"""Test97 read-only analysis: bracketed paired ratios and scenario-cluster CIs.

No automatic promotion. Bootstrap units are case templates, not trial repetitions.
"""
from __future__ import annotations
import argparse,csv,io,json,math,random,statistics,zipfile
from pathlib import Path
from collections import defaultdict

METRICS=('dom_all_gbps','stage1_gbps','stage2_gbps')
CANDIDATES=('A2_G5120','A2_G6144','A2_G7168','A2_G8192','A2_G10240')

def load(folder):
    folder=Path(folder)
    if folder.suffix.lower()=='.zip':
        with zipfile.ZipFile(folder) as z:
            if z.testzip() is not None:raise ValueError('ZIP integrity error')
            rows=list(csv.DictReader(io.StringIO(z.read('results97.csv').decode())))
            status=json.loads(z.read('status97.json'))
    else:
        with (folder/'results97.csv').open(newline='',encoding='utf8') as f:rows=list(csv.DictReader(f))
        status=json.loads((folder/'status97.json').read_text())
    return rows,status

def pairs(rows):
    by_group=defaultdict(dict)
    for r in rows:
        if r['variant'] in by_group[r['group']]:raise ValueError('Duplicate group '+r['group']+' / '+r['variant'])
        by_group[r['group']][r['variant']]=r
    ans=[]; drift=[];complete=0
    for gid,g in by_group.items():
        if not all(x in g for x in ('A2_REF','A2_REF_POST',*CANDIDATES)):continue
        a,c=g['A2_REF'],g['A2_REF_POST'];complete+=1
        for k in CANDIDATES:
            b=g[k]
            for field in ('group','phase','json_sha256','bytes','iterations','family','scenario','target_bytes'):
                if a[field]!=b[field] or c[field]!=b[field]:raise ValueError('Unpaired '+gid+': '+field)
            values=[]
            for m in METRICS:
                x,y,z=(float(item[m]) for item in (a,b,c))
                if not all(math.isfinite(v) and v>0 for v in (x,y,z)):raise ValueError('Invalid '+m)
                values.append(math.log(y)-.5*(math.log(x)+math.log(z)))
                if m=='dom_all_gbps' and k==CANDIDATES[0]:drift.append((a['phase'],abs(math.log(z/x))))
            ans.append({'group':gid,'phase':a['phase'],'variant':k,'scenario':a['scenario'],
                        'family':a['family'],'bytes':int(a['bytes']),
                        'case':(a['scenario'],a['family'],a['target_bytes']),
                        'values':values})
    return ans,complete,len(by_group),drift

def ci_cluster(rows,metric=0,boot=1000,seed=1050):
    if not rows:return None
    cases=defaultdict(list)
    for row in rows:cases[row['case']].append(row['values'][metric])
    vals=[statistics.mean(q) for q in cases.values()]
    mid=math.exp(statistics.mean(vals))
    if len(vals)<3:return mid,None,None,len(vals)
    rng=random.Random(seed)
    samples=[]
    for i in range(boot):
        samples.append(math.exp(statistics.mean(vals[rng.randrange(len(vals))] for _ in vals)))
    samples.sort()
    return mid,samples[int(.025*boot)],samples[int(.975*boot)],len(vals)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('input',help='test97_results.zip or run folder')
    p.add_argument('--output',default='DECISIONS_97.md')
    args=p.parse_args()
    rows,status=load(args.input)
    data,complete,total,drift=pairs(rows)
    lines=['# Test 97 — Analyse indépendante du seuil A2','','État serveur : **'+status.get('state','inconnu')+'** ; validation : **'+str(status.get('validated'))+'**',
       'Groupes appariés complets : **'+str(complete)+' / '+str(total)+'** ; mesures : **'+str(len(rows))+'**.','',
       'Ratio supérieur à 1,000× : candidat plus rapide. Référence : moyenne géométrique des deux mesures A2 encadrantes.','',
       '| Phase | Périmètre | Seuil | Paires | Types | DOM/A2 | IC 95 % (types) | Stage1/A2 | Stage2/A2 |',
       '|---|---|---:|---:|---:|---:|---|---:|---:|']
    for phase in ('holdout','train'):
        for scope in ('all','boundary','anchor','real_json','4096-8191','other_sizes'):
            for v in CANDIDATES:
                q=[x for x in data if x['phase']==phase and x['variant']==v and
                   (scope=='all' or (scope=='4096-8191' and 4096<=x['bytes']<8192) or
                    (scope=='other_sizes' and not 4096<=x['bytes']<8192) or x['scenario']==scope)]
                if not q:continue
                dom,lo,hi,typ=ci_cluster(q,seed=97)
                st1,*_=ci_cluster(q,1,boot=100)
                st2,*_=ci_cluster(q,2,boot=100)
                conf=(f'{lo:.4f}–{hi:.4f}×' if lo else 'non estimable')
                lines.append(f'| {phase} | {scope} | `{v}` | {len(q)} | {typ} | {dom:.4f}× | {conf} | {st1:.4f}× | {st2:.4f}× |')
    hold=[(v,ci_cluster([x for x in data if x['phase']=='holdout' and x['variant']==v])) for v in CANDIDATES]
    hold=[(v,q) for v,q in hold if q]
    lines+=['','## Décision méthodologique','','Le classement du holdout est exploratoire tant que le corpus de production et des conditions isolées indépendantes ne sont pas confirmés. Aucun changement de code n’est automatique.',
       'Les intervalles bootstrap regroupent les répétitions par type de cas (scénario / famille / taille). Ils ne sont pas corrigés pour comparaisons multiples.']
    if drift:
        lines.append(f"Dérive A2 avant/après : médiane absolue {100*(math.exp(statistics.median(d for ph,d in drift if ph=='holdout'))-1):.2f}% sur le holdout." if any(ph=='holdout' for ph,d in drift) else 'Pas de mesure de dérive holdout.')
    if hold:lines.append('Meilleur ratio DOM global *mesuré* sur le holdout : '+max(hold,key=lambda v:v[1][0])[0]+' ; à confirmer avant promotion.')
    if status.get('state')!='completed' or status.get('validated') is not True:lines.append('**ATTENTION : résultats non finalisés, aucune conclusion à promouvoir.**')
    Path(args.output).write_text('\n'.join(lines)+'\n',encoding='utf8')
    print('REPORT',args.output,'complete_pairs',complete,'rows',len(rows))

if __name__=='__main__':main()
