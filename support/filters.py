from datetime import date, timedelta

import django_filters
from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.db.models import Q

from core.models import Activity, ContactCampaignStatus, Subscription, Campaign
from .models import Issue, IssueSubcategory, Seller, ScheduledTask, SalesRecord


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
    assigned_to = django_filters.ModelChoiceFilter(
        queryset=User.objects.filter(is_staff=True).order_by('username'),
        widget=forms.Select(attrs={"class": "form-control"})
    )

    class Meta:
        model = Issue
        fields = ['category', 'sub_category', 'status', 'assigned_to']

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


class InvoicingIssueFilter(IssueFilter):
    sub_category = django_filters.ModelChoiceFilter(
        queryset=IssueSubcategory.objects.filter(category='I'),
        widget=forms.Select(attrs={"class": "form-control"})
    )


class ScheduledActivityFilter(django_filters.FilterSet):
    class Meta:
        model = Activity
        fields = ['status', 'campaign']


class ContactCampaignStatusFilter(django_filters.FilterSet):
    seller = django_filters.ModelChoiceFilter(
        queryset=Seller.objects.filter(internal=True)
    )

    class Meta:
        model = ContactCampaignStatus
        fields = ["seller"]


class UnsubscribedSubscriptionsByEndDateFilter(django_filters.FilterSet):
    date = django_filters.ChoiceFilter(choices=CREATION_CHOICES, method='filter_by_date')
    date_gte = django_filters.DateFilter(
        field_name='end_date', lookup_expr='gte', widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    date_lte = django_filters.DateFilter(
        field_name='end_date', lookup_expr='lte', widget=forms.TextInput(attrs={'autocomplete': 'off'}))

    def filter_by_date(self, queryset, name, value):
        if value == 'today':
            return queryset.filter(end_date=date.today())
        elif value == 'yesterday':
            return queryset.filter(end_date=date.today() - timedelta(1))
        elif value == 'last_7_days':
            return queryset.filter(
                end_date__gte=date.today() - timedelta(7), end_date__lte=date.today())
        elif value == 'last_30_days':
            return queryset.filter(
                end_date__gte=date.today() - timedelta(30), end_date__lte=date.today())
        elif value == 'this_month':
            return queryset.filter(
                end_date__month=date.today().month, end_date__year=date.today().year)
        elif value == 'last_month':
            month = date.today().month - 1 if date.today().month != 1 else 12
            year = date.today().year if date.today().month != 1 else date.today().year - 1
            return queryset.filter(end_date__month=month, end_date__year=year)
        else:
            return queryset

    class Meta:
        model = Subscription
        fields = []


class ScheduledTaskFilter(django_filters.FilterSet):
    contact_filter = django_filters.CharFilter(method='by_contact_data')
    address_filter = django_filters.CharFilter(method='by_address')
    creation_date_gte = django_filters.DateFilter(
        field_name='creation_date', lookup_expr='gte', widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    creation_date_lte = django_filters.DateFilter(
        field_name='creation_date', lookup_expr='lte', widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    execution_date_gte = django_filters.DateFilter(
        field_name='execution_date', lookup_expr='gte', widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    execution_date_lte = django_filters.DateFilter(
        field_name='execution_date', lookup_expr='lte', widget=forms.TextInput(attrs={'autocomplete': 'off'}))

    class Meta:
        model = ScheduledTask
        fields = [
            'category',
            'completed',
            'label_message',
            'special_instructions'
        ]

    def by_contact_data(self, queryset, name, value):
        return queryset.filter(
            Q(contact__id__contains=value)
            | Q(contact__name__contains=value)
            | Q(contact__id_document__contains=value)
            | Q(contact__email__icontains=value)
            | Q(contact__phone__icontains=value)
            | Q(contact__mobile__contains=value)
        )

    def by_address(self, queryset, name, value):
        return queryset.filter(address__address1__icontains=value)

class CampaignFilter(django_filters.FilterSet):
    name_icontains = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    class Meta:
        model = Campaign
        fields = {"active": ["exact"],
                  "name": ["icontains"]
                  }


class SalesRecordFilter(django_filters.FilterSet):
    date_time__gte = django_filters.DateFilter(
        field_name='date_time__date', lookup_expr='gte', widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    date_time__lte = django_filters.DateFilter(
        field_name='date_time__date', lookup_expr='lte', widget=forms.TextInput(attrs={'autocomplete': 'off'}))

    class Meta:
        model = SalesRecord
        fields = ['date_time', 'seller', 'sale_type']


class SalesRecordFilterForSeller(django_filters.FilterSet):
    date_time__gte = django_filters.DateFilter(
        field_name='date_time__date', lookup_expr='gte', widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    date_time__lte = django_filters.DateFilter(
        field_name='date_time__date', lookup_expr='lte', widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    class Meta:
        model = SalesRecord
        fields = ['date_time', 'sale_type']
        exclude = ['seller']
