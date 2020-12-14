#!/usr/bin/env python
import os
import sys
from optparse import OptionParser

parser = OptionParser()
_, args = parser.parse_args()

if not args:
    print("usage: runview.py <app>.<module>.<view> [args]")
    sys.exit(1)

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    app, module, view = args[0].split('.')
    try:
        _m = __import__('%s.%s' % (app, module), fromlist=[module])
    except ImportError:
        sys.stderr.write("Error: Can't find module or view\n")
        sys.exit(1)
    getattr(_m, view)(*tuple([eval(arg) for arg in args[1:]]))
