# coding=utf-8
DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": "utopiadev",
        "USER": "utopiadev_django",
        "PASSWORD": "utopiadev_django",
    }
}

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
        # Debug tools. Use if necessary
        "django_extensions",
        "debug_toolbar",
        # Extra Django apps
        "taggit",
        "admin_honeypot",
        "corsheaders",
        "rest_framework",
        "rest_framework.authtoken",
        "django_filters",
        "rosetta",
        "widget_tweaks",
        "tabbed_admin",
        # crm apps enabled
        "core",
        "support",
        "logistics",
        "community",
        "invoicing",
    )
else:
    # Use your own installed apps here if you need different settings
    pass

# Replace with your own allowed hosts.
ALLOWED_HOSTS = ["localhost"]

# Use this setting to only import certain contacts, activate with True and
# type the id numbers (int) in the MIGRATION_CUSTOM_CONTACT_LIST.
MIGRATION_USE_CUSTOM_CONTACT_LIST = False
MIGRATION_CUSTOM_CONTACT_LIST = []

# Use this setting if you want to skip importing the GeoRefAddresses
MIGRATION_SKIP_GEOREF_ADDRESSES = False

# Use this setting if you want to skip importing the Deliveries
MIGRATION_SKIP_DELIVERIES = False

# Default state and city used on the Address model. If it is not set, it will be None by default. Use your own cities.
DEFAULT_STATE = u"Montevideo"
DEFAULT_CITY = u"Montevideo"

# Message that will appear on an invoice if the user is a debtor. The use of unicode is encouraged.
# This is just a placeholder text.
IS_DEBTOR_INVOICE_MESSAGE = u"Call 867-5309 for more info"

# Use this to pre define your states on the Address model. If you don't want to use a choice for the states,
# set USE_STATES_CHOICE on False
USE_STATES_CHOICE = True
STATES = (("State 1", "State 1"), ("State 2", "State 2"))

# Add your payment methods for subscriptions here. This is required for the program to work.
SUBSCRIPTION_PAYMENT_METHODS = (
    ("O", "Other"),
    ("D", "Debit card"),
    ("S", "Cash payment"),
)

# Here you can add a series of reasons to categorize why a contact was unsubscribed. The index must be a positive
# number
UNSUBSCRIPTION_REASONS = (
    (1, "Economical reasons"),
    (2, "Did not like the product"),
    (3, "Problem with payment type"),
    (4, "Did not receive the product"),
)

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

# Use this if you have a custom app that you want to load the URLs from
# URLS_CUSTOM_MODULE = 'your.module.urls'

# Set this to true if you want to require route for billing. Useful for when you explicitly require to send the invoice
# via logistics.
REQUIRE_ROUTE_FOR_BILLING = False

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

# Temporary discount: slug: months. Use this dictionary if you want certain products to disappear from the subscription
# after a set amount of months.
TEMPORARY_DISCOUNT = {
    'product-slug': 3,
}

# How many days into the future are we going to bill contacts
BILLING_EXTRA_DAYS = 2
