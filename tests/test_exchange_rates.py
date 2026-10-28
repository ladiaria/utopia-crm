from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from invoicing.exchange_rates import ExchangeRateNotAvailable, get_exchange_rate, parse_bcu_response
from invoicing.models import ExchangeRate


# A real answer of the BCU for 2026-10-23 to 2026-10-26 (a Friday and a Monday: the weekend is not published),
# trimmed of its indentation.
BCU_ANSWER = b"""<?xml version="1.0" encoding="utf-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"><SOAP-ENV:Body>
<wsbcucotizaciones.ExecuteResponse xmlns="Cotiza"><Salida xmlns="Cotiza">
<respuestastatus><status>1</status><codigoerror>0</codigoerror><mensaje/></respuestastatus>
<datoscotizaciones>
<datoscotizaciones.dato xmlns="Cotiza"><Fecha>2026-10-23</Fecha><Moneda>2225</Moneda><Nombre>DLS. USA BILLETE</Nombre>
<CodigoISO>DLS.</CodigoISO><Emisor>ESTADOS UNIDOS</Emisor><TCC>40.078000</TCC><TCV>40.078000</TCV>
<ArbAct>1.000000</ArbAct><FormaArbitrar>0</FormaArbitrar></datoscotizaciones.dato>
<datoscotizaciones.dato xmlns="Cotiza"><Fecha>2026-10-26</Fecha><Moneda>2225</Moneda><Nombre>DLS. USA BILLETE</Nombre>
<CodigoISO>DLS.</CodigoISO><Emisor>ESTADOS UNIDOS</Emisor><TCC>40.214000</TCC><TCV>40.214000</TCV>
<ArbAct>1.000000</ArbAct><FormaArbitrar>0</FormaArbitrar></datoscotizaciones.dato>
</datoscotizaciones></Salida></wsbcucotizaciones.ExecuteResponse></SOAP-ENV:Body></SOAP-ENV:Envelope>"""

# What the BCU answers for a range with no published day, and for a malformed request.
BCU_ERROR = b"""<?xml version="1.0" encoding="utf-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"><SOAP-ENV:Body>
<wsbcucotizaciones.ExecuteResponse xmlns="Cotiza"><Salida xmlns="Cotiza">
<respuestastatus><status>0</status><codigoerror>%s</codigoerror><mensaje>%s</mensaje></respuestastatus>
<datoscotizaciones><datoscotizaciones.dato xmlns="Cotiza"><Moneda>0</Moneda><TCC>0.000000</TCC></datoscotizaciones.dato>
</datoscotizaciones></Salida></wsbcucotizaciones.ExecuteResponse></SOAP-ENV:Body></SOAP-ENV:Envelope>"""


class GetExchangeRateTest(TestCase):
    """
    The rate that applies to a date is the last one before it. The rows are built by hand: there is no exchange rate
    fixture, and each test needs its own gaps (weekends, holidays, a stopped load).
    """

    @classmethod
    def setUpTestData(cls):
        # Thursday 2026-10-22, Friday 2026-10-23 and Monday 2026-10-26.
        for day, rate in ((22, "40.083"), (23, "40.078"), (26, "40.214")):
            ExchangeRate.objects.create(currency="USD", date=date(2026, 10, day), rate=Decimal(rate))

    def test_uses_the_previous_business_day(self):
        # Tuesday uses Monday's rate, never its own.
        self.assertEqual(get_exchange_rate("USD", date(2026, 10, 27)).rate, Decimal("40.214"))
        self.assertEqual(get_exchange_rate("USD", date(2026, 10, 26)).rate, Decimal("40.078"))

    def test_skips_the_weekend(self):
        # Saturday, Sunday and Monday all use Friday's rate.
        for day in (24, 25, 26):
            self.assertEqual(get_exchange_rate("USD", date(2026, 10, day)).date, date(2026, 10, 23))

    def test_fails_without_a_previous_rate(self):
        with self.assertRaises(ExchangeRateNotAvailable):
            get_exchange_rate("USD", date(2026, 10, 22))
        with self.assertRaises(ExchangeRateNotAvailable):
            get_exchange_rate("EUR", date(2026, 10, 27))

    def test_tolerates_the_longest_holiday_gap(self):
        # Carnival: Monday and Tuesday are bank holidays, so Wednesday uses Friday's rate, 5 days old. One more day
        # of slack is still accepted.
        for days in (5, 6):
            self.assertEqual(
                get_exchange_rate("USD", date(2026, 10, 26) + timedelta(days=days)).date, date(2026, 10, 26)
            )

    def test_fails_when_the_rate_is_too_old(self):
        with self.assertRaises(ExchangeRateNotAvailable):
            get_exchange_rate("USD", date(2026, 10, 26) + timedelta(days=7))

    @override_settings(EXCHANGE_RATE_MAX_AGE_DAYS=2)
    def test_max_age_is_configurable(self):
        with self.assertRaises(ExchangeRateNotAvailable):
            get_exchange_rate("USD", date(2026, 10, 26))


class ParseBcuResponseTest(TestCase):
    def test_parses_the_buying_rate_of_each_day(self):
        self.assertEqual(
            parse_bcu_response(BCU_ANSWER, 2225),
            [(date(2026, 10, 23), Decimal("40.078")), (date(2026, 10, 26), Decimal("40.214"))],
        )

    def test_ignores_other_currencies(self):
        self.assertEqual(parse_bcu_response(BCU_ANSWER, 501), [])

    def test_no_published_day_is_not_an_error(self):
        answer = BCU_ERROR % (b"100", "No existe cotización para la fecha indicada".encode())
        self.assertEqual(parse_bcu_response(answer, 2225), [])

    def test_other_errors_raise(self):
        answer = BCU_ERROR % (b"102", "Campo de fecha inválida".encode())
        with self.assertRaisesRegex(ValueError, "102"):
            parse_bcu_response(answer, 2225)


def fake_source(currency, date_from, date_to):
    """Publishes 40.1 for every weekday of the range."""
    days = (date_from + timedelta(days=n) for n in range((date_to - date_from).days + 1))
    return [(day, Decimal("40.1")) for day in days if day.weekday() < 5]


fake_source.source_name = "fake"


def failing_source(currency, date_from, date_to):
    raise ConnectionError("unreachable")


@override_settings(EXCHANGE_RATE_SOURCE="tests.test_exchange_rates.fake_source", EXCHANGE_RATE_CURRENCIES=["USD"])
class UpdateExchangeRatesTest(TestCase):
    TODAY = date(2026, 10, 28)  # A Wednesday.

    def run_command(self, **options):
        with mock.patch("invoicing.management.commands.update_exchange_rates.date") as mocked_date:
            mocked_date.today.return_value = self.TODAY
            call_command("update_exchange_rates", verbosity=0, stdout=StringIO(), stderr=StringIO(), **options)

    def test_loads_the_published_days(self):
        self.run_command(days=6)
        self.assertEqual(
            list(ExchangeRate.objects.order_by("date").values_list("date", flat=True)),
            [date(2026, 10, day) for day in (22, 23, 26, 27, 28)],
        )
        self.assertEqual(set(ExchangeRate.objects.values_list("source", flat=True)), {"fake"})

    def test_is_idempotent(self):
        self.run_command(days=6)
        self.run_command(days=6)
        self.assertEqual(ExchangeRate.objects.count(), 5)

    def test_does_not_overwrite_a_different_row(self):
        ExchangeRate.objects.create(currency="USD", date=date(2026, 10, 27), rate=Decimal("41"))
        with self.assertRaisesRegex(CommandError, "1 anomalies"):
            self.run_command(days=6)
        manual = ExchangeRate.objects.get(date=date(2026, 10, 27))
        self.assertEqual((manual.rate, manual.source), (Decimal("41"), ExchangeRate.SOURCE_MANUAL))
        # The rest of the days are loaded anyway.
        self.assertEqual(ExchangeRate.objects.count(), 5)

    @override_settings(EXCHANGE_RATE_SOURCE="tests.test_exchange_rates.failing_source")
    def test_reports_a_failing_source_and_a_missing_rate(self):
        # One anomaly for the source, and one because there is no rate to bill today.
        with self.assertRaisesRegex(CommandError, "2 anomalies"):
            self.run_command()
        self.assertFalse(ExchangeRate.objects.exists())

    @override_settings(EXCHANGE_RATE_CURRENCIES=[])
    def test_does_nothing_without_currencies(self):
        self.run_command()
        self.assertFalse(ExchangeRate.objects.exists())
