from datetime import date, timedelta

import django_filters
from django.utils.translation import ugettext_lazy as _
from django.db.models import Q

from .models import Invoice


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
    ('overdue', _('Overdue'))
)


class InvoiceFilter(django_filters.FilterSet):
    contact_name = django_filters.CharFilter(method='filter_by_contact_name')
    creation_date = django_filters.ChoiceFilter(choices=CREATION_CHOICES, method='filter_by_creation_date')
    creation_gte = django_filters.DateFilter(field_name='creation_date', lookup_expr='gte')
    creation_lte = django_filters.DateFilter(field_name='creation_date', lookup_expr='lte')
    status = django_filters.ChoiceFilter(choices=STATUS_CHOICES, method='filter_by_status')

    class Meta:
        model = Invoice
        fields = ['contact_name']

    def __init__(self, *args, **kwargs):
        super(InvoiceFilter, self).__init__(*args, **kwargs)
        self.form.initial['creation_date'] = 'today'

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
        else:
            return queryset.filter(
                paid=False, debited=False, uncollectible=False, canceled=False, expiration_date__gt=date.today())
