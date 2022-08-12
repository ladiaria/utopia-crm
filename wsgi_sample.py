import os
import sys


# This Django project directory at the first item in the sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

# For Python 3.6 you must also activate your virtualenv using this commented lines:
# UTOPIA_CRM_VIRTUALENV = '/opt/venv/utopiacrm'
# activate_this_file = os.path.join(UTOPIA_CRM_VIRTUALENV, 'bin/activate_this.py')
# exec(compile(open(activate_this_file, "rb").read(), activate_this_file, 'exec'), dict(__file__=activate_this_file))

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
