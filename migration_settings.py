# coding=utf-8
import os


DEBUG = True

# Use your own email settings
SERVER_EMAIL = 'email@example.com'
ADMINS = (
    ('Utopia Admins', SERVER_EMAIL),
)
MANAGERS = ADMINS
# SMTP email host
EMAIL_HOST = 'smtp.example.com'

if DEBUG:
    # CorsMiddleware used in debug mode
    MIDDLEWARE = [
        "django.middleware.security.SecurityMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "corsheaders.middleware.CorsMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
        "debug_toolbar.middleware.DebugToolbarMiddleware",
        "simple_history.middleware.HistoryRequestMiddleware",
    ]
else:
    MIDDLEWARE = [
        "django.middleware.security.SecurityMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
        "debug_toolbar.middleware.DebugToolbarMiddleware",
        "simple_history.middleware.HistoryRequestMiddleware",
    ]

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

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Replace with your own allowed hosts.
ALLOWED_HOSTS = ["localhost"]

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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

WEB_UPDATE_USER_ENABLED = False

# Use this setting to only import certain contacts, activate with True and
# type the id numbers (int) in the MIGRATION_CUSTOM_CONTACT_LIST.
MIGRATION_USE_CUSTOM_CONTACT_LIST = False
MIGRATION_CUSTOM_CONTACT_LIST = []

# Use this setting if you want to skip importing the GeoRefAddresses
MIGRATION_SKIP_GEOREF_ADDRESSES = False

# Use this setting if you want to skip importing the Deliveries
MIGRATION_SKIP_DELIVERIES = False

# Message that will appear on an invoice if the user is a debtor. The use of unicode is encouraged.
# This is just a placeholder text.
IS_DEBTOR_INVOICE_MESSAGE = "Call 867-5309 for more info"

# Use this to pre define your states on the Address model. If you don't want to use a choice for the states,
# set USE_STATES_CHOICE on False
USE_STATES_CHOICE = False
STATES = ()

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

SUBSCRIPTION_PAYMENT_METHODS = ()

OLD_UNSUBSCRIPTION_REASONS = ()

# Percentage of discount for when the frequency is more than 1
DISCOUNT_3_MONTHS = 4.76
DISCOUNT_6_MONTHS = 7.3
DISCOUNT_12_MONTHS = 11.91

# Price of an envelope
ENVELOPE_PRICE = 4

# Payment methods for invoicing
INVOICE_PAYMENT_METHODS = (("M", "Mastercard"), ("V", "Visa"), ("C", "Cash"))

INVOICES_PATH = "path/to/folder/in/media/"

# Set the payment types that you want to track on labels here. They must be set by type on a string.
LABEL_INVOICE_PAYMENT_TYPES = "RI"

# Set this to true to show only one item per subscription in subscription invoices, instead of one item per
# invoiceitem.
USE_SQUASHED_SUBSCRIPTION_INVOICEITEMS = True

# Use your own logo for the admin and dashboard
LOGO = "static/img/logo-utopia.png"
# Use your own logo for the invoices. It can be a route or just the regular logo.
INVOICE_LOGO = LOGO

MAILTRAIN_URL = "https://mailtrain.example.com/"
MAILTRAIN_API_URL = MAILTRAIN_URL + "api/"
MAILTRAIN_API_KEY = "your_secret_key"

# Set this to true if you want to require route for billing. Useful for when you explicitly require to send the invoice
# via logistics.
REQUIRE_ROUTE_FOR_BILLING = False
SECRET_KEY = 'dev'

# Use these to set your own answers to issues. Each answer must be a tuple with two characters on the first element,
# and a string on the second element.
ISSUE_ANSWERS = (
    ('I1', 'Collected'),
    ('L1', 'Delivered again'),
)

# Used to generate new issues on the generate_invoicing_issues management command. Use a slug for your preferred status
NEW_INVOICING_ISSUE_STATUS_SLUG = 'new'

# Set a list of statuses slugs that will be used to mark the issue as finished. Examples below.
SOLVED_ISSUE_STATUS_SLUG = 'solved'
FINISHED_ISSUE_STATUS_SLUG_LIST = ['solved', 'not-solved']

# Used when a new issue is created, depending if it was assigned or not
ASSIGNED_ISSUE_STATUS_SLUG = 'assigned'
UNASSIGNED_ISSUE_STATUS_SLUG = 'unassigned'
PENDING_ISSUE_STATUS_SLUG = 'pending'
AUTO_ISSUE_STATUS_SLUG = 'automatic'  # for automatic tasks that have not been completed yet

CARDS = ()

try:
    from local_migration_settings import *
except ImportError:
    pass
