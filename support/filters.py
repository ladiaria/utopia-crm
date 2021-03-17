from datetime import date, timedelta

import django_filters
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.db.models import Q

from .models import Issue


CREATION_CHOICES = (
    ('today', _('Today')),
    ('yesterday', _('Yesterday')),
    ('last_7_days', _('Last 7 days')),
    ('last_30_days', _('Last 30 days')),
    ('this_month', _('This month')),
    ('last_month', _('Last month')),
    ('custom', _('Custom'))
)


class IssueFilter(django_filters.FilterSet):
    date = django_filters.ChoiceFilter(choices=CREATION_CHOICES, method='filter_by_date')
    date_gte = django_filters.DateFilter(
        field_name='date', lookup_expr='gte', widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    date_lte = django_filters.DateFilter(
        field_name='date', lookup_expr='lte', widget=forms.TextInput(attrs={'autocomplete': 'off'}))

    class Meta:
        model = Issue
        fields = ['category', 'subcategory', 'status', 'assigned_to']

    def filter_by_date(self, queryset, name, value):
        if value == 'today':
            return queryset.filter(date=date.today())
        elif value == 'yesterday':
            return queryset.filter(date=date.today() - timedelta(1))
        elif value == 'last_7_days':
            return queryset.filter(
                date__gte=date.today() - timedelta(7), date__lte=date.today())
        elif value == 'last_30_days':
            return queryset.filter(
                date__gte=date.today() - timedelta(30), date__lte=date.today())
        elif value == 'this_month':
            return queryset.filter(
                date__month=date.today().month, date__year=date.today().year)
        elif value == 'last_month':
            month = date.today().month - 1 if date.today().month != 1 else 12
            year = date.today().year if date.today().month != 1 else date.today().year - 1
            return queryset.filter(date__month=month, date__year=year)
        else:
            return queryset
