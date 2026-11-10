from django.conf import settings


def get_default_currency():
    """
    The ISO 4217 code of the local currency (DEFAULT_CURRENCY). Default of the currency fields of subscriptions and
    invoices: a callable, so migrations do not freeze the value of whatever settings generated them.
    """
    return getattr(settings, "DEFAULT_CURRENCY", "UYU")


def is_default_currency(currency):
    return currency == get_default_currency()
