# coding=utf-8
from datetime import date, timedelta

import django_filters
from django import forms
from django.utils.translation import gettext_lazy as _

from core.models import SubscriptionProduct, Product

EMPTY_ORDER_CHOICES = (
    ("only_ordered", _("Only ordered")),
    ("only_empty", _("Only empty")),
)

PRODUCT_WEEKDAY_CHOICES = (
    ("weekdays", _("Weekdays")),
    ("weekend", _("Weekend")),
    ("no_day", _("No day")),
)

ACTIVE_FUTURE_CHOICES = (
    ("active", _("Active")),
    ("future", _("Future")),
    ("both", _("Both")),
)


class OrderRouteFilter(django_filters.FilterSet):
    class Meta:
        model = SubscriptionProduct
        fields = ['product']

    product = django_filters.ModelChoiceFilter(
        queryset=Product.objects.filter(type='S', offerable=True, digital=False)
    )
    weekday = django_filters.ChoiceFilter(choices=PRODUCT_WEEKDAY_CHOICES, method="filter_by_product_weekday")
    empty_order = django_filters.ChoiceFilter(
        choices=EMPTY_ORDER_CHOICES, method="filter_by_empty_order"
    )
    active_future = django_filters.ChoiceFilter(choices=ACTIVE_FUTURE_CHOICES, method="filter_by_active")


    def filter_by_empty_order(self, queryset, name, value):
        if value == 'only_ordered':
            return queryset.filter(order__isnull=False)
        elif value == 'only_empty':
            return queryset.filter(order__isnull=True)
        else:
            return queryset

    def filter_by_product_weekday(self, queryset, name, value):
        if value == "weekdays":
            return queryset.filter(product__weekday__in=[1, 2, 3, 4, 5, 9])
        elif value == "weekend":
            return queryset.filter(product__weekday__in=[6, 7, 10])
        elif value == "no_day":
            return queryset.filter(product__isnull=True)
        else:
            return queryset

    def filter_by_active(self, queryset, name, value):
        active_qs = queryset.filter(subscription__active=True)
        future_qs = queryset.filter(subscription__active=False, subscription__start_date__gte=date.today())
        if value == "active":
            return active_qs
        elif value == "future":
            return future_qs
        elif value == "both":
            return active_qs | future_qs
        else:
            return queryset
