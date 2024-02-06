from django import forms
from django.forms import inlineformset_factory

from advertisement.models import AdvertisementActivity, Advertiser, AdPurchaseOrder, Agency, Ad


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

class AdPurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = AdPurchaseOrder
        fields = [
            "advertiser",
            "seller",
            "bill_to",
            "notes",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "advertiser": forms.HiddenInput(),
        }

class AdForm(forms.ModelForm):
    class Meta:
        model = Ad
        fields = ["order", "adtype", "description", "price"]
        widgets = {
            "order": forms.HiddenInput(),
        }


AdFormSet = inlineformset_factory(AdPurchaseOrder, Ad, form=AdForm, extra=1)