#!/usr/bin/env python3
"""Post-run Test96 paired analysis from verified result ZIP or run directory.
Reads data only. Confidence bounds bootstrap case types (not individual repeated trials).
"""
from __future__ import annotations
import argparse,csv,hashlib,io,json,math,random,statistics,zipfile
from collections import defaultdict
from pathlib import Path
METRICS=('dom_all_gbps','stage1_gbps','stage2_gbps')
VARIANTS=('A2_CTL','A2_IDX','A2_BOTH','A2_ESC','A2_G2048','A2_G8192')

def load(path):
    path=Path(path)
    if path.suffix=='.zip':
        with zipfile.ZipFile(path) as z:
            if z.testzip():raise RuntimeError('Corrupt ZIP')
            rows=list(csv.DictReader(io.StringIO(z.read('results96.csv').decode('utf8'))))
            status=json.loads(z.read('status96.json'))
            builds=json.loads(z.read('builds96.json'))
    else:
        with (path/'results96.csv').open(newline='',encoding='utf8') as f:rows=list(csv.DictReader(f))
        status=json.loads((path/'status96.json').read_text())
        builds=json.loads((path/'builds96.json').read_text())
    return rows,status,builds

def paired(rows):
    groups=defaultdict(dict)
    for r in rows:
        if r['variant'] in groups[r['group']]:raise ValueError('Duplicate group/variant '+r['group'])
        groups[r['group']][r['variant']]=r
    pairs=[]
    for group,variants in groups.items():
        base=variants.get('A2_REF')
        if base is None:continue
        for name in VARIANTS:
            candidate=variants.get(name)
            if not candidate:continue
            # The same document, iterations and group must have been used.
            for field in ('phase','scenario','family','target_bytes','json_sha256','bytes','iterations'):
                if base[field]!=candidate[field]:raise ValueError('Pair is not identical: '+group+' '+field)
            ratios={}
            for metric in METRICS:
                b=float(base[metric]);v=float(candidate[metric])
                if not all(math.isfinite(x) and x>0 for x in (b,v)):raise ValueError('Invalid throughput')
                ratios[metric]=math.log(v/b)
            pairs.append(dict(variant=name,phase=base['phase'],scenario=base['scenario'],family=base['family'],target=int(base['target_bytes']),group=group,logs=ratios))
    return pairs,len(groups)

def bootstrap_case_ci(items,metric,seed=1234,count=1500):
    """Case-cluster CI. Each distinct (scenario/family/target) is one unit;
    within each, average all repetitions. This does not pretend repetitions
    of a single synthetic shape are independent external workload samples.
    """
    bycase=defaultdict(list)
    for p in items:bycase[(p['scenario'],p['family'],p['target'])].append(p['logs'][metric])
    means=[statistics.mean(v) for k,v in sorted(bycase.items())]
    centre=math.exp(statistics.mean(means))
    if len(means)<3:return centre,None,None,len(means)
    rng=random.Random(seed);sampled=[]
    for _ in range(count):
        draw=[means[rng.randrange(len(means))] for _ in means]
        sampled.append(math.exp(statistics.mean(draw)))
    sampled.sort();return centre,sampled[int(.025*count)],sampled[int(.975*count)],len(means)

def main():
    parser=argparse.ArgumentParser(description='Test96 8h: paired holdout and stage analysis')
    parser.add_argument('results',help='test96_results.zip or native results directory')
    parser.add_argument('--output',default='DECISIONS_96.md')
    args=parser.parse_args();rows,status,builds=load(args.results)
    pairs,groups=paired(rows)
    lines=['# Test 96 — analyses appariées et décisions','','État distant : **'+str(status.get('state','unknown'))+'** ; lignes : '+str(len(rows))+' ; groupes : '+str(groups),
           'Constructions passées : '+', '.join(k for k,v in builds.get('builds',{}).items() if v.get('result')=='PASS'),'',
           '**Sens des ratios :** supérieur à 1,000× = candidate plus rapide que A2_REF. Tous les ratios sont sur des JSON strictement appariés.','',
           '## Résultats indépendants holdout (dernières 2 heures)','',
           '| Variante | Périmètre | Paires | Types de cas | DOM/A2 | IC bootstrap 95 % (types) | Stage1/A2 | Stage2/A2 |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    for phase in ('holdout','train'):
        if phase=='train':
            lines+=['','## Résultats exploration / entraînement','','| Variante | Périmètre | Paires | Types de cas | DOM/A2 | IC bootstrap 95 % (types) | Stage1/A2 | Stage2/A2 |',
                 '|---|---|---:|---:|---:|---:|---:|---:|']
        for variant in VARIANTS:
            for label,fn in [('all',lambda p:True),('anchor',lambda p:p['scenario']=='anchor'),('boundary',lambda p:p['scenario']=='boundary'),('region_mix',lambda p:p['scenario']=='region_mix'),('utf8',lambda p:p['family']=='utf8'),('nested',lambda p:p['family']=='nested'),('boolnull',lambda p:p['family']=='boolnull'),('4095 / 4096 / 4097',lambda p:p['target'] in (4095,4096,4097))]:
                data=[p for p in pairs if p['phase']==phase and p['variant']==variant and fn(p)]
                if not data:continue
                centre,lo,hi,types=bootstrap_case_ci(data,'dom_all_gbps')
                s1,_,_,_=bootstrap_case_ci(data,'stage1_gbps');s2,_,_,_=bootstrap_case_ci(data,'stage2_gbps')
                interval=f'{lo:.4f}–{hi:.4f}×' if lo is not None else '— (<3 types)'
                lines.append(f'| `{variant}` | {label} | {len(data)} | {types} | {centre:.4f}× | {interval} | {s1:.4f}× | {s2:.4f}× |')
    lines+=['','## Lecture et limites','',
         '- Les types de cas sont des groupes `(scenario, family, taille cible)` ; moyenne géométrique d’abord dans chaque type, puis entre types. Le poids des répétitions brutes diffère donc des rapports du runner.',
         '- Le bootstrap 95 % est exploratoire, **non corrigé** pour plusieurs comparaisons et non généralisable à des JSON de production.',
         '- Les tailles frontières synthétiques sont surreprésentées dans `all` ; utiliser `anchor` pour la tendance multi-familles, et `boundary` pour l’étude du seuil.',
         '- Toutes les variantes packed actives passent par un header overlay expérimental. Comparer les résultats entre variantes Test96 ; ne pas les identifier à `packed_plain` du Test94.',
         '- Aucun gain n’est considéré validé si le statut n’est pas `completed`, si la correction différentielle a échoué, si le holdout n’est pas représentatif, ou si UTF-8 régresse fortement.',
         '- Confirmer toute victoire sur des JSON de production et une répétition avec des graines entièrement nouvelles avant déploiement.','']
    if status.get('state')!='completed':lines.insert(3,'**ATTENTION : campagne incomplète ou interrompue ; classements provisoires.**')
    dest=Path(args.output);dest.write_text('\n'.join(lines),encoding='utf8')
    print('Created',dest, '; rows',len(rows),'paired',len(pairs))
if __name__=='__main__':main()
