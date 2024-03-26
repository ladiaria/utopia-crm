"""
This module is a "minimal" copy of settings.py but at the end it not imports any local setting, instead of that, it
imports a custom local_migration_settings.py (if any).
It's very useful to make "clean" migrations, without any possible default or choice value configured in
local_settings.py that can differ (very probbable) between developpers.
To make this "clean" migrations, use this as your settings module in the manage.py calls, this way:
>>> ./manage.py makemigrations --settings=migration_settings [app]
"""
import os

from django.utils.translation import gettext_lazy as _


LOGIN_URL = "/user/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# debug for special parts, override to True to print debug data
DEBUG_CONTACT_CLEAN = False
DEBUG_INVOICING = False

ALLOWED_HOSTS = ["localhost"]

# Useful to build absolute paths inside the project, like this: os.path.join(BASE_DIR, ...)
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

LOCALE_PATHS = (os.path.join(BASE_DIR, "locale"),)

SITE_ID = 1

FIXTURE_DIRS = (os.path.join(BASE_DIR, 'fixtures'), )
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]
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

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.admindocs",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    # Extra Django apps
    "django_extensions",
    "taggit",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_api_key",
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
    "advertisement",
]

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

CSS_URL = STATIC_URL + "css/"
IMG_URL = STATIC_URL + "img/"

# logo for the admin site and dashboard pages
LOGO = "static/img/logo-utopia.png"
# logo for the invoices.
INVOICE_LOGO = LOGO

# Background tasks settings
MAX_ATTEMPTS = 1
MAX_RUN_TIME = 10800

# Predefined states in Address model. If you don't want to use a choice for the states, override this to False.
USE_STATES_CHOICE = False

# Reasons to categorize why a contact was unsubscribed. The index must be a positive number
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

# Payment methods for subscriptions.
SUBSCRIPTION_PAYMENT_METHODS = (
    ("O", "Other"),
    ("D", "Debit card"),
    ("S", "Cash payment"),
)

# Invoicing.Invoice model storage path relative to "MEDIA"
INVOICES_PATH = "invoices"
INVOICE_PAYMENT_METHODS = (("M", "Mastercard"), ("V", "Visa"), ("C", "Cash"))

# How many days into the future are we going to bill contacts
BILLING_EXTRA_DAYS = 2

REQUIRE_ROUTE_FOR_BILLING = False

try:
    from local_migration_settings import *
except ImportError:
    pass
