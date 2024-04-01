#!/bin/sh
TEST_MODULES="tests.test_contact tests.test_dynamiccontactfilter tests.test_invoicing tests.test_subscriptor tests.test_email_replacements"
# exit now if we are being sourced by another script or shell (or utopia_crm_exit envvar=1 for zsh compatibility)
[[ "${#BASH_SOURCE[@]}" -gt "1" ]] && { return 0; }
[[ $utopia_crm_exit = 1 ]] && { return 0; }
python -W ignore manage.py test --settings=test_settings --keepdb ${TEST_MODULES}
