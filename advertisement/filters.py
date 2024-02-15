import django_filters

from django.utils.translation import gettext_lazy as _
from advertisement.models import Advertiser, AdPurchaseOrder


class AdvertiserFilter(django_filters.FilterSet):
    class Meta:
        model = Advertiser
        fields = {
            "name": ["icontains"],
            "priority": ["exact"],
        }


class AdPurchaseOrderFilter(django_filters.FilterSet):
    class Meta:
        model = AdPurchaseOrder
        fields = {
            "advertiser__name": ["icontains"],
            "seller": ["exact"],
            "bill_to": ["exact"],
            "date_created": ["exact", "gte", "lte"],
            "billed": ["exact"],
        }
        labels = {
            "advertiser": _("Advertiser"),
            "seller": _("Seller"),
            "bill_to": _("Bill to"),
            "date_created": _("Date"),
            "billed": _("Billed"),
        }
