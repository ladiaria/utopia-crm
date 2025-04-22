# coding=utf-8
from settings import *  # noqa
from local_settings import *  # noqa


ALLOWED_HOSTS = ['testserver', ]
LANGUAGE_CODE = 'en-us'
IGNORE_WEB_UPDATE_NEWSLETTERS = True  # TODO: explain this setting


try:
    from local_test_settings import *  # noqa
except ImportError:
    pass
