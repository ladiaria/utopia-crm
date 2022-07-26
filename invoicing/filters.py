from datetime import date, timedelta

import django_filters
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.db.models import Q

from .models import Invoice

YESNO_CHOICES = (
    ("yes", _("Yes")),
    ("no", _("No")),
)

CREATION_CHOICES = (
    ('today', _('Today')),
    ('yesterday', _('Yesterday')),
    ('last_7_days', _('Last 7 days')),
    ('last_30_days', _('Last 30 days')),
    ('this_month', _('This month')),
    ('last_month', _('Last month')),
    ('custom', _('Custom'))
)


STATUS_CHOICES = (
    ('paid', _("Paid")),
    ('debited', _("Debited")),
    ('paid_or_debited', _("Paid or debited")),
    ('pending', _('Pending')),
    ('canceled', _('Canceled')),
    ('uncollectible', _('Uncollectible')),
    ('overdue', _('Overdue')),
    ('not_paid', _('Not paid'))
)


class InvoiceFilter(django_filters.FilterSet):
    contact_name = django_filters.CharFilter(method='filter_by_contact_name')
    creation_date = django_filters.ChoiceFilter(choices=CREATION_CHOICES, method='filter_by_creation_date')
    creation_gte = django_filters.DateFilter(
        field_name='creation_date', lookup_expr='gte', widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    creation_lte = django_filters.DateFilter(
        field_name='creation_date', lookup_expr='lte', widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    status = django_filters.ChoiceFilter(choices=STATUS_CHOICES, method='filter_by_status')
    payment_gte = django_filters.DateFilter(
        field_name='payment_date', lookup_expr='gte', widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    payment_lte = django_filters.DateFilter(
        field_name='payment_date', lookup_expr='lte', widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    no_serial = django_filters.ChoiceFilter(choices=YESNO_CHOICES, method='filter_by_no_serial')

    class Meta:
        model = Invoice
        fields = ['contact_name', 'payment_type', 'serie', 'numero']

    def filter_by_contact_name(self, queryset, name, value):
        return queryset.filter(contact__name__icontains=value)

    def filter_by_creation_date(self, queryset, name, value):
        if value == 'today':
            return queryset.filter(creation_date=date.today())
        elif value == 'yesterday':
            return queryset.filter(creation_date=date.today() - timedelta(1))
        elif value == 'last_7_days':
            return queryset.filter(
                creation_date__gte=date.today() - timedelta(7), creation_date__lte=date.today())
        elif value == 'last_30_days':
            return queryset.filter(
                creation_date__gte=date.today() - timedelta(30), creation_date__lte=date.today())
        elif value == 'this_month':
            return queryset.filter(
                creation_date__month=date.today().month, creation_date__year=date.today().year)
        elif value == 'last_month':
            month = date.today().month - 1 if date.today().month != 1 else 12
            year = date.today().year if date.today().month != 1 else date.today().year - 1
            return queryset.filter(creation_date__month=month, creation_date__year=year)
        else:
            return queryset

    def filter_by_status(self, queryset, name, value):
        if value == 'paid':
            return queryset.filter(paid=True)
        elif value == 'debited':
            return queryset.filter(debited=True)
        elif value == 'paid_or_debited':
            return queryset.filter(Q(paid=True) | Q(debited=True))
        elif value == 'canceled':
            return queryset.filter(canceled=True)
        elif value == 'uncollectible':
            return queryset.filter(uncollectible=True)
        elif value == 'overdue':
            return queryset.filter(
                paid=False, debited=False, canceled=False, uncollectible=False, expiration_date__lte=date.today())
        elif value == 'not_paid':
            return queryset.filter(
                paid=False, debited=False, canceled=False, uncollectible=False,
            )
        else:
            return queryset.filter(
                paid=False, debited=False, uncollectible=False, canceled=False, expiration_date__gt=date.today())
    
    def filter_by_no_serial(self, queryset, name, value):
        if value == 'yes':
            return queryset.filter(
                numero__isnull=True
            )
        elif value == 'no':
            return queryset.filter(
                numero__isnull=False
            )
        else:
            return queryset
