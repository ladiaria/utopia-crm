from django.conf import settings
from django.db.models import Count, Sum


def get_default_currency():
    """
    The ISO 4217 code of the local currency (DEFAULT_CURRENCY). Default of the currency fields of subscriptions and
    invoices: a callable, so migrations do not freeze the value of whatever settings generated them.
    """
    return getattr(settings, "DEFAULT_CURRENCY", "UYU")


def is_default_currency(currency):
    return currency == get_default_currency()


def split_by_currency(queryset, amount_field="amount", currency_field="currency"):
    """
    Splits a queryset of rows with an amount into the ones in the local currency, which are the only ones money totals
    add up, and a summary of the rest: [{"currency", "count", "total"}], one per currency, never added to the local
    ones (it/utopia-crm-ladiaria#123).
    """
    default = get_default_currency()
    # Summed over the rows themselves, by pk: the queryset may come with joins (and distinct) that would add a row up
    # once per joined row
    others = (
        queryset.model._default_manager.filter(pk__in=queryset.exclude(**{currency_field: default}).values("pk"))
        .order_by()
        .values(currency_field)
        .annotate(count=Count("pk"), total=Sum(amount_field))
        .order_by(currency_field)
    )
    return queryset.filter(**{currency_field: default}), [
        {"currency": row[currency_field], "count": row["count"], "total": row["total"]} for row in others
    ]
