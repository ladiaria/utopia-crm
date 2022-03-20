# coding=utf-8
from settings import *  # noqa
from local_settings import *  # noqa

ALLOWED_HOSTS = ['testserver', ]
IGNORE_WEB_UPDATE_NEWSLETTERS = True

try:
    from local_test_settings import *  # noqa
except ImportError:
    pass
