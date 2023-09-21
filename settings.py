# coding: utf-8
# Django settings for utopia-crm project.
import os
import chartkick

from django.utils.translation import gettext_lazy as _


LOGIN_URL = "/user/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
DEBUG = False
DEBUG_INVOICING = True  # prints debug data for invoicing in uwsgi log

SERVER_EMAIL = "email@example.com"
ADMINS = (("Utopia Admins", SERVER_EMAIL),)
MANAGERS = ADMINS
# SMTP email host
EMAIL_HOST = "smtp.example.com"
# supervision email.
SUPERVISION_EMAIL = "example@example.com"
DEFAULT_EMAIL_FROM = SUPERVISION_EMAIL

ALLOWED_HOSTS = []

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Local time zone for this installation. All choices can be found here:
# http://www.postgresql.org/docs/current/static/datetime-keywords.html#DATETIME-TIMEZONE-SET-TABLE
TIME_ZONE = "America/Montevideo"
DATE_FORMAT = "Y-m-d"

# Language code for this installation. All choices can be found here:
# http://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
# http://blogs.law.harvard.edu/tech/stories/storyReader$15
LANGUAGE_CODE = "es"
LANGUAGES = [
    ("en", _("English")),
    ("es", _("Spanish")),
]
USE_I18N = True

LOCALE_PATHS = (os.path.join(BASE_DIR, "locale"),)

SITE_ID = 1

FIXTURE_DIRS = (os.path.join(BASE_DIR, 'fixtures'), )
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static"), chartkick.js()]
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(BASE_DIR, "templates"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = "urls"

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
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "widget_tweaks",
    "simple_history",
    "django_htmx",
    "leaflet",
    "djgeojson",
    'markdownify.apps.MarkdownifyConfig',
    # crm apps enabled
    "core",
    "support",
    "logistics",
    "community",
    "invoicing",
)


# Password storage and validators
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.SHA1PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.BCryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "validators.NumberValidator"},
    {"NAME": "validators.UppercaseValidator"},
    {"NAME": "validators.LowercaseValidator"},
]

# other settings
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

CSS_URL = STATIC_URL + "css/"
IMG_URL = STATIC_URL + "img/"

LOGO = "static/img/logo-utopia.png"  # Image logo under static directory

# Background tasks settings
MAX_ATTEMPTS = 1
MAX_RUN_TIME = 10800

TABBED_ADMIN_USE_JQUERY_UI = True

GRAPH_MODELS = {
    "all_applications": True,
    "group_models": True,
}

# Use this to pre define your states on the Address model. If you don't want to use a choice for the states,
# set USE_STATES_CHOICE on False
USE_STATES_CHOICE = True
STATES = (("State 1", "State 1"), ("State 2", "State 2"))

# Here you can add a series of reasons to categorize why a contact was unsubscribed. The index must be a positive
# number
UNSUBSCRIPTION_REASON_CHOICES = (
    (1, "Does not like content"),
    (2, "Economical reasons"),
    (3, "Other"),
)

# Same as the previous, but for where you received the unsubscription request.
UNSUBSCRIPTION_CHANNEL_CHOICES = (
    (1, "E-Mail"),
    (2, "Phone"),
)

# Add your payment methods for subscriptions here. This is required for the program to work.
SUBSCRIPTION_PAYMENT_METHODS = (
    ("O", "Other"),
    ("D", "Debit card"),
    ("S", "Cash payment"),
)

# Invoicing.Invoice model storage path relative to "MEDIA"
INVOICES_PATH = "invoices"

# How many days into the future are we going to bill contacts
BILLING_EXTRA_DAYS = 2

# list of statuses slugs that will be used to mark the issue as finished
ISSUE_STATUS_SOLVED = "solved"
ISSUE_STATUS_FINISHED_LIST = [ISSUE_STATUS_SOLVED, "not-solved"]

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Import local settings if they exist
# TODO: improve hardcoded load of community settings (which are this community settings?)
try:
    from local_settings import *
except ImportError:
    pass
