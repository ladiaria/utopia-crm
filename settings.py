# Django settings for utopia-crm project
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

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
        'LOCATION': '127.0.0.1:11211',
    },
}

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
    "middleware.hideapp_middleware.HideAppMiddleware",
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
    'django_select2',
    "phonenumber_field",
    # crm apps enabled
    "core",
    "support",
    "logistics",
    "community",
    "invoicing",
    "advertisement",
]

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

# logo for the admin site and dashboard pages
LOGO = "static/img/logo-utopia.png"
# logo for the invoices.
INVOICE_LOGO = LOGO

TABBED_ADMIN_USE_JQUERY_UI = True

GRAPH_MODELS = {
    "all_applications": True,
    "group_models": True,
}

# Background tasks
MAX_ATTEMPTS = 1
MAX_RUN_TIME = 10800

# django-select2
SELECT2_CACHE_BACKEND = "default"  # it can use any other cache backend supported by Django like redis

# default NLs map, format:
# key=function to eval receiving contact as arg, value: default NLs product slugs to add if key function returns True
# use special key True to add default NLs in the entry for all contacts, example: {True: ["default"]}
CORE_DEFAULT_NEWSLETTERS = {}

# Predefined states in Address model. If you don't want to use a choice for the states, override this to False
USE_STATES_CHOICE = True
# The values to use if the previous setting is True
STATES = (("State 1", "State 1"), ("State 2", "State 2"))

# Reasons to categorize why a contact was unsubscribed. The index must be a positive number
UNSUBSCRIPTION_REASON_CHOICES = (
    (1, "Does not like content"),
    (2, "Economical reasons"),
    (3, "Other"),
)

# Same as the previous, but for where you received the unsubscription request
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

# list of statuses slugs that will be used to mark the issue as finished
ISSUE_STATUS_SOLVED = "solved"
ISSUE_STATUS_FINISHED_LIST = [ISSUE_STATUS_SOLVED, "not-solved"]

# logistics
LOGISTICS_LABEL_INVOICE_PAYMENT_TYPES = []

# Override to True if route for billing is required
# Useful when you explicitly require to send the invoices via logistics
REQUIRE_ROUTE_FOR_BILLING = False

# Route numbers to ignore the billing of subscriptions which main route is included in this list
EXCLUDE_ROUTES_FROM_BILLING_LIST = []

# Route numbers to allow sellers to have contacts with products having these particular routes
# We usually use the same ones than we use at EXCLUDE_ROUTES_FROM_BILLING_LIST
SPECIAL_ROUTES_FOR_SELLERS_LIST = []

# utopia-cms integration (override this in your local_settings.py). TODO: s/(WEB_|LDSOCIAL_)/UTOPIACMS_/
WEB_UPDATE_USER_ENABLED = False  # TODO: write analogous systemcheck made in CMS when this is True and "no url"
LDSOCIAL_URL = ""  # The SITE_URL setting of the "associated" utopia-cms deplyment (CMS)
LDSOCIAL_API_KEY = ""  # A key generated in the CMS using "rest_framework_api_key" app
WEB_UPDATE_HTTP_BASIC_AUTH = None  # Override to tuple (user, pass) if the CMS is restricted using basic auth
ENV_HTTP_BASIC_AUTH = False  # Override to True if this CRM deployment is restricted using basic auth
# Subscriptions to publication and area newsletters sync (to find usage, do not grep literally, use "_MEWSLETTER_MAP")
WEB_UPDATE_NEWSLETTER_MAP = {
    # Override to sync CMS Publication newsletters subscriptions, format: key: CMS Publication.id, value: product.slug
}
WEB_UPDATE_AREA_NEWSLETTER_MAP = {
    # Override to sync CMS Area newsletters subscriptions, format: key: CMS Category.id, value: product.slug
}
# If True, allows queuing subscriptions to start after the active one ends. This is useful for
# example to queue a subscription to start after the current one ends, in the case the customer
# wants to pay for a new subscription before the current one ends.
ALLOW_QUEUE_SUBSCRIPTIONS = False

# MercadoPago integration (override this to True in your local_settings.py to enable)
MERCADOPAGO_ENABLED = False

# phonenumbers default region
PHONENUMBER_DEFAULT_REGION = "UY"

# Variables which their default value will be assigned after local_settings import, if not overrided there
WEB_UPDATE_USER_URI = None
WEB_DELETE_USER_URI = None
WEB_EMAIL_CHECK_URI = None
WEB_CREATE_USER_ENABLED = None
WEB_CREATE_USER_POST_WHITELIST = []

GEOREF_SERVICES = False

# Import local settings if they exist
# TODO: - improve hardcoded load of community settings (which are this community settings?)
#         (maybe is the app "community", which defines variables that can be better migrated to this settings file)
#       - investigate usage of django-environ to manage settings more easily
try:
    from local_settings import *  # noqa
except ImportError:
    pass

if locals().get("DEBUG_TOOLBAR_ENABLE"):
    # NOTE when enabled, you need to: pip install django-debug-toolbar && ./manage.py collectstatic
    INTERNAL_IPS = ('127.0.0.1', )  # '0.0.0.0' or '*' also can be used here
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')

# utopia-cms interoperability default urls. TODO: s/(WEB_|LDSOCIAL_)/UTOPIACMS_/
if LDSOCIAL_URL:
    WEB_UPDATE_USER_URI = WEB_UPDATE_USER_URI or (LDSOCIAL_URL + 'usuarios/fromcrm')
    WEB_DELETE_USER_URI = WEB_DELETE_USER_URI or (LDSOCIAL_URL + 'usuarios/deletefromcrm')
    WEB_EMAIL_CHECK_URI = WEB_EMAIL_CHECK_URI or (LDSOCIAL_URL + 'usuarios/api/email_check/')
    LDSOCIAL_API_URI = f"{LDSOCIAL_URL}api/"

if WEB_CREATE_USER_ENABLED is None:
    WEB_CREATE_USER_ENABLED = WEB_UPDATE_USER_ENABLED

if not WEB_CREATE_USER_ENABLED and WEB_EMAIL_CHECK_URI not in WEB_CREATE_USER_POST_WHITELIST:
    WEB_CREATE_USER_POST_WHITELIST.append(WEB_EMAIL_CHECK_URI)

if ENV_HTTP_BASIC_AUTH and not locals().get("API_KEY_CUSTOM_HEADER"):
    # by default, this variable is not defined, thats why we use locals() instead of set a "neutral" value
    API_KEY_CUSTOM_HEADER = "HTTP_X_API_KEY"
