#!/bin/zsh
export DJANGO_SETTINGS_MODULE="test_settings"
python manage.py test tests.test_subscriptor
python manage.py test tests.test_orm
