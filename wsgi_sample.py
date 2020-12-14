import os, sys

# This Django project directory at the first item in the sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

# Set your virtualenv path
UTOPIA_CRM_VIRTUALENV = '/opt/venv/utopiacrm'

# Avctivate it and assign the application variable
execfile(os.path.join(UTOPIA_CRM_VIRTUALENV, 'bin/activate_this.py'),
    dict(__file__=os.path.join(UTOPIA_CRM_VIRTUALENV, 'bin/activate_this.py')))

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

