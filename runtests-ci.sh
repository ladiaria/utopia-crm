#!/bin/sh
source ./runtests.sh
python -W ignore manage.py test --settings=ci_test_settings -k ${TEST_MODULES}
