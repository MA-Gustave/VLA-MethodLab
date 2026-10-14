#!/usr/bin/env python3
"""Dependency and import health check for RVV-VLA Lab Windows launchers.

Runs without attempting SSH, installing packages or opening a Tk window.
Return codes: 0 OK, 1 missing/broken dependency, 3 unsupported Python.
"""
import importlib
import importlib.machinery
import importlib.util
from pathlib import Path
import sys


def check(which):
    if sys.version_info < (3, 10):
        print('ERROR: Python 3.10+ is required; detected %s' % sys.version.split()[0])
        return 3

    modules = {
        'paramiko': ('paramiko',),
        'tkinter': ('tkinter',),
        'studio': ('tkinter', 'paramiko', 'rvvlab_backend', 'rvvlab_storage',
                   'rvvlab_reports', 'rvvlab_night', 'rvvlab_test_runner'),
    }
    if which not in modules:
        print('Usage: check_runtime.py {paramiko|tkinter|studio}')
        return 2

    for name in modules[which]:
        try:
            importlib.import_module(name)
        except Exception as exc:
            print('NOT READY: %s: %s: %s' % (name, type(exc).__name__, str(exc)))
            return 1

    if which == 'studio':
        file = Path(__file__).resolve().parent / 'RVV_Lab_Studio.pyw'
        if not file.is_file():
            print('NOT READY: missing GUI: ' + str(file))
            return 1
        try:
            # Import the GUI without entering main() or starting Tk().
            loader = importlib.machinery.SourceFileLoader('_rvvlab_studio_preflight', str(file))
            spec = importlib.util.spec_from_loader(loader.name, loader)
            module = importlib.util.module_from_spec(spec)
            loader.exec_module(module)
        except Exception as exc:
            print('NOT READY: Studio import: %s: %s' % (type(exc).__name__, str(exc)))
            return 1

    print('OK: ' + which)
    return 0


if __name__ == '__main__':
    sys.exit(check(sys.argv[1] if len(sys.argv) == 2 else ''))
