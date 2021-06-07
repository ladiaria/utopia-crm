import django_filters

from django.utils.translation import ugettext_lazy as _
from django.db.models import Q
from django.conf import settings

from .models import Contact


YESNO_CHOICES = (
    ("1", _("Yes")),
    ("0", _("No")),
)


class ContactFilter(django_filters.FilterSet):
    filter_multiple = django_filters.CharFilter(method="by_phone_and_email")
    state = django_filters.ChoiceFilter(choices=settings.STATES, method="by_state")
    active_subscriptions = django_filters.ChoiceFilter(
        choices=YESNO_CHOICES, method="with_active_subscription"
    )
    tags = django_filters.CharFilter(method="by_tags")

    class Meta:
        model = Contact
        fields = ["filter_multiple", "subtype"]

    def by_phone_and_email(self, queryset, name, value):
        return queryset.filter(
            Q(phone__contains=value)
            | Q(mobile__contains=value)
            | Q(work_phone__contains=value)
            | Q(name__icontains=value)
            | Q(email__icontains=value)
            | Q(id_document__contains=value)
        )

    def by_state(self, queryset, name, value):
        return queryset.filter(addresses__state=value).distinct()

    def with_active_subscription(self, queryset, name, value):
        if value == "0":
            return queryset.exclude(subscriptions__active=True).distinct()
        elif value == "1":
            return queryset.filter(subscriptions__active=True).distinct()

    def by_tags(self, queryset, name, value):
        tags = value.split(',')
        if tags:
            queryset = queryset.filter(tags__name__in=tags).distinct()
        return queryset
