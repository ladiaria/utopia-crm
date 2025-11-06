# coding=utf-8
from pymailcheck import split_email
import json

from django.conf import settings
from django import forms
from django.core.mail import mail_managers
from django.utils.translation import gettext as _
from django.utils.safestring import mark_safe

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

        email = cleaned_data.get('email')

        # Skip "complex" validations if disabled in settings
        # TODO: rename this setting to CORE_EMAIL[_(COMPLEX|DOMAIN|TYPOSQUASH)]_VALIDATION_ENABLED
        if not getattr(settings, 'EMAIL_VALIDATION_ENABLED', True):
            return email

        was_valid = cleaned_data.get("email_was_valid")
        replacement, suggestion = cleaned_data.get("email_replacement"), cleaned_data.get("email_suggestion")
        if was_valid:
            if not replacement:
                mail_managers(
                    _("WARN: wrong email replacement risk"),
                    f"The email {email} can soon be overwritten by the emailfix management command.",
                    True,
                )
            return email
        elif email:
            splitted = split_email(email)
            if suggestion:
                replacement_request_add(
                    split_email(cleaned_data.get("email_replaced"))["domain"],
                    splitted["domain"],
                    getattr(self, 'instance', None),
                )
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
                                    (":submit[name='%s']" % admin_submit_btn_name)
                                    if admin_submit_btn_name
                                    else "#send_form"
                                ),
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

        raw_tags = self.data.get("tags")
        if raw_tags:
            try:
                parsed_tags = json.loads(raw_tags)
                if isinstance(parsed_tags, list) and all("value" in tag for tag in parsed_tags):
                    cleaned_data["tags"] = [tag["value"] for tag in parsed_tags]
            except json.JSONDecodeError:
                pass
        else:
            cleaned_data["tags"] = []

        return cleaned_data

    def clean_id_document(self):
        id_document = self.cleaned_data.get("id_document")

        if id_document and self.instance:
            s = Contact.objects.filter(id_document=id_document).exclude(pk=self.instance.pk)
            if s.exists():
                contact = s[0]
                url = contact.get_absolute_url()
                link_label = _("Open in a new tab")
                url_str = f'<a href="{url}" target="_blank">{link_label}</a>'
                msg = mark_safe(
                    _("Contact %(contact_id)s already has this document. %(url_str)s")
                    % {"contact_id": contact.id, "url_str": url_str}
                )
                raise forms.ValidationError(msg)

        return id_document

    def clean_email(self):
        email = self.cleaned_data.get("email")

        if email and self.instance:
            email = email.lower()
            s = Contact.objects.filter(email=email).exclude(pk=self.instance.pk)
            if s.exists():
                contact = s[0]
                url = contact.get_absolute_url()
                link_label = _("Open in a new tab")
                url_str = f'<a href="{url}" target="_blank">{link_label}</a>'
                msg = mark_safe(
                    _("Contact %(contact_id)s already has this email. %(url_str)s")
                    % {"contact_id": contact.id, "url_str": url_str}
                )
                raise forms.ValidationError(msg)

        return email


class SubscriptionAdminForm(forms.ModelForm):

    frequency = forms.IntegerField(required=True, help_text=_("Frequency of billing in months"))

    class Meta:
        model = Subscription
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        user = self.request.user
        subscription_type = cleaned_data.get('type')
        free_subscription_requested_by = cleaned_data.get('free_subscription_requested_by')
        end_date = cleaned_data.get('end_date')
        if not user.has_perm('core.can_add_free_subscription'):
            original_type = self.instance.type if self.instance else None
            if subscription_type in ("F", "S") and original_type != subscription_type:
                self.add_error("type", _("You don't have permission to set this subscription as free"))
        if subscription_type in ("F", "S") and not free_subscription_requested_by:
            self.add_error(
                "free_subscription_requested_by", _("You need to select who requested the subscription if it's free")
            )
        if subscription_type in ("F", "S") and not end_date:
            self.add_error("end_date", _("Free subscriptions must have an end date"))
        # t949 - If subscription is promotion it must not have a payment type and must have an end date
        if subscription_type == "P" and cleaned_data.get('payment_type'):
            self.add_error("payment_type", _("Promotion subscriptions must not have a payment type"))
        if subscription_type == "P" and not end_date:
            self.add_error("end_date", _("Promotion subscriptions must have an end date"))
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super(SubscriptionAdminForm, self).__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        if instance:
            self.fields['billing_address'].queryset = Address.objects.filter(contact=instance.contact)


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
