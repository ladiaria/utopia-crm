from django import forms

from core.models import Address
from advertisement.models import AdvertisementActivity, Advertiser


class AdvertisementActivityForm(forms.ModelForm):
    class Meta:
        model = AdvertisementActivity
        fields = ["date", "advertiser", "direction", "type", "notes", "seller", "status"]


class AddAdvertiserForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(AddAdvertiserForm, self).__init__(*args, **kwargs)
        # Limit the choices for the address field to only those related to the contact
        if self.instance and self.instance.id:
            self.fields['billing_address'].queryset = self.instance.addresses.all()
        else:
            self.fields['billing_address'].queryset = Address.objects.none()

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
