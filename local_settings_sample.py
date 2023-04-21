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
        "corsheaders",
        "rest_framework",
        "rest_framework.authtoken",
        "django_filters",
        "widget_tweaks",
        # crm apps enabled
        "core",
        "support",
        "logistics",
        "community",
        "invoicing",
    )

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
DEFAULT_STATE = "Montevideo"
DEFAULT_CITY = "Montevideo"

# Message that will appear on an invoice if the user is a debtor. The use of unicode is encouraged.
# This is just a placeholder text.
IS_DEBTOR_INVOICE_MESSAGE = "Call 867-5309 for more info"

# Percentage of discount for when the frequency is more than 1
DISCOUNT_3_MONTHS = 4.76
DISCOUNT_6_MONTHS = 7.3
DISCOUNT_12_MONTHS = 11.91

# Price of an envelope
ENVELOPE_PRICE = 4

# Payment methods for invoicing
INVOICE_PAYMENT_METHODS = (("M", "Mastercard"), ("V", "Visa"), ("C", "Cash"))

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

# Set this with a list with one or more routes if you want to ignore the billing of a subscription which main route is
# included in the list.
EXCLUDE_ROUTES_FROM_BILLING_LIST = [50, 51]

# Set this with a list of routes if you want your sellers to have a list of contacts with products having these
# particular routes. We usually use the same ones than we use at EXCLUDE_ROUTES_FROM_BILLING_LIST.
SPECIAL_ROUTES_FOR_SELLERS_LIST = [50, 51]

# Use these to set your own answers to issues. Each answer must be a tuple with two characters on the first element,
# and a string on the second element.
ISSUE_ANSWERS = (
    ('I1', 'Collected'),
    ('L1', 'Delivered again'),
)

# Set a list of statsues slugs that will be used to allow an issue to be closed
ISSUE_STATUS_AUTO_CLOSE_SLUGS = [
    'new',
    'uncollectible',
]

# Set a list of subcategories slugs that will be used to allow an issue to be closed
ISSUE_SUBCATEGORY_AUTO_CLOSE_SLUGS = [
    'inactive',
    '1-invoice-debt',
]

# Used when a new issue is created, depending if it was assigned or not. You must create the issue statuses beforehand
ISSUE_STATUS_ASSIGNED = 'assigned'
ISSUE_STATUS_UNASSIGNED = 'unassigned'
ISSUE_STATUS_PENDING = 'pending'
ISSUE_STATUS_NEW = 'new'

# When using subcategories for debt, we use certain subcategories depending on how many overdue invoices the person has.
ISSUE_SUBCATEGORY_1_INVOICE = 'debt-1-invoice'
ISSUE_SUBCATEGORY_2_INVOICES = 'debt-2-invoices'
ISSUE_SUBCATEGORY_GENERIC_DEBT = 'generic-debt'

# Temporary discount: slug: months. Use this dictionary if you want certain products to disappear from the subscription
# after a set amount of months.
TEMPORARY_DISCOUNT = {
    'product-slug': 3,
}
