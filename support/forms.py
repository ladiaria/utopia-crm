# coding=utf-8
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django import forms

from .models import Issue
from .choices import ISSUE_SUBCATEGORIES

from core.models import Contact, Product, Subscription, Address, DynamicContactFilter
from core.choices import ADDRESS_TYPE_CHOICES, FREQUENCY_CHOICES

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


class ServiceIssueStartForm(forms.ModelForm):
    """
    Used when you want to start an issue to change something on a Contact, what used to be 'Events'
    """

    logistics_subcategories = [("", "-----")]
    for subcategory in ISSUE_SUBCATEGORIES:
        # Only show the options that are set as logistics, they all start with an L on the key
        if subcategory[0] in ("S04", "S05"):
            logistics_subcategories.append(subcategory)
    subcategory = forms.ChoiceField(choices=logistics_subcategories)

    class Meta:
        model = Issue
        fields = ("contact", "category", "subcategory", "notes", "subscription")


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
        required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
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
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    mobile = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"class": "form-control"})
    )
    email = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
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
    name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    phone = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    mobile = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"class": "form-control"})
    )
    email = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    id_document = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
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
            format="%Y-%m-%d", attrs={"class": "datepicker form-control"}
        )
    )
    billing_address = forms.ModelChoiceField(
        Address.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    billing_name = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    billing_id_document = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    billing_rut = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    billing_phone = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    billing_email = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    default_address = forms.ModelChoiceField(
        Address.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )


class GestionStartForm(forms.ModelForm):
    """
    Used when you want to start an issue to track debtors, what used to be a 'CollectionIssue'
    """

    class Meta:
        model = Issue
        fields = (
            "contact",
            "date",
            "category",
            "subcategory",
            "notes",
            "assigned_to",
            "progress",
            "answer_1",
            "answer_2",
            "status",
            "end_date",
            "next_action_date",
            "closing_date",
            "subscription",
        )


class LogisticsIssueStartForm(forms.ModelForm):
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
    )

    # Add a default empty option
    logistics_subcategories = [("", "-----")]
    for subcategory in ISSUE_SUBCATEGORIES:
        # Only show the options that are set as logistics, they all start with an L on the key
        if subcategory[0][0] == "L":
            logistics_subcategories.append(subcategory)
    subcategory = forms.ChoiceField(
        choices=logistics_subcategories,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Issue
        widgets = {
            "notes": forms.Textarea(attrs={"class": "form-control"}),
            "subscription": forms.Select(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "copies": forms.NumberInput(attrs={"class": "form-control"}),
        }
        fields = (
            "contact",
            "category",
            "subcategory",
            "notes",
            "copies",
            "subscription_product",
            "subscription",
            "product",
        )


class LogisticsIssueChangeForm(forms.ModelForm):
    """
    Used when you want to start an issue to track logistics, what used to be 'Claims'
    """

    contact = forms.ModelChoiceField(queryset=Contact.objects, widget=forms.TextInput)
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(type="S", bundle_product=False)
    )
    # Add a default empty option
    logistics_subcategories = [("", "-----")]
    for subcategory in ISSUE_SUBCATEGORIES:
        # Only show the options that are set as logistics, they all start with an L on the key
        if subcategory[0][0] == "L":
            logistics_subcategories.append(subcategory)

    class Meta:
        model = Issue
        widgets = {
            "progress": forms.Textarea(attrs={"class": "form-control"}),
            "subcategory": forms.Select(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "copies": forms.NumberInput(attrs={"class": "form-control"}),
            "assigned_to": forms.Select(attrs={"class": "form-control"}),
            "answer_1": forms.Select(attrs={"class": "form-control"}),
            "answer_2": forms.Textarea(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }
        fields = (
            "contact",
            "date",
            "category",
            "subcategory",
            "notes",
            "assigned_to",
            "progress",
            "answer_1",
            "answer_2",
            "status",
            "end_date",
            "next_action_date",
            "closing_date",
            "subscription",
            "product",
            "copies",
            "subscription_product",
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
