from django import forms
from django.forms.models import inlineformset_factory

from .models import Invoice, InvoiceItem


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['payment_type']


InvoiceItemFormSet = inlineformset_factory(Invoice, InvoiceItem, fields=['product', 'copies'])
