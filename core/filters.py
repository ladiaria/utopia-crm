import django_filters

from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from .models import Contact, State


YESNO_CHOICES = (
    ("1", _("Yes")),
    ("0", _("No")),
)


class ContactFilter(django_filters.FilterSet):
    filter_multiple = django_filters.CharFilter(method="main_filter")
    state = django_filters.ModelChoiceFilter(queryset=State.objects.filter(active=True), method="by_state")
    active_subscriptions = django_filters.ChoiceFilter(
        choices=YESNO_CHOICES, method="with_active_subscription"
    )
    tags = django_filters.CharFilter(method="by_tags")
    address = django_filters.CharFilter(method="by_address")

    class Meta:
        model = Contact
        fields = ["filter_multiple", "subtype"]

    def main_filter(self, queryset, name, value):
        # Split the value by spaces to handle multiple terms
        terms = value.split()

        if len(terms) > 1:
            # Allow the search to have more than one term, in this case we assume that the user is searching for a
            # name and a last name
            first_name_term = terms[0]
            last_name_term = terms[1]
            queryset = queryset.filter(
                Q(name__icontains=first_name_term) & Q(last_name__icontains=last_name_term)
            )
        else:
            # Single term search
            queryset = queryset.filter(
                Q(phone__contains=value)
                | Q(mobile__contains=value)
                | Q(work_phone__contains=value)
                | Q(name__icontains=value)
                | Q(last_name__icontains=value)
                | Q(email__icontains=value)
                | Q(id_document__contains=value)
            )

        return queryset

    def by_state(self, queryset, name, value):
        return queryset.filter(addresses__state=value).distinct()

    def with_active_subscription(self, queryset, name, value):
        if value == "0":
            return queryset.exclude(subscriptions__active=True).distinct()
        elif value == "1":
            return queryset.filter(subscriptions__active=True).distinct()

    def by_tags(self, queryset, name, value):
        tags = value.split(',')
        for tag in tags:
            queryset = queryset.filter(tags__name=tag).distinct()
        return queryset

    def by_address(self, queryset, name, value):
        return queryset.filter(addresses__address_1__icontains=value).distinct()
