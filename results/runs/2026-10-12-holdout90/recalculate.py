"""Usage: python recalculate.py /path/to/unzipped/night-run [output.csv]"""
import csv, json, math, statistics, sys
from pathlib import Path
from collections import defaultdict, Counter
p=Path(sys.argv[1]); rows=list(csv.DictReader((p/'map.csv').open()))
info={x['id']:x for x in json.loads((p/'corpus_manifest.json').read_text())['scenarios']}
tags=sorted({r['variant'] for r in rows}); groups=defaultdict(dict)
for r in rows:
 k=tuple(r[x] for x in ('phase','corpus','parse_iterations','trial'))
 if r['variant'] in groups[k]:raise ValueError('Duplicate observation')
 groups[k][r['variant']]=r
base='upstream_vls256'; a='A2_quick_dispatch'
gm=lambda x:math.exp(statistics.mean(math.log(v) for v in x))
case=defaultdict(lambda:defaultdict(list))
for k,g in groups.items():
 if set(g)!=set(tags):continue
 for t in tags:
  value=float(g[t]['dom_all_gbps'])/float(g[base]['dom_all_gbps'])
  assert math.isfinite(value) and value>0
  case[k[1]][t].append(value)
values={c:{t:gm(v) for t,v in d.items()} for c,d in case.items()}
print('Observations:',len(rows),'Complete matched groups:',sum(len(g)==len(tags) for g in groups.values()),'Unique cases:',len(values))
print('Case-weighted DOM ratios:',{t:gm([v[t] for v in values.values()]) for t in tags})
print('Retrospective best-of-five / A2 (zero selection cost):',gm([max(v.values())/v[a] for v in values.values()]))
for design in sorted({i['design'] for i in info.values()}):
 vs=[v for c,v in values.items() if info[c.split('@')[0]]['design']==design]
 print(design,len(vs),gm([v[a] for v in vs]))
if len(sys.argv)>2:
 with open(sys.argv[2],'w',newline='',encoding='utf8') as f:
  w=csv.DictWriter(f,fieldnames=['corpus','design','bytes','complete_trials',*tags,'retrospective_best','best_over_A2']);w.writeheader()
  for c,v in sorted(values.items()):
   i=info[c.split('@')[0]]
   w.writerow(dict(corpus=c,design=i['design'],bytes=i['bytes'],complete_trials=len(case[c][a]),**v,retrospective_best=max(v,key=v.get),best_over_A2=max(v.values())/v[a]))
