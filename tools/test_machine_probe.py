#!/usr/bin/env python3
"""Offline smoke tests for hardware inventory/bench comparator; no network."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

PROBE = Path(__file__).with_name('machine_probe.py')


def invoke(*args):
    result = subprocess.run([sys.executable, str(PROBE), *map(str,args)],
                            text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, (result.stdout, result.stderr)
    return result.stdout


with tempfile.TemporaryDirectory(prefix='machine_probe_test_') as temp:
    root = Path(temp)
    target = root/'inventory'
    invoke('--label', 'epcc-login', '--specs-only', '--output-dir',target)
    files = list(target.glob('*.json'))
    assert len(files) == 1
    a = json.loads(files[0].read_text())
    assert a['schema'] == 'rvvlab-machine-probe-v1'
    assert a['label'] == 'epcc-login'
    assert not a['benchmarks']
    assert a['hardware']['architecture']
    assert a['hardware']['cpu_logical'] is None or a['hardware']['cpu_logical'] >= 1
    assert a['hardware']['disk']['free_gib'] > 0
    assert 'Architecture' in list(target.glob('*.md'))[0].read_text()

    target2 = root/'pythononly'
    invoke('--label', 'cloud-v', '--no-native', '--output-dir',target2)
    other = json.loads(list(target2.glob('*.json'))[0].read_text())
    assert other['benchmarks']['python_json_mb_per_sec'] > 0
    assert 'native_memcpy_gib_per_sec' not in other['benchmarks']
    target3 = root/'compare'
    content = invoke('--compare',files[0],list(target2.glob('*.json'))[0], '--output-dir',target3)
    assert 'Machine comparison' in content and (target3/'machine_comparison.md').exists()

    # Test ratio direction and absence of fabricated values for missing tests.
    import importlib.util
    spec = importlib.util.spec_from_file_location('machine_probe', PROBE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    first = dict(a)
    second = dict(other)
    first['benchmarks'] = {'native_cpu_million_iterations_per_sec': 100.0,
                           'native_memcpy_gib_per_sec': 4.0,
                           'python_json_mb_per_sec': 10.0}
    second['benchmarks'] = {'native_cpu_million_iterations_per_sec': 80.0,
                            'native_memcpy_gib_per_sec': 8.0,
                            'python_json_mb_per_sec': 15.0}
    txt = mod.compare(first,second)
    assert '-20.0%' in txt and '+100.0%' in txt and '+50.0%' in txt, txt

print('PASS: hardware inventory, safe specs-only, Python JSON benchmark, reports, two-machine comparison and percentage direction')
