#!/bin/sh
TEST_MODULES="tests.test_contact tests.test_dynamiccontactfilter tests.test_invoicing tests.test_subscriptor"
# exit now if we are being sourced by another script or shell
[[ "${#BASH_SOURCE[@]}" -gt "1" ]] && { return 0; }
python -W ignore manage.py test --settings=test_settings --keepdb ${TEST_MODULES}

