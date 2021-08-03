# coding=utf-8
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

from .models import Issue, IssueStatus
from .choices import ISSUE_SUBCATEGORIES

from core.models import Contact, Product, Subscription, Address, DynamicContactFilter, SubscriptionProduct, Activity
from core.choices import ADDRESS_TYPE_CHOICES, FREQUENCY_CHOICES, ACTIVITY_TYPES

from support.models import Seller


class SellerForm(forms.ModelForm):
    class Meta:
        model = Seller
        fields = '__all__'

    def clean_user(self):
        user = self.cleaned_data.get("user")

        if user and self.instance:
            s = Seller.objects.filter(user=user).exclude(pk=self.instance.pk)
            if s:
                seller = s[0]
                msg = _("This user is already set in seller {}".format(seller))
                raise forms.ValidationError(msg)

        return user


class NewPauseScheduledTaskForm(forms.Form):
    subscription = forms.ModelChoiceField(
        Subscription.objects.all(), widget=forms.Select(attrs={"class": "form-control"})
    )
    date_1 = forms.DateField(
        widget=forms.DateTimeInput(
            attrs={"class": "datepicker form-control float-right"}
        )
    )
    date_2 = forms.DateField(
        widget=forms.DateTimeInput(
            attrs={"class": "datepicker form-control float-right"}
        )
    )
    activity_type = forms.ChoiceField(
        widget=forms.Select(attrs={"class": "form-control"}),
        choices=ACTIVITY_TYPES,
    )

    def clean(self):
        date_1 = self.cleaned_data.get("date_1")
        date_2 = self.cleaned_data.get("date_2")

        if not date_2 > date_1:
            raise forms.ValidationError(
                _(
                    "There must be at least 1 day difference between date 2 and 1. Date 1 must be smaller than date 2"
                )
            )


class NewAddressChangeScheduledTaskForm(forms.Form):
    date_1 = forms.DateField(
        widget=forms.DateTimeInput(
            attrs={"class": "datepicker form-control float-right"}
        )
    )
    contact_address = forms.ModelChoiceField(
        Address.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    new_address = forms.BooleanField(
        label=_("New address"), required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
    new_address_1 = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    new_address_2 = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    new_address_city = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    new_address_state = forms.ChoiceField(
        required=False, widget=forms.Select(attrs={"class": "form-control"})
    )
    if getattr(settings, "USE_STATES_CHOICE"):
        new_address_state.choices = settings.STATES
    new_address_notes = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    new_address_type = forms.ChoiceField(
        required=False,
        choices=ADDRESS_TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    activity_type = forms.ChoiceField(
        widget=forms.Select(attrs={"class": "form-control"}),
        choices=ACTIVITY_TYPES,
    )
    new_label_message = forms.CharField(
        max_length=40, required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    new_special_instructions = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )

    def clean(self):
        new_address = self.cleaned_data.get("new_address")
        new_address_1 = self.cleaned_data.get("new_address_1")
        new_address_city = self.cleaned_data.get("new_address_city")
        new_address_state = self.cleaned_data.get("new_address_state")

        if new_address and not (
            new_address_1 and new_address_city and new_address_state
        ):
            raise forms.ValidationError(
                _(
                    "Please complete the new address first line, city and state if new address is selected"
                )
            )


class NewPromoForm(forms.Form):
    name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    phone = forms.CharField(
        empty_value=None, required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    mobile = forms.CharField(
        empty_value=None, required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    notes = forms.CharField(
        empty_value=None, required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": "4"})
    )
    email = forms.CharField(
        empty_value=None, required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    start_date = forms.DateField(
        widget=forms.DateInput(
            format="%Y-%m-%d", attrs={"class": "datepicker form-control"}
        )
    )
    end_date = forms.DateField(
        widget=forms.DateInput(
            format="%Y-%m-%d", attrs={"class": "datepicker form-control"}
        )
    )
    default_address = forms.ModelChoiceField(
        Address.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )


class NewSubscriptionForm(forms.Form):
    contact_id = forms.CharField(required=False)
    name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    phone = forms.CharField(
        empty_value=None, required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    mobile = forms.CharField(
        empty_value=None, required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    notes = forms.CharField(
        empty_value=None, required=False, widget=forms.Textarea(attrs={"class": "form-control"})
    )
    register_activity = forms.CharField(
        empty_value=None,
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": "4"}),
    )
    email = forms.CharField(
        empty_value=None, required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    id_document = forms.CharField(
        empty_value=None, required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    frequency = forms.ChoiceField(
        required=False,
        choices=FREQUENCY_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    payment_type = forms.ChoiceField(
        required=False,
        choices=settings.SUBSCRIPTION_PAYMENT_METHODS,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    start_date = forms.DateField(
        widget=forms.DateInput(
            format="%Y-%m-%d", attrs={"class": "datepicker form-control", "autocomplete": "off"}
        )
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(
            format="%Y-%m-%d", attrs={"class": "datepicker form-control", "autocomplete": "off"}
        )
    )
    billing_address = forms.ModelChoiceField(
        Address.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    billing_name = forms.CharField(
        empty_value=None, required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    billing_id_document = forms.CharField(
        empty_value=None, required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    billing_rut = forms.CharField(
        empty_value=None, required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    billing_phone = forms.CharField(
        empty_value=None, required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    billing_email = forms.CharField(
        empty_value=None, required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    default_address = forms.ModelChoiceField(
        Address.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def clean(self):
        contact_id = self.cleaned_data['contact_id']
        id_document = self.cleaned_data['id_document']
        email = self.cleaned_data['email']

        if Contact.objects.filter(email=email).exclude(id=contact_id).exists():
            raise ValidationError(_("This email already exists in a different contact"))

        if Contact.objects.filter(id_document=id_document).exclude(id=contact_id).exists():
            raise ValidationError(_("This id document already exists in a different contact"))


class IssueStartForm(forms.ModelForm):
    """
    Used when you want to start an issue to track logistics, what used to be 'Claims
    """

    contact = forms.ModelChoiceField(
        queryset=Contact.objects,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    widget = forms.Select(attrs={"class": "form-control"})
    # contact.disabled = True
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(type="S"),
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False,
    )

    subscription_product = forms.ModelChoiceField(
        queryset=SubscriptionProduct.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False,
    )

    subscription = forms.ModelChoiceField(
        queryset=Subscription.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False,
    )

    subcategory = forms.ChoiceField(
        choices=ISSUE_SUBCATEGORIES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    activity_type = forms.ChoiceField(
        widget=forms.Select(attrs={"class": "form-control"}),
        choices=ACTIVITY_TYPES,
    )

    status = forms.ModelChoiceField(
        required=False,
        queryset=IssueStatus.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"})
    )

    assigned_to = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.filter(is_staff=True).order_by('username'),
        widget=forms.Select(attrs={"class": "form-control"})
    )

    class Meta:
        model = Issue
        widgets = {
            "notes": forms.Textarea(attrs={"class": "form-control"}),
            "subscription_product": forms.Select(attrs={"class": "form-control"}),
            "subscription": forms.Select(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "copies": forms.NumberInput(attrs={"class": "form-control"}),
            "assigned_to": forms.Select(attrs={"class": "form-control"}),
        }
        fields = (
            "contact",
            "category",
            "subcategory",
            "notes",
            "copies",
            "subscription_product",
            "product",
            "assigned_to",
            "subscription",
            "status",
        )


class IssueChangeForm(forms.ModelForm):
    """
    Used when you want to start an issue to track logistics, what used to be 'Claims'
    """

    contact = forms.ModelChoiceField(queryset=Contact.objects, widget=forms.TextInput)
    next_action_date = forms.DateField(
        required=False, widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "datepicker form-control"}),
    )

    class Meta:
        model = Issue
        widgets = {
            "contact": forms.Textarea(attrs={"class": "form-control"}),
            "progress": forms.Textarea(attrs={"class": "form-control"}),
            "assigned_to": forms.Select(attrs={"class": "form-control"}),
            "answer_1": forms.Select(attrs={"class": "form-control"}),
            "answer_2": forms.Textarea(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }
        fields = (
            "contact",
            "status",
            "progress",
            "answer_1",
            "answer_2",
            "next_action_date",
            "assigned_to",
        )


SELECT_CONTACT_FOR_ISSUE_TYPE_CHOICES = (
    ("L", _("Logistics")),
    ("S04", _("Pause")),
    ("S05", _("Change address")),
)


class SelectContactForIssue(forms.Form):
    contact_id = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    issue_type = forms.ChoiceField(
        choices=SELECT_CONTACT_FOR_ISSUE_TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def clean_contact_id(self):
        contact_id = self.cleaned_data.get("contact_id")
        try:
            Contact.objects.get(pk=contact_id)
        except Contact.DoesNotExist:
            raise forms.ValidationError(_("Contact does not exist"))
        return contact_id


class NewAddressForm(forms.Form):
    address_1 = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    address_2 = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    address_city = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    address_state = forms.ChoiceField(
        required=False, widget=forms.Select(attrs={"class": "form-control"})
    )
    if getattr(settings, "USE_STATES_CHOICE"):
        address_state.choices = settings.STATES
    address_notes = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    address_type = forms.ChoiceField(
        required=False,
        choices=ADDRESS_TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )


class NewDynamicContactFilterForm(forms.ModelForm):
    class Meta:
        model = DynamicContactFilter
        widgets = {
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "products": forms.SelectMultiple(attrs={"class": "form-control"}),
            "newsletters": forms.SelectMultiple(attrs={"class": "form-control"}),
            "mode": forms.Select(attrs={"class": "form-control"}),
            "mailtrain_id": forms.TextInput(attrs={"class": "form-control"}),
        }
        fields = (
            "description",
            "products",
            "newsletters",
            "allow_promotions",
            "allow_polls",
            "mode",
            "autosync",
            "mailtrain_id",
        )


class NewActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = (
            "contact",
            "direction",
            "activity_type",
            "notes",
        )
        widgets = {
            "contact": forms.TextInput(attrs={"class": "form-control d-none"}),
            "direction": forms.Select(attrs={"class": "form-control"}),
            "activity_type": forms.Select(attrs={"class": "form-control"}),
            "notes": forms.TextInput(attrs={"class": "form-control"}),
        }
