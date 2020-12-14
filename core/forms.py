# coding=utf-8
import re
from django import forms
from django.utils.translation import gettext as _
from .models import Contact, Subscription, Address


class ContactAdminForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = '__all__'

    def clean(self):
        protected = self.cleaned_data.get('protected')
        protection_reason = self.cleaned_data.get('protection_reason')

        if protected and not protection_reason:
            msg = _('This field must be provided if the contact is protected')
            self.add_error('protection_reason', forms.ValidationError(msg))

        return self.cleaned_data

    def clean_id_document(self):
        id_document = self.cleaned_data.get('id_document')

        if id_document and not id_document.isdigit():
            msg = _('This only admits numeric characters')
            raise forms.ValidationError(msg)

        if id_document and self.instance:
            s = Contact.objects.filter(id_document=id_document).exclude(
                pk=self.instance.pk)
            if s:
                msg = (_('Contact {} already has this id document number'.format(s[0].id)))
                raise forms.ValidationError(msg)

        return id_document

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone and not phone.replace('/', '').isdigit():
            raise forms.ValidationError(_('Only numbers and slashes are accepted'))
        return phone

    def clean_work_phone(self):
        work_phone = self.cleaned_data.get('work_phone')
        if work_phone and not work_phone.replace('/', '').isdigit():
            raise forms.ValidationError(_('Only numbers and slashes are accepted'))
        return work_phone

    def clean_mobile(self):
        mobile = self.cleaned_data.get('mobile')
        if mobile and not mobile.replace('/', '').isdigit():
            raise forms.ValidationError(_('Only numbers and slashes are accepted'))
        return mobile

    """
    def clean_email(self):
        email = self.cleaned_data('email')
        email_re = re.compile(
            r'^[A-Z0-9._%-][+A-Z0-9._%-]*@(?:[A-Z0-9-]+\.)+[A-Z]{2,4}$', re.IGNORECASE)
        if not email_re.search(email):
            raise forms.ValidationError(_('This is not a valid email address'))

        return email
    """


class SubscriptionAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(SubscriptionAdminForm, self).__init__(*args, **kwargs)
        self.fields['billing_address'].queryset = self.instance.contact.addresses.all()

    class Meta:
        model = Subscription
        fields = '__all__'


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = (
            'contact', 'address_1', 'address_2', 'city', 'state', 'email',
            'notes', 'address_type', 'default')

    def clean(self):
        default = self.cleaned_data.get('default')
        contact = self.cleaned_data.get('contact')
        if default:
            sub_other_addresses = Address.objects.filter(
                contact=contact)
            if sub_other_addresses:
                for s in sub_other_addresses:
                    s.default = False
                    s.save()
        return self.cleaned_data
