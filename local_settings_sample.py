# coding=utf-8
from settings import MIDDLEWARE


DEBUG = True

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

# Mercado Pago settings, this is optional. Enable to use Mercado Pago as a payment platform, but leave it
# disabled to not use it.
MERCADOPAGO_ENABLED = False  # Override to True to enable Mercado Pago
# MERCADOPAGO_ACCESS_TOKEN = ""  # Override to your Mercado Pago access token in local_settings.py
# MERCADOPAGO_API_MAX_ATTEMPTS = 10  # Override to the maximum number of attempts to get a successful payment
# MERCADOPAGO_FORCE_FAIL_PAYMENT = False  # Override to True to make the payment fail

# Recipients for MercadoPago debit errors (already used by mercadopago_debit)
# MERCADOPAGO_ERRORS_RECIPIENTS = ["comercial@example.com"]
# Recipients for MercadoPago new-subscription errors (t1156): full exception + traceback + MP data
# MERCADOPAGO_SUBSCRIPTION_ERRORS_RECIPIENTS = ["soporte@example.com"]

# =============================================================================
# Error reporting: ADMINS + Sentry
# =============================================================================
# ADMINS receive emails on uncaught server errors (Django default behaviour). Each entry is
# a (name, email) tuple. MANAGERS defaults to ADMINS in settings.py.
# ADMINS = [("Nami", "tu-email@example.com")]

# Sentry error tracking. The SDK is initialized here (not in the base settings) so only the
# environments that need it (production) enable it. Only production should report, per t1156.
# SENTRY_ENABLED = True
# SENTRY_DSN = "https://YOUR_KEY@YOUR_SENTRY_INSTANCE.ingest.sentry.io/YOUR_PROJECT_ID"
# SENTRY_ENVIRONMENT = "production"  # only production sends data to Sentry
#
# if locals().get("SENTRY_ENABLED") and locals().get("SENTRY_DSN") and SENTRY_ENVIRONMENT == "production":
#     import sentry_sdk
#     from sentry_sdk.integrations.django import DjangoIntegration
#
#     def before_send(event, hint):
#         """Filter sensitive MercadoPago / auth data before sending to Sentry."""
#         request = event.get("request", {})
#         data = request.get("data")
#         if isinstance(data, dict):
#             sensitive_keys = [
#                 "password", "token", "secret", "api_key", "security_code",
#                 "mp_card_id", "card_number", "credit_card",
#             ]
#             for key in sensitive_keys:
#                 if key in data:
#                     data[key] = "[Filtered]"
#         return event
#
#     sentry_sdk.init(
#         dsn=SENTRY_DSN,
#         integrations=[DjangoIntegration()],
#         before_send=before_send,
#         environment=SENTRY_ENVIRONMENT,
#         traces_sample_rate=0.0,
#         # CRM has no end-user web traffic; keep PII off by default.
#         send_default_pii=False,
#     )
# =============================================================================
