# coding=utf-8
from settings import INSTALLED_APPS, MIDDLEWARE


DEBUG = True
DEBUG_TOOLBAR_ENABLE = False  # requirements to enable: pip install "django-debug-toolbar<3.2" && cstatic

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": "utopiadev",
        "USER": "utopiadev_django",
        "PASSWORD": "utopiadev_django",
    }
}

if DEBUG:
    # CorsMiddleware used in debug mode
    MIDDLEWARE.insert(2, "corsheaders.middleware.CorsMiddleware")

if DEBUG_TOOLBAR_ENABLE:
    INTERNAL_IPS = ('127.0.0.1', )  # '0.0.0.0' or '*' also can be used here
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')

# Make this unique, and don't share it with anybody.
SECRET_KEY = ""

# Example values for many settings, uncomment and change as your needs.
# (the uncommented variables are required, an error can be generated if not defined)

# Default state and city used on the Address model. If it is not set, it will be None by default.
# DEFAULT_STATE = "Montevideo"
# DEFAULT_CITY = "Montevideo"

# Discounts to apply when the subscription frequency is more than 1 (default=0)
# DISCOUNT_3_MONTHS = 4.76
# DISCOUNT_6_MONTHS = 7.3
# DISCOUNT_12_MONTHS = 11.91

# Price of an envelope (default=not set)
# ENVELOPE_PRICE = 4

# Payment methods for invoicing
INVOICE_PAYMENT_METHODS = (("M", "Mastercard"), ("V", "Visa"), ("C", "Cash"))

# Set the payment types that you want to track on labels in this list. (NOTE: this example matches "R" or "I")
# LOGISTICS_LABEL_INVOICE_PAYMENT_TYPES = "RI"

# Show only one item per subscription in subscription invoices, instead of one item per invoiceitem. (default=False)
# USE_SQUASHED_SUBSCRIPTION_INVOICEITEMS = False

# Mailtrain integration, TODO: write documentation
# MAILTRAIN_URL = "https://mailtrain.example.com/"
# MAILTRAIN_API_URL = MAILTRAIN_URL + "api/"
# MAILTRAIN_API_KEY = "your_secret_key"

# Use this if you have a custom app that you want to load the URLs from
# URLS_CUSTOM_MODULE = 'your.module.urls'

# Set a list of statsues slugs that will be used to allow an issue to be closed
# ISSUE_STATUS_AUTO_CLOSE_SLUGS = ['new', 'uncollectible']

# Set a list of subcategories slugs that will be used to allow an issue to be closed
# ISSUE_SUBCATEGORY_AUTO_CLOSE_SLUGS = ['inactive', '1-invoice-debt']

# Used when a new issue is created, depending if it was assigned or not. You must create the issue statuses beforehand
# TODO: verify if they can be commented
ISSUE_STATUS_ASSIGNED = 'assigned'
ISSUE_STATUS_UNASSIGNED = 'unassigned'
ISSUE_STATUS_PENDING = 'pending'
ISSUE_STATUS_NEW = 'new'

# When using subcategories for debt, use this depending on how many overdue invoices the contact has.
# TODO: explain if the categorization is done automatically or not.
# TODO: verify if they can be commented
ISSUE_SUBCATEGORY_1_INVOICE = 'debt-1-invoice'
ISSUE_SUBCATEGORY_2_INVOICES = 'debt-2-invoices'
ISSUE_SUBCATEGORY_GENERIC_DEBT = 'generic-debt'

# Temporary discounts: A dict map of product slug, months.
# Use for products (discounts) that have to disappear from the subscription after a set amount of months.
# TEMPORARY_DISCOUNT = {'product-slug': 3}

# Settings for GDAL and GEOS for MacOS. Only uncomment if necessary, or delete if not needed.
# GDAL_LIBRARY_PATH = "/opt/homebrew/opt/gdal/lib/libgdal.dylib"
# GEOS_LIBRARY_PATH = "/opt/homebrew/opt/geos/lib/libgeos_c.dylib"
