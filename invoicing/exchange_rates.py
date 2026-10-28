"""
Exchange rates: which rate applies to a date.

The rate that applies to a date is the last one published *before* that date, that is, the one of the previous
business day. Sources only publish on business days, so the previous row already skips weekends and holidays and
no calendar is needed.

The rates are loaded by update_exchange_rates from a source that each installation provides, since where the official
rate is published depends on the country.

Settings:

- EXCHANGE_RATE_CURRENCIES: ISO 4217 codes that update_exchange_rates fetches every day (default: none).
- EXCHANGE_RATE_SOURCE: dotted path to a callable ``(currency, date_from, date_to)`` that returns ``(date, rate)``
  pairs, one per published day in the range, both ends included. It may set a ``source_name`` attribute, stored on
  each row it loads. There is no default: it is required when EXCHANGE_RATE_CURRENCIES is set.
- EXCHANGE_RATE_MAX_AGE_DAYS: how many calendar days old the previous rate can be before get_exchange_rate refuses
  it (default 6). Long bank holidays leave gaps of several days (in Uruguay, up to 5 at Carnival), so 6 only fails
  when the daily load stopped working.
"""

from django.conf import settings
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _

from invoicing.models import ExchangeRate


DEFAULT_MAX_AGE_DAYS = 6


class ExchangeRateNotAvailable(Exception):
    pass


def get_exchange_rate(currency, for_date):
    """
    Returns the ExchangeRate that applies to for_date: the last one before it. Raises ExchangeRateNotAvailable if
    there is none, or if it is older than EXCHANGE_RATE_MAX_AGE_DAYS: a document issued with a stale rate would be
    wrong, and it is better that it waits until the rate is loaded.
    """
    max_age = getattr(settings, "EXCHANGE_RATE_MAX_AGE_DAYS", DEFAULT_MAX_AGE_DAYS)
    exchange_rate = ExchangeRate.objects.filter(currency=currency, date__lt=for_date).order_by("-date").first()
    if exchange_rate is None:
        raise ExchangeRateNotAvailable(
            _("There is no {currency} exchange rate before {date}").format(currency=currency, date=for_date)
        )
    if (for_date - exchange_rate.date).days > max_age:
        raise ExchangeRateNotAvailable(
            _("The last {currency} exchange rate before {date} is from {rate_date}, more than {days} days old").format(
                currency=currency, date=for_date, rate_date=exchange_rate.date, days=max_age
            )
        )
    return exchange_rate


def get_exchange_rate_source():
    """Returns the callable set in EXCHANGE_RATE_SOURCE, or None if there is none."""
    source_path = getattr(settings, "EXCHANGE_RATE_SOURCE", None)
    return import_string(source_path) if source_path else None
