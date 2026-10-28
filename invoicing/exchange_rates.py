"""
Exchange rates: which rate applies to a date, and where the daily rates come from.

The rate that applies to a date is the last one published *before* that date, that is, the one of the previous
business day. Sources only publish on business days, so the previous row already skips weekends and holidays and
no calendar is needed.

Settings:

- EXCHANGE_RATE_CURRENCIES: ISO 4217 codes that update_exchange_rates fetches every day (default: none).
- EXCHANGE_RATE_SOURCE: dotted path to a callable ``(currency, date_from, date_to)`` that returns ``(date, rate)``
  pairs, one per published day in the range (default: the Central Bank of Uruguay, ``fetch_bcu``). It may set a
  ``source_name`` attribute, stored on each row it loads.
- EXCHANGE_RATE_MAX_AGE_DAYS: how many calendar days old the previous rate can be before get_exchange_rate refuses
  it (default 6). Uruguayan bank holidays leave gaps of up to 5 days (Carnival, Tourism Week), so 6 only fails when
  the daily load stopped working.
"""

from datetime import date as date_type
from decimal import Decimal
from xml.etree import ElementTree

import requests

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
    return import_string(getattr(settings, "EXCHANGE_RATE_SOURCE", "invoicing.exchange_rates.fetch_bcu"))


# Central Bank of Uruguay (BCU) web service. It is public and needs no key.
BCU_URL = "https://cotizaciones.bcu.gub.uy/wscotizaciones/servlet/awsbcucotizaciones"
BCU_NAMESPACE = "Cotiza"
# BCU currency codes, by ISO 4217 code. 2225 is "DLS. USA BILLETE", the interbank US dollar.
BCU_CURRENCY_CODES = {"USD": 2225}
# The error code the BCU answers when the range has no published day (a weekend, a holiday, today before it closes).
BCU_NO_RATE_ERROR_CODE = "100"
BCU_REQUEST = """<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:cot="Cotiza">
<soapenv:Header/>
<soapenv:Body>
<cot:wsbcucotizaciones.Execute>
<cot:Entrada>
<cot:Moneda><cot:item>{code}</cot:item></cot:Moneda>
<cot:FechaDesde>{date_from}</cot:FechaDesde>
<cot:FechaHasta>{date_to}</cot:FechaHasta>
<cot:Grupo>0</cot:Grupo>
</cot:Entrada>
</cot:wsbcucotizaciones.Execute>
</soapenv:Body>
</soapenv:Envelope>"""


def fetch_bcu(currency, date_from, date_to):
    """
    Returns the (date, rate) pairs the BCU published between date_from and date_to, both included. The rate is the
    buying one (TCC); for the interbank dollar the BCU publishes the same value for buying and selling.
    """
    code = BCU_CURRENCY_CODES.get(currency)
    if code is None:
        raise ValueError(_("The BCU source does not know the currency {currency}").format(currency=currency))
    response = requests.post(
        BCU_URL,
        data=BCU_REQUEST.format(code=code, date_from=date_from.isoformat(), date_to=date_to.isoformat()),
        headers={"Content-Type": "text/xml; charset=utf-8"},
        timeout=30,
    )
    response.raise_for_status()
    return parse_bcu_response(response.content, code)


fetch_bcu.source_name = "bcu"


def parse_bcu_response(content, code):
    ns = {"c": BCU_NAMESPACE}
    root = ElementTree.fromstring(content)
    status = root.find(".//c:respuestastatus", ns)
    if status is None:
        raise ValueError(_("Unexpected answer from the BCU"))
    if status.findtext("c:status", namespaces=ns) != "1":
        error_code = status.findtext("c:codigoerror", namespaces=ns)
        if error_code == BCU_NO_RATE_ERROR_CODE:
            return []
        raise ValueError(
            _("The BCU answered error {code}: {message}").format(
                code=error_code, message=status.findtext("c:mensaje", namespaces=ns)
            )
        )
    rates = []
    for item in root.iterfind(".//c:datoscotizaciones.dato", ns):
        if item.findtext("c:Moneda", namespaces=ns) != str(code):
            continue
        rate_date = date_type.fromisoformat(item.findtext("c:Fecha", namespaces=ns))
        rates.append((rate_date, Decimal(item.findtext("c:TCC", namespaces=ns))))
    return rates
