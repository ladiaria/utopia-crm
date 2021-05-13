# coding=utf-8
from django import forms
from django.utils.translation import gettext as _
from .models import Contact, Subscription, Address


no_email_validation_msg = _('email must be left blank if the contact has no email')


def validate_no_email(form, no_email, email):
    """
    If no_email is checked, the the email should be None.
    If no_email is not checked, then no assertions should be made because the contact's email is yet uknown.
    """
    if no_email and email:
        form.add_error('no_email', forms.ValidationError(no_email_validation_msg))


class ContactAdminForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = "__all__"
        widgets = {
            "birthdate": forms.TextInput(attrs={"class": "form-control datepicker"}),
        }

    def clean(self):
        protected = self.cleaned_data.get("protected")
        protection_reason = self.cleaned_data.get("protection_reason")
        email = self.cleaned_data.get("email")
        no_email = self.cleaned_data.get("no_email")

        if protected and not protection_reason:
            msg = _("This field must be provided if the contact is protected")
            self.add_error("protection_reason", forms.ValidationError(msg))

        # no_email validation:
        validate_no_email(self, no_email, email)

        return self.cleaned_data

    def clean_id_document(self):
        id_document = self.cleaned_data.get("id_document")

        if id_document and not id_document.isdigit():
            msg = _("This only admits numeric characters")
            raise forms.ValidationError(msg)

        if id_document and self.instance:
            s = Contact.objects.filter(id_document=id_document).exclude(
                pk=self.instance.pk
            )
            if s:
                msg = _(
                    "Contact {} already has this id document number".format(s[0].id)
                )
                raise forms.ValidationError(msg)

        return id_document

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if phone and not phone.replace("/", "").isdigit():
            raise forms.ValidationError(_("Only numbers and slashes are accepted"))
        return phone

    def clean_work_phone(self):
        work_phone = self.cleaned_data.get("work_phone")
        if work_phone and not work_phone.replace("/", "").isdigit():
            raise forms.ValidationError(_("Only numbers and slashes are accepted"))
        return work_phone

    def clean_mobile(self):
        mobile = self.cleaned_data.get("mobile")
        if mobile and not mobile.replace("/", "").isdigit():
            raise forms.ValidationError(_("Only numbers and slashes are accepted"))
        return mobile


class SubscriptionAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(SubscriptionAdminForm, self).__init__(*args, **kwargs)
        self.fields["billing_address"].queryset = self.instance.contact.addresses.all()

    class Meta:
        model = Subscription
        fields = "__all__"


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = (
            "contact",
            "address_1",
            "address_2",
            "city",
            "state",
            "email",
            "notes",
            "address_type",
            "default",
        )

    def clean(self):
        default = self.cleaned_data.get("default")
        contact = self.cleaned_data.get("contact")
        if default:
            sub_other_addresses = Address.objects.filter(contact=contact)
            if sub_other_addresses:
                for s in sub_other_addresses:
                    s.default = False
                    s.save()
        return self.cleaned_data
