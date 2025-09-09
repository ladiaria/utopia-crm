from django.utils.translation import gettext_lazy as _
from django import forms
from django.forms import ValidationError
from django.contrib.auth.models import User
from django.utils.safestring import mark_safe
from django.utils import timezone

from phonenumber_field.formfields import PhoneNumberField
from phonenumber_field.widgets import RegionalPhoneNumberWidget

from core.models import (
    Contact,
    Product,
    Subscription,
    Address,
    DynamicContactFilter,
    SubscriptionProduct,
    Activity,
    State,
    IdDocumentType,
    regex_alphanumeric_msg,
)
from core.forms import EmailValidationForm
from core.choices import ADDRESS_TYPE_CHOICES, ACTIVITY_TYPES
from core.signals import alphanumeric

from .models import Seller, Issue, IssueStatus, IssueSubcategory, SalesRecord
from .choices import get_issue_categories


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
        widget=forms.DateTimeInput(attrs={"class": "datepicker form-control float-right", "autocomplete": "off"})
    )
    date_2 = forms.DateField(
        widget=forms.DateTimeInput(attrs={"class": "datepicker form-control float-right", "autocomplete": "off"})
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
                _("There must be at least 1 day difference between date 2 and 1. Date 1 must be smaller than date 2")
            )


class PartialPauseTaskForm(forms.Form):
    date_1 = forms.DateField(
        widget=forms.DateTimeInput(attrs={"class": "datepicker form-control float-right", "autocomplete": "off"}),
        label=_("Date of deactivation"),
    )
    date_2 = forms.DateField(
        widget=forms.DateTimeInput(attrs={"class": "datepicker form-control float-right", "autocomplete": "off"}),
        label=_("Date of activation (Products will be activated this exact day)"),
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
                _("There must be at least 1 day difference between date 2 and 1. Date 1 must be smaller than date 2")
            )


class NewAddressChangeScheduledTaskForm(forms.Form):
    date_1 = forms.DateField(
        widget=forms.DateTimeInput(attrs={"class": "datepicker form-control float-right", "autocomplete": "off"})
    )
    contact_address = forms.ModelChoiceField(
        Address.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    new_address = forms.BooleanField(
        label=_("New address"), required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
    new_address_1 = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    new_address_2 = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    new_address_city = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    new_address_state = forms.ModelChoiceField(
        queryset=State.objects.all(), required=False, widget=forms.Select(attrs={"class": "form-control"})
    )
    new_address_notes = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
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
    new_special_instructions = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))

    def clean(self):
        new_address = self.cleaned_data.get("new_address")
        new_address_1 = self.cleaned_data.get("new_address_1")
        new_address_city = self.cleaned_data.get("new_address_city")
        new_address_state = self.cleaned_data.get("new_address_state")
        contact_address = self.cleaned_data.get("contact_address")

        if not (new_address or contact_address):
            raise forms.ValidationError(_("Please select an existing address or create a new one."))

        if new_address and not (new_address_1 and new_address_city and new_address_state):
            raise forms.ValidationError(
                _("Please complete the new address first line, city and state if new address is selected")
            )


class NewPromoForm(EmailValidationForm):
    name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}), required=False)
    phone = PhoneNumberField(
        empty_value="",
        required=False,
        widget=RegionalPhoneNumberWidget(attrs={"class": "form-control"}),
    )
    mobile = PhoneNumberField(
        empty_value="",
        required=False,
        widget=RegionalPhoneNumberWidget(attrs={"class": "form-control"}),
    )
    notes = forms.CharField(
        empty_value=None, required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": "4"})
    )
    email = forms.EmailField(
        empty_value=None, required=False, widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    start_date = forms.DateField(
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "datepicker form-control", "autocomplete": "off"})
    )
    end_date = forms.DateField(
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "datepicker form-control", "autocomplete": "off"})
    )
    default_address = forms.ModelChoiceField(
        Address.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def clean(self):
        self.email_extra_clean(super().clean())


class NewSubscriptionForm(EmailValidationForm, forms.ModelForm):

    def __init__(self, *args, **kwargs):
        contact = kwargs.pop("contact")
        super().__init__(*args, **kwargs)
        if contact:
            self.fields["billing_address"].queryset = Address.objects.filter(contact=contact)

    class Meta:
        model = Subscription
        fields = (
            "contact",
            "name",
            "last_name",
            "phone",
            "mobile",
            "notes",
            "email",
            "id_document_type",
            "id_document",
            "frequency",
            "payment_type",
            "start_date",
            "end_date",
            "billing_address",
            "billing_name",
            "billing_phone",
            "billing_email",
            "default_address",
            "send_bill_copy_by_email",
            "billing_id_doc",
            "rut",
        )
        widgets = {
            "contact": forms.HiddenInput(),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "mobile": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": "4"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "id_document": forms.TextInput(attrs={"class": "form-control"}),
            "frequency": forms.Select(attrs={"class": "form-control"}),
            "payment_type": forms.Select(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"class": "datepicker form-control", "autocomplete": "off"},
            ),
            "end_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"class": "datepicker form-control", "autocomplete": "off"},
            ),
            "billing_address": forms.Select(attrs={"class": "form-control"}),
            "billing_name": forms.TextInput(attrs={"class": "form-control"}),
            "billing_id_doc": forms.TextInput(attrs={"class": "form-control"}),
            "rut": forms.TextInput(attrs={"class": "form-control"}),
            "billing_phone": forms.TextInput(attrs={"class": "form-control"}),
            "billing_email": forms.TextInput(attrs={"class": "form-control"}),
            "default_address": forms.Select(attrs={"class": "form-control"}),
            "send_bill_copy_by_email": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

        labels = {
            "name": _("Name"),
            "last_name": _("Last name"),
            "phone": _("Phone"),
            "mobile": _("Mobile"),
            "notes": _("Notes"),
            "email": _("Email"),
            "id_document": _("ID Document"),
            "frequency": _("Frequency"),
            "payment_type": _("Payment type"),
            "start_date": _("Start date"),
            "end_date": _("End date"),
            "billing_address": _("Billing address"),
            "billing_name": _("Billing name"),
            "rut": _("Unique Taxpayer ID"),
            "billing_id_doc": _("Billing ID Document"),
            "billing_phone": _("Billing phone"),
            "billing_email": _("Billing email"),
            "default_address": _("Default address"),
            "send_bill_copy_by_email": _("Send bill copy by email"),
        }

    name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}), label="Nombre")
    last_name = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}), label="Apellido", required=False
    )
    phone = PhoneNumberField(
        empty_value="", widget=RegionalPhoneNumberWidget(attrs={"class": "form-control"}), label="Teléfono"
    )
    mobile = PhoneNumberField(
        empty_value="",
        required=False,
        widget=RegionalPhoneNumberWidget(attrs={"class": "form-control"}),
        label="Celular",
    )
    notes = forms.CharField(
        empty_value=None,
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": "4"}),
        label="Observaciones",
    )
    register_activity = forms.CharField(
        empty_value=None,
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": "1"}),
        label="Registrar actividad",
    )
    email = forms.EmailField(
        empty_value=None,
        required=False,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
        label="Correo electrónico",
    )
    id_document_type = forms.ModelChoiceField(
        required=False,
        queryset=IdDocumentType.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Tipo de documento",
    )
    id_document = forms.CharField(
        empty_value=None,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Documento de identidad",
    )
    default_address = forms.ModelChoiceField(
        Address.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Aplicar dirección a todos los productos. Podrás cambiarlas una por una luego.",
    )
    send_bill_copy_by_email = forms.BooleanField(
        label="Enviar factura por correo electrónico",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean_name(self):
        data = self.cleaned_data["name"].strip()
        if not alphanumeric.match(data):
            raise ValidationError(regex_alphanumeric_msg)
        return data

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            email = email.lower()
        return email

    def clean(self):
        cleaned_data = super().clean()
        email = self.email_extra_clean(cleaned_data)
        if email:
            contact_id, id_document = cleaned_data["contact"].id, cleaned_data["id_document"]

            if Contact.objects.filter(email=email).exclude(id=contact_id).exists():
                c = Contact.objects.filter(email=email).exclude(id=contact_id).first()
                url = f'<a href="{c.get_absolute_url()}" target="_blank">Abrir en otra pestaña</a>'
                raise ValidationError(mark_safe(f"Este email ya existe en otro contacto (id: {c.id}). {url}"))

            if id_document and Contact.objects.filter(id_document=id_document).exclude(id=contact_id).exists():
                c = Contact.objects.filter(id_document=id_document).exclude(id=contact_id).first()
                url = f'<a href="{c.get_absolute_url()}" target="_blank">Abrir en otra pestaña</a>'
                raise ValidationError(
                    mark_safe(f"Este documento de identidad ya existe en otro contacto (id: {c.id}). {url}")
                )


class IssueStartForm(forms.ModelForm):
    """
    Used when you want to start an issue to track logistics, what used to be 'Claims
    """

    contact = forms.ModelChoiceField(
        queryset=Contact.objects,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    widget = forms.Select(attrs={"class": "form-control"})
    # TODO: explain or remove the following commented line
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
    sub_category = forms.ModelChoiceField(
        label=_("Sub Category (Required)"),
        queryset=IssueSubcategory.objects.all(),
        widget=forms.Select(attrs={"class": "form-control", "autocomplete": "off"}),
    )
    activity_type = forms.ChoiceField(
        widget=forms.Select(attrs={"class": "form-control"}),
        choices=ACTIVITY_TYPES,
    )
    status = forms.ModelChoiceField(
        required=False, queryset=IssueStatus.objects.all(), widget=forms.Select(attrs={"class": "form-control"})
    )
    assigned_to = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.filter(is_staff=True).order_by('username'),
        widget=forms.Select(attrs={"class": "form-control", "autocomplete": "off"}),
    )
    contact_address = forms.ModelChoiceField(
        Address.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    new_address = forms.BooleanField(
        label=_("New address"), required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
    new_address_1 = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    new_address_2 = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    new_address_city = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    new_address_state = forms.ModelChoiceField(
        queryset=State.objects.all(), required=False, widget=forms.Select(attrs={"class": "form-control"})
    )
    new_address_notes = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    new_address_type = forms.ChoiceField(
        required=False,
        choices=ADDRESS_TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def clean(self):
        dict_categories = dict(get_issue_categories())
        category = self.cleaned_data.get("category")
        sub_category = self.cleaned_data.get("sub_category")
        if sub_category.category == "I" and category == "M":
            pass
        elif sub_category.category and sub_category.category != category:
            msg = _("{} is not a subcategory of {}").format(sub_category, dict_categories[category])
            self.add_error("sub_category", forms.ValidationError(msg))

        return self.cleaned_data

    class Meta:
        model = Issue
        widgets = {
            "notes": forms.Textarea(attrs={"class": "form-control"}),
            "subscription_product": forms.Select(attrs={"class": "form-control"}),
            "subscription": forms.Select(attrs={"class": "form-control"}),
            "category": forms.HiddenInput(attrs={"class": "form-control"}),
            "copies": forms.NumberInput(attrs={"class": "form-control"}),
            "envelope": forms.CheckboxInput(attrs={"class": "form-check-input"}),
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
            "envelope",
        )


class IssueChangeForm(forms.ModelForm):
    """
    Used when you want to start an issue to track logistics, what used to be 'Claims'
    """

    sub_category = forms.ModelChoiceField(
        required=False, queryset=IssueSubcategory.objects.all(), widget=forms.Select(attrs={"class": "form-control"})
    )
    contact = forms.ModelChoiceField(queryset=Contact.objects, widget=forms.TextInput)
    next_action_date = forms.DateField(
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "datepicker form-control", "autocomplete": "off"}),
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
            "envelope": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "copies": forms.TextInput(attrs={"class": "form-control"}),
        }
        fields = (
            "contact",
            "sub_category",
            "status",
            "progress",
            "answer_1",
            "answer_2",
            "next_action_date",
            "assigned_to",
            "envelope",
            "copies",
        )


class InvoicingIssueChangeForm(forms.ModelForm):
    """
    Used when you want to start an issue to track logistics, what used to be 'Claims'
    """

    sub_category = forms.ModelChoiceField(
        required=False,
        queryset=IssueSubcategory.objects.filter(category='I'),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    contact = forms.ModelChoiceField(queryset=Contact.objects, widget=forms.TextInput)
    next_action_date = forms.DateField(
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "datepicker form-control", "autocomplete": "off"}),
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
            "envelope": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        fields = (
            "contact",
            "sub_category",
            "status",
            "progress",
            "answer_1",
            "answer_2",
            "next_action_date",
            "assigned_to",
            "envelope",
        )


SELECT_CONTACT_FOR_ISSUE_TYPE_CHOICES = (
    ("L", _("Logistics")),
    ("S04", _("Pause")),
    ("S05", _("Change address")),
)


class NewAddressForm(forms.Form):
    address_1 = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    address_2 = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    address_city = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    address_state = forms.ModelChoiceField(
        queryset=State.objects.all(), required=False, widget=forms.Select(attrs={"class": "form-control"})
    )
    address_notes = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
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
            "debtor_contacts": forms.Select(attrs={"class": "form-control"}),
            "mailtrain_id": forms.TextInput(attrs={"class": "form-control"}),
        }
        fields = (
            "description",
            "products",
            "newsletters",
            "allow_promotions",
            "allow_polls",
            "debtor_contacts",
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


class CreateActivityForm(forms.ModelForm):
    datetime = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}), input_formats=['%Y-%m-%dT%H:%M'], label=_("Date")
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["datetime"].required = True
        self.fields["activity_type"].required = True
        self.fields["datetime"].initial = timezone.now().strftime("%Y-%m-%dT%H:%M")
        self.fields["status"].initial = "C"
        self.fields["direction"].initial = "I"
        self.fields["topic"].required = False
        self.fields["response"].required = False

    class Meta:
        model = Activity
        fields = [
            "contact",
            "topic",
            "response",
            "direction",
            "datetime",
            "notes",
            "activity_type",
            "status",
        ]
        widgets = {
            "contact": forms.HiddenInput(),
            "status": forms.HiddenInput(),
        }


class UnsubscriptionForm(forms.ModelForm):
    end_date = forms.DateField(
        required=True,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "datepicker form-control", "autocomplete": "off"}),
    )

    class Meta:
        model = Subscription
        fields = (
            "end_date",
            "unsubscription_type",
            "unsubscription_channel",
            "unsubscription_reason",
            "unsubscription_addendum",
        )
        widgets = {
            "unsubscription_type": forms.Select(attrs={"class": "form-control"}),
            "unsubscription_channel": forms.Select(attrs={"class": "form-control"}),
            "unsubscription_reason": forms.Select(attrs={"class": "form-control"}),
            "unsubscription_addendum": forms.Textarea(attrs={"class": "form-control"}),
        }


class AdditionalProductForm(forms.ModelForm):
    end_date = forms.DateField(
        required=True,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "datepicker form-control", "autocomplete": "off"}),
    )

    class Meta:
        model = Subscription
        fields = (
            "end_date",
            "unsubscription_addendum",
        )
        widgets = {
            "unsubscription_addendum": forms.Textarea(attrs={"class": "form-control"}),
        }


class ContactCampaignStatusByDateForm(forms.Form):
    date_gte = forms.DateField(
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "datepicker form-control", "autocomplete": "off"}),
    )
    date_lte = forms.DateField(
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "datepicker form-control", "autocomplete": "off"}),
    )


class SubscriptionPaymentCertificateForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = ("payment_certificate",)


class AddressComplementaryInformationForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ("picture", "google_maps_url")


class SugerenciaGeorefForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            "contact",
            "address_1",
            "address_2",
            "city",
            "state",
            "state_georef_id",
            "city_georef_id",
            "latitude",
            "longitude",
            "verified",
            "address_type",
        ]


class ValidateSubscriptionForm(forms.ModelForm):
    override_commission_value = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": _("Override amount"), "min": 0}),
    )
    seller = forms.ModelChoiceField(
        queryset=Seller.objects.filter(internal=True),
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = SalesRecord
        fields = ("can_be_commissioned", "override_commission_value", "seller")
        widgets = {
            "can_be_commissioned": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class SalesRecordCreateForm(forms.ModelForm):
    override_commission_value = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": _("Override amount"), "min": 0}),
    )

    class Meta:
        model = SalesRecord
        fields = ("total_commission_value", "can_be_commissioned", "seller", "subscription")
        widgets = {
            "can_be_commissioned": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "subscription": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        subscription = kwargs.pop('subscription', None)
        super().__init__(*args, **kwargs)
        self.fields['seller'].queryset = Seller.objects.filter(internal=True)
        # Use subscription_id to initialize fields or set initial values
        if subscription:
            # Assuming you have a field named 'subscription' to hold the subscription_id
            self.fields['subscription'].initial = subscription


class CorporateSubscriptionForm(NewSubscriptionForm):
    class Meta(NewSubscriptionForm.Meta):
        fields = NewSubscriptionForm.Meta.fields + ('number_of_subscriptions', 'override_price')


class AffiliateSubscriptionForm(forms.Form):
    contact = forms.ModelChoiceField(queryset=Contact.objects.all())
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contact'].queryset = self.fields['contact'].queryset.order_by('name')


class ImportContactsForm(forms.Form):
    file = forms.FileField(
        label='CSV File', help_text='Please upload a CSV file', widget=forms.FileInput(attrs={'accept': '.csv'})
    )
    tags = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Comma-separated tags', 'class': 'form-control'})
    )
    tags_existing = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Tags for existing contacts', 'class': 'form-control'}),
    )
    tags_active = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Tags for active contacts', 'class': 'form-control'}),
    )
    tags_in_campaign = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Tags for contacts in campaign', 'class': 'form-control'}),
    )


class CheckForExistingContactsForm(forms.Form):
    file = forms.FileField(
        label=_('CSV File'), help_text=_('Please upload a CSV file'), widget=forms.FileInput(attrs={'accept': '.csv'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].widget.attrs['class'] = 'form-control'
        self.fields['file'].widget.attrs['accept'] = '.csv'
        self.fields['file'].widget.attrs['placeholder'] = _('Upload CSV file')
        self.fields['file'].widget.attrs['required'] = True

    def clean_file(self):
        file = self.cleaned_data['file']
        if not file.name.endswith('.csv'):
            raise forms.ValidationError(_('File must be a CSV file'))
        return file
