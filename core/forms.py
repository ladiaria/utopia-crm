# coding=utf-8
from pymailcheck import split_email

from django import forms
from django.core.mail import mail_managers
from django.utils.translation import gettext as _

from util.email_typosquash import clean_email as email_typosquash_clean, replacement_request_add

from .models import Contact, Subscription, Address, EmailBounceActionLog


no_email_validation_msg = _('email must be left blank if the contact has no email')


class EmailValidationError(forms.ValidationError):

    def __init__(self, *args, **kwargs):
        valid = kwargs.pop("valid", False)
        replacement = kwargs.pop("replacement", "")
        suggestion = kwargs.pop("suggestion", "")
        splitted = kwargs.pop("splitted", "")
        submit_btn_selector = kwargs.pop("submit_btn_selector", "")
        super().__init__(*args, **kwargs)
        self.valid = valid
        self.replacement = replacement
        self.suggestion = suggestion
        self.splitted = splitted
        self.submit_btn_selector = submit_btn_selector


class EmailValidationForm(forms.Form):
    email_was_valid = forms.BooleanField(widget=forms.HiddenInput(), required=False)
    email_replaced = forms.EmailField(widget=forms.HiddenInput(), required=False)
    email_replacement = forms.EmailField(widget=forms.HiddenInput(), required=False)
    email_suggestion = forms.EmailField(widget=forms.HiddenInput(), required=False)

    @staticmethod
    def email_is_bouncer(email):
        return EmailBounceActionLog.email_is_bouncer(email)

    def checked_products(self):
        return [int(val) for key, val in self.data.items() if key.startswith("check-")]

    def bound_product_values(self, product_id):
        if self.is_bound:
            address = self.data.get("address-%d" % product_id)
            result = {"address": int(address)} if address else {}
            for key in ("copies", "message", "instructions"):
                val = self.data.get("%s-%d" % (key, product_id))
                if val:
                    result[key] = val
            return result

    def email_extra_clean(self, cleaned_data):

        email, was_valid = cleaned_data.get("email"), cleaned_data.get("email_was_valid")
        replacement, suggestion = cleaned_data.get("email_replacement"), cleaned_data.get("email_suggestion")
        if was_valid:
            if not replacement:
                mail_managers(
                    _("WARN: wrong email replcement risk"),
                    "The email %s can be soon be overwritten by the emailfix management command." % email,
                    True,
                )
            return email
        elif email:
            splitted = split_email(email)
            if suggestion:
                replacement_request_add(split_email(cleaned_data.get("email_replaced"))["domain"], splitted["domain"])
                return email
            elif not replacement:

                email_typosquash_clean_result = email_typosquash_clean(email)
                valid = email_typosquash_clean_result["valid"]
                replacement = email_typosquash_clean_result.get("replacement", "")
                if not valid or replacement:
                    suggestion = email_typosquash_clean_result.get("suggestion", "")
                    if replacement or suggestion:
                        admin_submit_btn_name = next(
                            (k for k in ("_save", "_addanother", "_continue") if k in self.data), None
                        )
                        self.add_error(
                            "email",
                            EmailValidationError(
                                _('Confirmation for email replacement is needed'),
                                code='email_typosquash_clean_confirmation',
                                valid=valid,
                                replacement=replacement,
                                suggestion=suggestion,
                                splitted=splitted,
                                submit_btn_selector=(
                                    ":submit[name='%s']" % admin_submit_btn_name
                                ) if admin_submit_btn_name else "#send_form",
                            ),
                        )
                    else:
                        self.add_error(
                            "email",
                            EmailValidationError(
                                _('Invalid email: %(email)s'),
                                code='email_typosquash_clean_invalid',
                                params={'email': email},
                            ),
                        )
                else:
                    return email


def validate_no_email(form, no_email, email):
    """
    If no_email is checked, the the email should be None.
    If no_email is not checked, then no assertions should be made because the contact's email is yet uknown.
    """
    if no_email and email:
        form.add_error('no_email', forms.ValidationError(no_email_validation_msg))


class ContactAdminForm(EmailValidationForm, forms.ModelForm):
    class Meta:
        model = Contact
        fields = "__all__"
        widgets = {
            "birthdate": forms.TextInput(attrs={"class": "form-control datepicker"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        protected = cleaned_data.get("protected")
        protection_reason = cleaned_data.get("protection_reason")

        if protected and not protection_reason:
            msg = _("This field must be provided if the contact is protected")
            self.add_error("protection_reason", forms.ValidationError(msg))
        else:
            email = cleaned_data.get("email")
            if email:
                email = self.email_extra_clean(cleaned_data)

            # no_email validation:
            validate_no_email(self, cleaned_data.get("no_email"), email)


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

    def clean_email(self):
        email = self.cleaned_data.get("email")

        if email and self.instance:
            email = email.lower()
            s = Contact.objects.filter(email=email).exclude(pk=self.instance.pk)
            if s:
                msg = _("Error: Contact {} already has this email".format(s[0].id))
                raise forms.ValidationError(msg)

        return email


class SubscriptionAdminForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super(SubscriptionAdminForm, self).__init__(*args, **kwargs)
        if 'instance' in kwargs:
            self.fields['billing_address'].queryset = Address.objects.filter(
                contact=kwargs['instance'].contact)


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
