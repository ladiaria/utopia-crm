import django_filters
from unidecode import unidecode
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, Func

from .models import Contact, State


YESNO_CHOICES = (
    ("1", _("Yes")),
    ("0", _("No")),
)


class Unaccent(Func):
    function = "UNACCENT"


def apply_main_filter(queryset, value):
    """
    Reusable function to apply the main filter logic to a queryset.

    Args:
    - queryset: The queryset to filter.
    - value: The search term(s) to filter by.

    Returns:
    - Filtered queryset.
    """
    # Normalize the search value
    normalized_value = unidecode(value)
    terms = normalized_value.split()

    # Annotate for unaccented searches
    queryset = queryset.annotate(
        unaccented_name=Unaccent('name'),
        unaccented_last_name=Unaccent('last_name')
    )

    if len(terms) > 1:
        # Handle multiple terms
        first_name_term = terms[0]
        last_name_term = terms[1]
        queryset = queryset.filter(
            (
                Q(unaccented_name__icontains=first_name_term) &
                Q(unaccented_last_name__icontains=last_name_term)
            ) |
            Q(unaccented_name__icontains=f"{first_name_term} {last_name_term}") |
            Q(unaccented_name__icontains=normalized_value)
        )
    else:
        queryset = queryset.filter(
            Q(id__contains=value)
            | Q(phone__contains=value)
            | Q(mobile__contains=value)
            | Q(work_phone__contains=value)
            | Q(unaccented_name__icontains=normalized_value)
            | Q(unaccented_last_name__icontains=normalized_value)
            | Q(email__icontains=value)
            | Q(id_document__contains=value)
        )

    return queryset


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
        return apply_main_filter(queryset, value)

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
