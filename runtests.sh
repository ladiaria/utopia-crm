#!/bin/sh
if [ -f ".env" ]; then
    source ./.env
fi
if [ -z ${TEST_MODULES+x} ]; then
    TEST_MODULES="tests.test_contact tests.test_dynamiccontactfilter tests.test_invoicing tests.test_subscriptor tests.test_email_replacements tests.test_automated_activation_disabling"
fi
if [ -n "$EXTRA_TEST_MODULES" ]; then
    TEST_MODULES="$TEST_MODULES $EXTRA_TEST_MODULES"
fi
python -W ignore manage.py compilemessages --settings=test_settings
# exit now if we are being sourced by another script or shell (or utopia_crm_exit envvar=1 for zsh compatibility)
[[ "${#BASH_SOURCE[@]}" -gt "1" ]] && { return 0; }
[[ $utopia_crm_exit = 1 ]] && { return 0; }
if [[ -z "${TEST_MODULES// }" ]]; then
    echo "No tests to run"
    exit 0
fi
python -W ignore manage.py test --settings=test_settings --exclude-tag broken --keepdb ${TEST_MODULES}
