# coding=utf-8
from datetime import date

from settings import *


DEBUG = True
ALLOWED_HOSTS = ['testserver', ]

DATABASES = {
    'default': {
        'HOST': '127.0.0.1',
        'NAME': 'utopia',
        'PASSWORD': 'citest',
        'USER': 'utopiatest_django',
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
    }
}
