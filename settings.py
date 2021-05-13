# coding: utf-8
# Django settings for utopia-crm project.
import os
import chartkick
from django.utils.translation import ugettext_lazy as _

LOGIN_URL = '/user/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
DEBUG = False
DEBUG_INVOICING = True  # prints debug data for invoicing in uwsgi log

SERVER_EMAIL = 'email@example.com'
ADMINS = (
    ('Utopia Admins', SERVER_EMAIL),
)
MANAGERS = ADMINS
# SMTP email host
EMAIL_HOST = 'smtp.example.com'
# supervision email.
SUPERVISION_EMAIL = u'example@example.com'
DEFAULT_EMAIL_FROM = SUPERVISION_EMAIL

ALLOWED_HOSTS = []

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Local time zone for this installation. All choices can be found here:
# http://www.postgresql.org/docs/current/static/datetime-keywords.html#DATETIME-TIMEZONE-SET-TABLE
TIME_ZONE = 'America/Montevideo'
DATE_FORMAT = 'Y-m-d'

# Language code for this installation. All choices can be found here:
# http://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
# http://blogs.law.harvard.edu/tech/stories/storyReader$15
LANGUAGE_CODE = 'es'
LANGUAGES = [
    ('en', _('English')),
    ('es', _('Spanish')),
]
USE_I18N = True
USE_L10N = True

LOCALE_PATHS = (
    os.path.join(BASE_DIR, 'locale'),
)

SITE_ID = 1

STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static'), chartkick.js()]
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Make this unique, and don't share it with anybody.
SECRET_KEY = '****'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates'), ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'urls'

INSTALLED_APPS = (
    "django.contrib.admin",
    "django.contrib.admindocs",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    # Extra Django apps
    "taggit",
    "admin_honeypot",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "rosetta",
    "widget_tweaks",
    # crm apps enabled
    "core",
    "support",
    "logistics",
    "community",
    "invoicing",
)

# Password storage
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.SHA1PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.BCryptPasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [{
    'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    'OPTIONS': {'min_length': 8}}, {'NAME': 'validators.NumberValidator'},
    {'NAME': 'validators.UppercaseValidator'},
    {'NAME': 'validators.LowercaseValidator'}]

####################################################################

CSS_URL = STATIC_URL + 'css/'
IMG_URL = STATIC_URL + 'img/'

LOGO = 'static/img/logo-utopia.png'  # Image logo under static directory

# Background tasks settings
MAX_ATTEMPTS = 1
MAX_RUN_TIME = 10800

TABBED_ADMIN_USE_JQUERY_UI = True

GRAPH_MODELS = {
    'all_applications': True,
    'group_models': True,
}

# Import local settings if they exist
# TODO: improve hardcoded load of community settings
try:
    from local_settings import *  # noqa
except ImportError:
    pass
