from datetime import date, timedelta

import django_filters
from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.db.models import Q

from core.models import Activity, ContactCampaignStatus, Subscription, Campaign, Product
from .models import Issue, IssueSubcategory, IssueResolution, Seller, ScheduledTask, SalesRecord, SellerConsoleAction


CREATION_CHOICES = (
    ('today', _('Today')),
    ('yesterday', _('Yesterday')),
    ('last_7_days', _('Last 7 days')),
    ('next_7_days', _('Next 7 days')),
    ('last_30_days', _('Last 30 days')),
    ('this_month', _('This month')),
    ('last_month', _('Last month')),
    ('no_date', _('No date set')),
    ('custom', _('Custom')),
)


class IssueFilter(django_filters.FilterSet):
    date = django_filters.ChoiceFilter(
        choices=CREATION_CHOICES,
        method='filter_by_date',
        label=_('Issue Date'),
        help_text=_('When the issue was created')
    )
    date_gte = django_filters.DateFilter(
        field_name='date',
        lookup_expr='gte',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label=_('From')
    )
    date_lte = django_filters.DateFilter(
        field_name='date',
        lookup_expr='lte',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label=_('To')
    )
    next_action_date = django_filters.ChoiceFilter(
        choices=CREATION_CHOICES,
        method='filter_by_next_action_date',
        label=_('Next Action Date'),
        help_text=_('When the next action is scheduled')
    )
    next_action_date_gte = django_filters.DateFilter(
        field_name='next_action_date',
        lookup_expr='gte',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label=_('From')
    )
    next_action_date_lte = django_filters.DateFilter(
        field_name='next_action_date',
        lookup_expr='lte',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label=_('To')
    )
    assigned_to = django_filters.ModelChoiceFilter(
        queryset=User.objects.filter(is_staff=True).order_by('username'),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    resolution = django_filters.ModelChoiceFilter(
        queryset=IssueResolution.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_('Resolution')
    )
    unassigned = django_filters.BooleanFilter(
        method='filter_unassigned',
        label=_('Unassigned only'),
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    exclude_finished = django_filters.BooleanFilter(
        method='filter_exclude_finished',
        label=_('Exclude finished'),
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = Issue
        fields = ['category', 'sub_category', 'status', 'assigned_to', 'resolution']

    def filter_by_date(self, queryset, name, value):
        if value == 'today':
            return queryset.filter(date=date.today())
        elif value == 'yesterday':
            return queryset.filter(date=date.today() - timedelta(1))
        elif value == 'last_7_days':
            return queryset.filter(date__gte=date.today() - timedelta(7), date__lte=date.today())
        elif value == 'next_7_days':
            return queryset.filter(date__gte=date.today(), date__lte=date.today() + timedelta(7))
        elif value == 'last_30_days':
            return queryset.filter(date__gte=date.today() - timedelta(30), date__lte=date.today())
        elif value == 'this_month':
            return queryset.filter(date__month=date.today().month, date__year=date.today().year)
        elif value == 'last_month':
            month = date.today().month - 1 if date.today().month != 1 else 12
            year = date.today().year if date.today().month != 1 else date.today().year - 1
            return queryset.filter(date__month=month, date__year=year)
        else:
            return queryset

    def filter_unassigned(self, queryset, name, value):
        if value:
            return queryset.filter(assigned_to__isnull=True)
        return queryset

    def filter_exclude_finished(self, queryset, name, value):
        if value:
            finished_list = getattr(settings, 'ISSUE_STATUS_FINISHED_LIST', [])
            return queryset.exclude(status__slug__in=finished_list)
        return queryset

    def filter_by_next_action_date(self, queryset, name, value):
        today = date.today()
        if value == 'today':
            return queryset.filter(next_action_date=today)
        elif value == 'yesterday':
            return queryset.filter(next_action_date=today - timedelta(1))
        elif value == 'last_7_days':
            return queryset.filter(
                next_action_date__gte=today - timedelta(7),
                next_action_date__lte=today
            )
        elif value == 'next_7_days':
            return queryset.filter(
                next_action_date__gte=today,
                next_action_date__lte=today + timedelta(7)
            )
        elif value == 'last_30_days':
            return queryset.filter(
                next_action_date__gte=today - timedelta(30),
                next_action_date__lte=today
            )
        elif value == 'this_month':
            return queryset.filter(
                next_action_date__month=today.month,
                next_action_date__year=today.year
            )
        elif value == 'last_month':
            month = today.month - 1 if today.month != 1 else 12
            year = today.year if today.month != 1 else today.year - 1
            return queryset.filter(next_action_date__month=month, next_action_date__year=year)
        elif value == 'no_date':
            return queryset.filter(next_action_date__isnull=True)
        else:
            return queryset


class InvoicingIssueFilter(IssueFilter):
    sub_category = django_filters.ModelChoiceFilter(
        queryset=IssueSubcategory.objects.filter(category='I'), widget=forms.Select(attrs={"class": "form-control"})
    )


class ScheduledActivityFilter(django_filters.FilterSet):
    seller_console_action = django_filters.ModelChoiceFilter(
        queryset=SellerConsoleAction.objects.filter(is_active=True)
    )
    # Add date range filters for the subscription end date
    # These will be used in the view to filter activities after they've been annotated
    subscription_end_date_min = django_filters.DateFilter(
        label=_('Subscription End Date From'),
        widget=forms.DateInput(attrs={'type': 'date'}),
        method='filter_subscription_end_date_min',
    )
    subscription_end_date_max = django_filters.DateFilter(
        label=_('Subscription End Date To'),
        widget=forms.DateInput(attrs={'type': 'date'}),
        method='filter_subscription_end_date_max',
    )

    def filter_subscription_end_date_min(self, queryset, name, value):
        # This is a placeholder method - actual filtering happens in the view
        return queryset

    def filter_subscription_end_date_max(self, queryset, name, value):
        # This is a placeholder method - actual filtering happens in the view
        return queryset

    class Meta:
        model = Activity
        fields = ['status', 'campaign', 'seller_console_action']


class ContactCampaignStatusFilter(django_filters.FilterSet):
    seller = django_filters.ModelChoiceFilter(queryset=Seller.objects.filter(internal=True).order_by('name'))
    date_assigned_min = django_filters.DateFilter(
        field_name='date_assigned',
        lookup_expr='gte',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    date_assigned_max = django_filters.DateFilter(
        field_name='date_assigned',
        lookup_expr='lte',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    last_action_date_min = django_filters.DateFilter(
        field_name='last_action_date',
        lookup_expr='gte',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    last_action_date_max = django_filters.DateFilter(
        field_name='last_action_date',
        lookup_expr='lte',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )

    class Meta:
        model = ContactCampaignStatus
        fields = ["seller", "status"]


class UnsubscribedSubscriptionsByEndDateFilter(django_filters.FilterSet):
    date = django_filters.ChoiceFilter(choices=CREATION_CHOICES, method='filter_by_date')
    date_gte = django_filters.DateFilter(
        field_name='end_date', lookup_expr='gte', widget=forms.TextInput(attrs={'autocomplete': 'off'})
    )
    date_lte = django_filters.DateFilter(
        field_name='end_date', lookup_expr='lte', widget=forms.TextInput(attrs={'autocomplete': 'off'})
    )

    def filter_by_date(self, queryset, name, value):
        if value == 'today':
            return queryset.filter(end_date=date.today())
        elif value == 'yesterday':
            return queryset.filter(end_date=date.today() - timedelta(1))
        elif value == 'last_7_days':
            return queryset.filter(end_date__gte=date.today() - timedelta(7), end_date__lte=date.today())
        elif value == 'last_30_days':
            return queryset.filter(end_date__gte=date.today() - timedelta(30), end_date__lte=date.today())
        elif value == 'this_month':
            return queryset.filter(end_date__month=date.today().month, end_date__year=date.today().year)
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
        field_name='creation_date', lookup_expr='gte', widget=forms.TextInput(attrs={'autocomplete': 'off'})
    )
    creation_date_lte = django_filters.DateFilter(
        field_name='creation_date', lookup_expr='lte', widget=forms.TextInput(attrs={'autocomplete': 'off'})
    )
    execution_date_gte = django_filters.DateFilter(
        field_name='execution_date', lookup_expr='gte', widget=forms.TextInput(attrs={'autocomplete': 'off'})
    )
    execution_date_lte = django_filters.DateFilter(
        field_name='execution_date', lookup_expr='lte', widget=forms.TextInput(attrs={'autocomplete': 'off'})
    )

    class Meta:
        model = ScheduledTask
        fields = ['category', 'completed', 'label_message', 'special_instructions']

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
        fields = {"active": ["exact"], "name": ["icontains"]}


class SalesRecordFilter(django_filters.FilterSet):
    payment_method_choices = getattr(settings, 'SUBSCRIPTION_PAYMENT_METHODS', ())
    validated = django_filters.BooleanFilter(field_name='subscription__validated')
    date_time__gte = django_filters.DateFilter(
        field_name='date_time__date', lookup_expr='gte', widget=forms.TextInput(attrs={'autocomplete': 'off'})
    )
    date_time__lte = django_filters.DateFilter(
        field_name='date_time__date', lookup_expr='lte', widget=forms.TextInput(attrs={'autocomplete': 'off'})
    )
    start_date__gte = django_filters.DateFilter(
        field_name='subscription__start_date',
        lookup_expr='gte',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label=_('Subscription start date (min)'),
    )
    start_date__lte = django_filters.DateFilter(
        field_name='subscription__start_date',
        lookup_expr='lte',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label=_('Subscription start date (max)'),
    )
    seller = django_filters.ModelMultipleChoiceFilter(
        queryset=Seller.objects.filter(salesrecord__isnull=False, internal=True).order_by('name').distinct(),
        field_name='seller',
    )
    payment_method = django_filters.MultipleChoiceFilter(
        choices=payment_method_choices, field_name="subscription__payment_type"
    )
    products = django_filters.ModelMultipleChoiceFilter(
        queryset=Product.objects.filter(type__in=['S', 'O'], active=True).order_by('name'),
        field_name='products',
        label=_('Products'),
    )

    class Meta:
        model = SalesRecord
        fields = ['date_time', 'seller', 'sale_type']


class SalesRecordFilterForSeller(django_filters.FilterSet):
    payment_method_choices = getattr(settings, 'SUBSCRIPTION_PAYMENT_METHODS', ())
    date_time__gte = django_filters.DateFilter(
        field_name='date_time__date', lookup_expr='gte', widget=forms.TextInput(attrs={'autocomplete': 'off'})
    )
    date_time__lte = django_filters.DateFilter(
        field_name='date_time__date', lookup_expr='lte', widget=forms.TextInput(attrs={'autocomplete': 'off'})
    )
    start_date__gte = django_filters.DateFilter(
        field_name='subscription__start_date',
        lookup_expr='gte',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label=_('Subscription start date (min)'),
    )
    start_date__lte = django_filters.DateFilter(
        field_name='subscription__start_date',
        lookup_expr='lte',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label=_('Subscription start date (max)'),
    )
    payment_method = django_filters.MultipleChoiceFilter(
        choices=payment_method_choices, field_name="subscription__payment_type"
    )
    products = django_filters.ModelMultipleChoiceFilter(
        queryset=Product.objects.filter(type__in=['S', 'O'], active=True).order_by('name'),
        field_name='products',
        label=_('Products'),
    )

    class Meta:
        model = SalesRecord
        fields = ['date_time', 'sale_type']
        exclude = ['seller']


class SubscriptionEndDateFilter(django_filters.FilterSet):
    end_date_min = django_filters.DateFilter(
        field_name='end_date', lookup_expr='gte', label='End Date From', widget=forms.DateInput(attrs={'type': 'date'})
    )
    end_date_max = django_filters.DateFilter(
        field_name='end_date', lookup_expr='lte', label='End Date To', widget=forms.DateInput(attrs={'type': 'date'})
    )
    contact_name = django_filters.CharFilter(field_name='contact__name', lookup_expr='icontains', label='Contact Name')
    contact_id_document = django_filters.CharFilter(
        field_name='contact__id_document', lookup_expr='icontains', label='Contact ID Document'
    )
    products = django_filters.ModelMultipleChoiceFilter(
        queryset=Product.objects.all(),
        field_name='products',
        label='Products',
    )

    class Meta:
        model = Subscription
        fields = ['end_date_min', 'end_date_max', 'contact_name', 'contact_id_document', 'products']

    def filter_products(self, queryset, name, value):
        if value:
            return queryset.filter(products__in=value).distinct()
        return queryset
