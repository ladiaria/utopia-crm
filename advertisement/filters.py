import django_filters

from django.utils.translation import gettext_lazy as _
from advertisement.models import Advertiser


class AdvertiserFilter(django_filters.FilterSet):
    class Meta:
        model = Advertiser
        fields = {
            "name": ["icontains"],
            "priority": ["exact"],
        }
