#!/bin/zsh
export DJANGO_SETTINGS_MODULE="test_settings"
python manage.py test tests.test_contact tests.test_dynamiccontactfilter tests.test_invoicing tests.test_subscriptor

