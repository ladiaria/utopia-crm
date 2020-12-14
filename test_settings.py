# coding=utf-8
from settings import *  # noqa

ALLOWED_HOSTS = ['testserver', ]

try:
    from local_test_settings import *  # noqa
except ImportError:
    pass
