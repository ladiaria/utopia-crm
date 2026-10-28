from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _

from invoicing.exchange_rates import ExchangeRateNotAvailable, get_exchange_rate, get_exchange_rate_source
from invoicing.models import ExchangeRate


class Command(BaseCommand):
    help = (
        "Loads the daily exchange rates of EXCHANGE_RATE_CURRENCIES from EXCHANGE_RATE_SOURCE, which each "
        "installation provides. It fetches the last --days days, so a day the source failed is caught up the next "
        "one. Rows that already exist are never overwritten: if one differs from the source (for instance, it was "
        "loaded by hand), it is reported. It also reports when the rate for today is not available, so it should run "
        "before billing. With --verbosity 0 it only prints anomalies, and it exits with an error if there is any, so "
        "a cron only mails when something needs attention."
    )

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=10, help="How many days back to fetch (default 10).")
        parser.add_argument(
            "--currency", action="append", help="Fetch this currency instead of EXCHANGE_RATE_CURRENCIES. Repeatable."
        )

    def handle(self, *args, **options):
        currencies = options["currency"] or getattr(settings, "EXCHANGE_RATE_CURRENCIES", [])
        if not currencies:
            if options["verbosity"] >= 1:
                self.stdout.write(_("No currencies to update: EXCHANGE_RATE_CURRENCIES is empty."))
            return
        source = get_exchange_rate_source()
        if source is None:
            raise CommandError(
                _("EXCHANGE_RATE_SOURCE is not set: set it to the dotted path of the function that fetches the rates.")
            )
        source_name = getattr(source, "source_name", "auto")
        today = date.today()
        date_from = today - timedelta(days=options["days"])
        anomalies = []

        for currency in currencies:
            try:
                rates = source(currency, date_from, today)
            except Exception as e:
                anomalies.append(_("{currency}: the source failed: {error}").format(currency=currency, error=e))
                rates = []
            for rate_date, rate in rates:
                existing = ExchangeRate.objects.filter(currency=currency, date=rate_date).first()
                if existing is None:
                    ExchangeRate.objects.create(currency=currency, date=rate_date, rate=rate, source=source_name)
                    if options["verbosity"] >= 1:
                        self.stdout.write(
                            _("{currency} {date}: {rate} loaded").format(currency=currency, date=rate_date, rate=rate)
                        )
                elif existing.rate != rate:
                    anomalies.append(
                        _(
                            "{currency} {date}: the stored rate {stored} ({stored_source}) differs from the source's "
                            "{rate}. It was not overwritten: fix it from the admin."
                        ).format(
                            currency=currency,
                            date=rate_date,
                            stored=existing.rate,
                            stored_source=existing.source,
                            rate=rate,
                        )
                    )
            try:
                get_exchange_rate(currency, today)
            except ExchangeRateNotAvailable as e:
                anomalies.append(str(e))

        if anomalies:
            for anomaly in anomalies:
                self.stderr.write(anomaly)
            raise CommandError(_("{count} anomalies while updating exchange rates").format(count=len(anomalies)))
