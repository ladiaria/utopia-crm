#!/usr/bin/env python

from __future__ import print_function
from os import path
from glob import glob

from pexpect import spawn


if __name__ == '__main__':
    failed, alltests = [], glob('tests/test_*.py')
    for itest, test in enumerate(alltests, 1):
        module = path.splitext(path.basename(test))[0]
        print('%d/%d %s ...' % (itest, len(alltests), module), end='')
        child = spawn('nosetests --nocapture tests.%s' % module)
        try:
            child.expect('OK', timeout=60)
            print(' ok')
        except Exception:
            print(' F')
            failed.append(module)
    print()
    if failed:
        print('Please run each failed test separately with:\n')
        for module in failed:
            print('nosetests --nocapture tests.%s' % module)
        print()
    else:
        print('OK')
