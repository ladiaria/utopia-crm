from django import forms

from advertisement.models import AdvertisementActivity, Advertiser, Agency


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


class AddAgencyForm(forms.ModelForm):
    class Meta:
        model = Agency
        fields = [
            "name",
            "main_contact",
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
