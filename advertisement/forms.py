from django import forms

from core.models import Contact
from advertisement.models import AdvertisementActivity, Advertiser


class AdvertisementActivityForm(forms.ModelForm):
    class Meta:
        model = AdvertisementActivity
        fields = ["date", "advertiser", "direction", "type", "notes", "seller", "status"]


class AddAdvertiserForm(forms.ModelForm):

    class Meta:
        model = Advertiser
        fields = [
            "name",
            "main_contact",
            "type",
            "email",
            "phone",
            "priority",
            "billing_name",
            "billing_id_document",
            "utr",
            "billing_phone",
            "billing_address",
            "billing_email",
            "main_seller",
        ]
