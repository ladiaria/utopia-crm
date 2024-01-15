from django import forms

from advertisement.models import AdvertisementActivity


class AdvertisementActivityForm(forms.ModelForm):
    class Meta:
        model = AdvertisementActivity
        fields = ["date", "advertiser", "direction", "type", "notes", "seller", "status"]
