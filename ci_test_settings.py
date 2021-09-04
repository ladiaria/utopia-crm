# coding=utf-8
from settings import *


DEBUG = True
ALLOWED_HOSTS = ['testserver', ]

DATABASES = {
    'default': {
        'HOST': '127.0.0.1',
        'NAME': 'utopiacrm',
        'PASSWORD': 'citest',
        'USER': 'utopiatest_django',
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
    }
}

try:
    from local_ci_test_settings import *
except ImportError:
    pass
