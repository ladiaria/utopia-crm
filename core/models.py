# coding=utf-8
from __future__ import unicode_literals
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from django.contrib.auth.models import User
from django.conf import settings
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q, Sum, Count
from django.forms import ValidationError
from django.utils.text import format_lazy
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.fields import AutoSlugField
from django.utils.html import mark_safe

from taggit.managers import TaggableManager

from .choices import *
from utils import (
    delete_email_from_mailtrain_list,
    subscribe_email_to_mailtrain_list,
    get_emails_from_mailtrain_list,
)
from util.dates import get_default_next_billing, get_default_start_date, diff_month


regex_alphanumeric = u"^[@A-Za-z0-9ñüáéíóúÑÜÁÉÍÓÚ _'.\-]*$"
regex_alphanumeric_msg = _(
    "This name only supports alphanumeric characters, at, apostrophes, spaces, hyphens, underscores, and periods."
)

alphanumeric = RegexValidator(regex_alphanumeric, regex_alphanumeric_msg)

min_month = MinValueValidator(1, _("Month can't be less than 1"))
max_month = MaxValueValidator(12, _("Month can't be more than 12"))
min_year = MinValueValidator(
    datetime.now().year,
    _("Year is not valid, minimum value is %s" % datetime.now().year),
)


class Institution(models.Model):
    """
    If the contact comes from an institution. This holds the institutions.
    """

    name = models.CharField(max_length=255, verbose_name=_("Name"))
    old_pk = models.PositiveIntegerField(blank=True, null=True, db_index=True)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = _("institution")
        verbose_name_plural = _("institutions")
        ordering = ("name",)


class Ocupation(models.Model):
    """
    Model containing the possible ocupations for a contact.
    """

    code = models.CharField(max_length=3, primary_key=True, verbose_name=_("Code"))
    name = models.CharField(max_length=128, verbose_name=_("Name"))

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ("code",)
        verbose_name = _("ocupation")
        verbose_name_plural = _("ocupations")


class Subtype(models.Model):
    """
    Holds the origin of a contact. Probably will be deprecated soon and will be totally replaced by tags.
    """

    name = models.CharField(max_length=255, verbose_name=_("name"))
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    old_pk = models.PositiveIntegerField(blank=True, null=True, db_index=True)

    def get_contact_count(self):
        return self.contact_set.all().count()

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = _("subtype")
        verbose_name_plural = _("subtypes")
        ordering = ("name",)


class Variable(models.Model):
    """
    Different variables that need to be stored in database. They usually work like settings but in a dynamic way.
    """

    name = models.CharField(max_length=255, verbose_name=_("name"))
    value = models.CharField(max_length=255, verbose_name=_("value"))
    type = models.CharField(
        max_length=255, blank=True, choices=VARIABLE_TYPES, verbose_name=_("type")
    )

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = _("variable")
        verbose_name_plural = _("variables")
        ordering = ("name",)


class Product(models.Model):
    """
    Products that a subscription can have. By default they can be subscription products or newsletters.

    Products MUST have a billing priority to be billed.
    """

    name = models.CharField(max_length=50, verbose_name=_("Name"), db_index=True)
    slug = AutoSlugField(populate_from="name", null=True, blank=True)
    active = models.BooleanField(default=False, verbose_name=_("Active"))
    price = models.IntegerField(default=0)
    type = models.CharField(max_length=1, default="O", choices=PRODUCT_TYPE_CHOICES, db_index=True)
    weekday = models.IntegerField(default=None, choices=PRODUCT_WEEKDAYS, null=True, blank=True)
    offerable = models.BooleanField(default=False, verbose_name=_("Allow offer"))
    billing_priority = models.PositiveSmallIntegerField(null=True, blank=True)
    digital = models.BooleanField(default=False, verbose_name=_("Digital"))
    old_pk = models.PositiveIntegerField(blank=True, null=True)

    def __unicode__(self):
        name = self.name
        if self.type == "N":
            name += ", newsletter"
        return "%s" % name

    def get_type(self):
        """
        Returns the type of product
        """
        types = dict(PRODUCT_TYPE_CHOICES)
        return types.get(self.type, "N/A")

    def get_weekday(self):
        """
        Returns the weekday of the product. Used only for products that are bound to a specific day.
        """
        weekdays = dict(PRODUCT_WEEKDAYS)
        return weekdays.get(self.weekday, "N/A")

    class Meta:
        verbose_name = _("product")
        verbose_name_plural = _("products")
        ordering = ("id",)


class Contact(models.Model):
    """
    Holds people personal information
    """

    subtype = models.ForeignKey(
        Subtype,
        blank=True,
        null=True,
        verbose_name=_("Subtype"),
        on_delete=models.SET_NULL,
    )
    referrer = models.ForeignKey(
        "self",
        related_name="referred",
        blank=True,
        null=True,
        verbose_name=_("Referrer"),
        on_delete=models.SET_NULL,
    )
    institution = models.ForeignKey(
        Institution,
        blank=True,
        null=True,
        verbose_name=_("Institution"),
        on_delete=models.SET_NULL,
    )
    name = models.CharField(max_length=100, validators=[alphanumeric], verbose_name=_("Name"))
    id_document = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Identifcation Document"))
    phone = models.CharField(max_length=20, verbose_name=_("Phone"))
    work_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Work phone"))
    mobile = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Mobile"))
    email = models.EmailField(blank=True, null=True, unique=True, verbose_name=_("Email"))
    no_email = models.BooleanField(default=False, verbose_name=_("No email"))
    gender = models.CharField(max_length=1, choices=GENDERS, blank=True, null=True, verbose_name=_("Gender"))
    ocupation = models.ForeignKey(
        Ocupation,
        blank=True,
        null=True,
        verbose_name=_("Ocupation"),
        on_delete=models.SET_NULL,
    )
    education = models.PositiveSmallIntegerField(
        blank=True, null=True, choices=EDUCATION_CHOICES, verbose_name=_("Education")
    )
    birthdate = models.DateField(blank=True, null=True, verbose_name=_("Birthdate"))
    private_birthdate = models.BooleanField(default=False, verbose_name=_("Private birthdate"))
    protected = models.BooleanField(default=False, blank=True, verbose_name=_("Protected"))
    protection_reason = models.TextField(blank=True, null=True, verbose_name=_("Protection reason"))
    notes = models.TextField(blank=True, null=True, verbose_name=_("Notes"))
    tags = TaggableManager(blank=True)
    allow_polls = models.BooleanField(default=True, verbose_name=_("Allows polls"))
    allow_promotions = models.BooleanField(default=True, verbose_name=_("Allows promotions"))

    def __unicode__(self):
        return self.name

    def clean(self):
        if (
            getattr(settings, "WEB_UPDATE_USER_ENABLED", False)
            and self.email
            and self.id
        ):
            custom_module = getattr(settings, "WEB_UPDATE_USER_VALIDATION_MODULE", None)
            if custom_module:
                validateEmailOnWeb_func = __import__(
                    custom_module, fromlist=["validateEmailOnWeb"]
                ).validateEmailOnWeb
                msg = validateEmailOnWeb_func(self.id, self.email)
                if msg == "TIMEOUT":
                    # TODO: Alert user about web timeout
                    pass
                elif msg != "OK":
                    raise ValidationError({"email": msg})

    def save(self, *args, **kwargs):
        if not getattr(self, "updatefromweb", False):
            self.clean()
        return super(Contact, self).save(*args, **kwargs)

    def is_debtor(self):
        """
        Checks if the contact has expired invoices, returns True or False
        """
        return bool(self.expired_invoices_count())

    def get_expired_invoices(self):
        """
        Returns a queryset with the expired invoices for the contact.
        """
        return self.invoice_set.filter(
            expiration_date__lte=date.today(),
            paid=False,
            debited=False,
            canceled=False,
            uncollectible=False,
        )

    def expired_invoices_count(self):
        """
        Counts the amount of expired invoices for the contact.
        """
        return self.get_expired_invoices().count()

    def get_total_invoices_count(self):
        return self.invoice_set.all().count()

    def get_paid_invoices_count(self):
        return self.invoice_set.filter(Q(paid=True) | Q(debited=True)).count()

    def get_latest_invoice(self):
        if self.invoice_set.exists():
            return self.invoice_set.all().latest("id")
        else:
            return None

    def add_to_campaign(self, campaign_id):
        """
        Adds a contact to a campaign. If the contact is already in that campaign this will raise an exception.
        """
        campaign = Campaign.objects.get(pk=campaign_id)
        if not ContactCampaignStatus.objects.filter(
            contact=self, campaign=campaign
        ).exists():
            # We first create the big object that will hold the status for the campaign
            ContactCampaignStatus.objects.create(contact=self, campaign=campaign)
            return _("Contact %s (ID: %s) added to campaign") % (self.name, self.id)
        else:
            raise Exception(
                _("Contact %s (ID: %s) already in campaign") % (self.name, self.id)
            )

    def has_active_subscription(self, count=False):
        """
        Checks if the contact has any active subscription. If count is passed through this, it will instead return
        how many of these they have.
        """
        subs = self.subscriptions.filter(active=True)
        return subs.exists() if count is False else subs.count()

    def get_debt(self):
        """
        Returns how much money the contact owes.
        """
        sum_import = self.invoice_set.filter(
            expiration_date__lte=date.today(),
            paid=False,
            debited=False,
            canceled=False,
            uncollectible=False,
        ).aggregate(Sum("amount"))
        return sum_import.get("amount__sum", None)

    def has_no_open_issues(self, category=None):
        """
        Checks if all the issues for this contact are finalized, based off the finished issue status slug list on
        the settings. Use any statuses you like to be used as an issue finisher.
        """
        if category:
            return (
                self.issue_set.filter(
                    status__slug__in=settings.FINISHED_ISSUE_STATUS_SLUG_LIST,
                    category=category,
                ).count()
                == self.issue_set.filter(category=category).count()
            )
        else:
            return (
                self.issue_set.filter(
                    status__slug__in=settings.FINISHED_ISSUE_STATUS_SLUG_LIST
                ).count()
                == self.issue_set.all().count()
            )

    def get_subscriptions(self):
        """
        Returns a queryset with the subscriptions of this contact.
        """
        return self.subscriptions.all()

    def get_active_subscriptions(self):
        return self.subscriptions.filter(active=True)

    def get_active_subscriptionproducts(self):
        return SubscriptionProduct.objects.filter(
            subscription__active=True, subscription__contact=self
        )

    def get_subscriptions_with_expired_invoices(self):
        """
        Returns a list with the distinct subscriptions that have expired invoices
        """
        subscriptions = []
        for invoice in self.get_expired_invoices():
            for invoice_item in invoice.invoiceitem_set.all():
                if (
                    invoice_item.subscription
                    and invoice_item.subscription not in subscriptions
                ):
                    subscriptions.append(invoice_item.subscription)
        return subscriptions

    def get_first_active_subscription(self):
        """
        Returns the first active subscription by id
        """
        if self.has_active_subscription():
            return self.subscriptions.filter(active=True)[0]
        else:
            return None

    def last_activity(self):
        """
        Returns the latest activity of this contact.
        """
        if self.activity_set.exists():
            return self.activity_set.latest("id")
        else:
            return None

    def get_gender(self):
        """
        Gets the description of the gender (Male, Female, Other)
        """
        genders = dict(GENDERS)
        return genders.get(self.gender, "N/A")

    def add_newsletter(self, newsletter_id):
        try:
            newsletter = Product.objects.get(id=newsletter_id, type="N")
        except Exception:
            raise _("Invalid product id")
        SubscriptionNewsletter.objects.get_or_create(
            contact=self, product=newsletter, active=True
        )

    def remove_newsletter(self, newsletter_id):
        try:
            newsletter = Product.objects.get(id=newsletter_id, type="N")
        except Exception:
            raise _("Invalid product id")
        try:
            SubscriptionNewsletter.objects.get(contact=self, product=newsletter).delete()
        except SubscriptionNewsletter.DoesNotExist:
            pass

    def has_newsletter(self, newsletter_id):
        return SubscriptionNewsletter.objects.filter(contact=self, product_id=newsletter_id, active=True).exists()

    def get_newsletters(self):
        """
        Returns a queryset with all the newsletters that this contact has subscriptions in.
        """
        return SubscriptionNewsletter.objects.filter(contact=self)

    def get_newsletter_products(self):
        return Product.objects.filter(type='N', subscriptionnewsletter__contact=self)

    def get_last_paid_invoice(self):
        """
        Returns the last paid invoice for this contact if it exists. Returns None if they have none.
        """
        try:
            return self.invoice_set.filter(Q(paid=True) | Q(debited=True)).latest("id")
        except Exception:
            return None

    def add_product_history(
        self,
        subscription,
        product,
        new_status,
        campaign=None,
        seller=None,
        override_date=None,
    ):
        """
        Adds a product history for this contact on the ContactProductHistory table. This is used to keep record of
        how many times a Contact has been active or inactive, and when. Soon this will be improved.
        """
        # TODO: this method should be migrated to the Subscription model

        history_of_this_product = subscription.contactproducthistory_set.filter(
            product=product
        )

        if history_of_this_product.exists():
            latest_history_of_this_product = history_of_this_product.latest("id")
        else:
            latest_history_of_this_product = None

        if latest_history_of_this_product:
            if latest_history_of_this_product.status == new_status:
                # if this is the same event, we will do nothing
                pass
            else:
                # if this is a different event, then we will activate or deactivate accordingly
                ContactProductHistory.objects.create(
                    contact=self,
                    subscription=subscription,
                    date=override_date or date.today(),
                    product=product,
                    status=new_status,
                    seller=seller,
                )
        else:
            ContactProductHistory.objects.create(
                contact=self,
                subscription=subscription,
                date=override_date or date.today(),
                product=product,
                status=new_status,
                seller=seller,
            )

    def get_total_issues_count(self):
        return self.issue_set.all().count()

    def get_finished_issues_count(self):
        return self.issue_set.filter(
            status__slug__in=settings.FINISHED_ISSUE_STATUS_SLUG_LIST
        ).count()

    def get_open_issues_count(self):
        return self.get_total_issues_count() - self.get_finished_issues_count()

    def get_open_issues_by_subcategory_count(self, subcategory):
        return self.issue_set.filter(subcategory=subcategory).exclude(
            status__slug__in=settings.FINISHED_ISSUE_STATUS_SLUG_LIST).count()

    def get_finished_issues_by_subcategory_count(self, subcategory):
        return self.issue_set.filter(subcategory=subcategory).exclude(
            status__slug__in=settings.FINISHED_ISSUE_STATUS_SLUG_LIST).count()

    def get_total_scheduledtask_count(self):
        return self.scheduledtask_set.count()

    def get_total_activities_count(self):
        return self.activity_set.count()

    class Meta:
        verbose_name = _("contact")
        verbose_name_plural = _("contacts")
        ordering = ("-id",)


class Address(models.Model):
    """
    Model that contains all the addresses for each contact. They're reused throughout the subscriptions,
    issues, and more models. This uses settings.
    """

    contact = models.ForeignKey(
        Contact,
        blank=True,
        null=True,
        verbose_name=_("Contact"),
        related_name="addresses",
    )
    address_1 = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("Address 1")
    )
    address_2 = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("Address 2")
    )
    city = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        default=getattr(settings, "DEFAULT_CITY", None),
        verbose_name=_("City"),
    )
    state = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        default=getattr(settings, "DEFAULT_STATE", None),
        verbose_name=_("State"),
    )
    if getattr(settings, "USE_STATES_CHOICE"):
        state.choices = settings.STATES
    email = models.EmailField(blank=True, null=True, verbose_name=_("Email"))
    address_type = models.CharField(
        max_length=50, choices=ADDRESS_TYPE_CHOICES, verbose_name=_("Address type")
    )
    notes = models.TextField(blank=True, null=True, verbose_name=_("Notes"))
    default = models.BooleanField(default=False, verbose_name=_("Default"))
    geo_ref_address = models.ForeignKey(
        "logistics.GeorefAddress",
        blank=True,
        null=True,
        verbose_name=_("GeorefAddress"),
    )

    # TODO: validate there is only one default address per contact

    def __unicode__(self):
        return "%s %s %s %s" % (
            self.address_1,
            self.address_2 or "",
            self.city or "",
            self.state or "",
        )

    def get_type(self):
        """
        Returns the type of the address.
        """
        types = dict(ADDRESS_TYPE_CHOICES)
        return types.get(self.address_type, "N/A")

    class Meta:
        verbose_name = _("address")
        verbose_name_plural = _("addresses")


class SubscriptionProduct(models.Model):
    """
    Contains a single product of type 'S' (subscription) inside of a subscription for a single contact.
    This allows contacts to have more than one product with its respective amount of copies, address where the product
    is delivered, and route/order.
    """

    product = models.ForeignKey("core.Product")
    subscription = models.ForeignKey("core.Subscription")
    copies = models.PositiveSmallIntegerField(default=1)
    address = models.ForeignKey("core.Address", blank=True, null=True, on_delete=models.SET_NULL)
    route = models.ForeignKey(
        "logistics.Route",
        blank=True,
        null=True,
        verbose_name=_("Route"),
        on_delete=models.SET_NULL,
    )
    order = models.PositiveSmallIntegerField(verbose_name=_("Order"), blank=True, null=True)
    label_message = models.CharField(max_length=40, blank=True, null=True)
    special_instructions = models.TextField(blank=True, null=True)
    label_contact = models.ForeignKey("core.contact", blank=True, null=True, on_delete=models.SET_NULL)
    seller = models.ForeignKey("support.Seller", blank=True, null=True, on_delete=models.SET_NULL)
    has_envelope = models.PositiveSmallIntegerField(
        blank=True, null=True, verbose_name=_("Envelope"), choices=ENVELOPE_CHOICES
    )

    def __unicode__(self):
        # TODO: result translation (i18n)
        if self.address:
            address = self.address.address_1
        else:
            address = u""

        return u"{} - {} - (Suscripción de ${})".format(
            self.product, address, self.subscription.get_price_for_full_period()
        )


class SubscriptionNewsletter(models.Model):
    """
    Similar to SubscriptionProduct, this contains a single product of type 'N' (newsletter) for a single contact, but
    inside of the same contact. So one contact can only have one set of newsletters which they will receive.
    """

    product = models.ForeignKey("core.Product", limit_choices_to={"type": "N"})
    contact = models.ForeignKey("core.Contact")
    active = models.BooleanField(default=True)


class Subscription(models.Model):
    """
    Model that holds a contract in which the contact will be able to receive one or more products (see
    SubscriptionProduct). This will allow you to bill the contact for this service (invoicing app) if the subscription
    has a paid type.
    """

    campaign = models.ForeignKey(
        "core.Campaign",
        blank=True,
        null=True,
        verbose_name=_("Campaign"),
        on_delete=models.SET_NULL,
    )
    active = models.BooleanField(default=True, verbose_name=_("Active"))
    contact = models.ForeignKey(
        Contact, verbose_name=_("Contact"), related_name="subscriptions"
    )
    type = models.CharField(
        max_length=1, default="N", choices=SUBSCRIPTION_TYPE_CHOICES
    )
    status = models.CharField(
        max_length=2, blank=True, null=True, choices=SUBSCRIPTION_STATUS_CHOICES
    )

    # Billing information. This is added in case it's necessary.
    billing_name = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Billing name")
    )
    billing_id_doc = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Billing Identification Document"),
    )
    rut = models.CharField(
        max_length=12, blank=True, null=True, verbose_name=_("R.U.T.")
    )
    billing_phone = models.CharField(
        max_length=20, blank=True, null=True, verbose_name=_("Billing phone")
    )
    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_("Balance"),
    )
    send_bill_copy_by_email = models.BooleanField(
        default=False, verbose_name=_("Send bill copy by email")
    )
    billing_address = models.ForeignKey(
        Address,
        blank=True,
        null=True,
        verbose_name=_("Billing address"),
        related_name="billing_contacts",
        on_delete=models.SET_NULL,
    )
    billing_email = models.EmailField(
        blank=True, null=True, verbose_name=_("Billing email")
    )

    envelope = models.NullBooleanField(default=False, verbose_name=_("Envelope"))
    free_envelope = models.NullBooleanField(
        default=False, verbose_name=_("Free envelope")
    )
    re_routed = models.NullBooleanField(default=False, verbose_name=_("Rerouted"))

    start_date = models.DateField(
        blank=True,
        null=True,
        default=get_default_start_date,
        verbose_name=_("Start date"),
    )
    end_date = models.DateField(blank=True, null=True, verbose_name=_("End date"))
    next_billing = models.DateField(
        default=get_default_next_billing,
        blank=True,
        null=True,
        verbose_name=_("Next billing"),
    )
    resubscription_date = models.DateField(
        blank=True, null=True, verbose_name=_("Resubscription date")
    )

    highlight_in_listing = models.BooleanField(
        default=False, verbose_name=_("Highlight in listing")
    )
    send_pdf = models.BooleanField(default=False, verbose_name=_("Send pdf"))
    directions = models.TextField(blank=True, null=True, verbose_name=_("Directions"))
    inactivity_reason = models.IntegerField(
        choices=INACTIVITY_REASONS,
        blank=True,
        null=True,
        verbose_name=_("Inactivity reason"),
    )
    pickup_point = models.ForeignKey(
        "logistics.PickupPoint", blank=True, null=True, verbose_name=_("Pickup point")
    )
    label_message = models.CharField(
        max_length=40, blank=True, null=True, verbose_name=_("Label message")
    )

    # Unsubscription
    unsubscription_date = models.DateField(
        blank=True, null=True, verbose_name=_("Unsubscription date")
    )
    unsubscription_manager = models.ForeignKey(
        User,
        verbose_name=_("Unsubscription manager"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    unsubscription_reason = models.PositiveSmallIntegerField(
        choices=settings.UNSUBSCRIPTION_REASONS,
        blank=True,
        null=True,
        verbose_name=_("Unsubscription reason"),
    )
    unsubscription_addendum = models.TextField(
        blank=True, null=True, verbose_name=_("Unsubscription addendum")
    )

    # Product
    products = models.ManyToManyField(Product, through="SubscriptionProduct")
    frequency = models.PositiveSmallIntegerField(default=1, choices=FREQUENCY_CHOICES)
    payment_type = models.CharField(
        max_length=1,
        choices=settings.SUBSCRIPTION_PAYMENT_METHODS,
        null=True,
        blank=True,
        verbose_name=_("Payment type"),
    )

    updated_from = models.OneToOneField(
        'core.Subscription',
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    # Mercadopago tokens, and others
    card_id = models.CharField(max_length=13, blank=True, null=True)
    customer_id = models.CharField(max_length=24, blank=True, null=True)

    def __unicode__(self):
        return unicode(_("{} subscription for the contact {} {}").format(
            _("Active") if self.active else _("Inactive"),
            self.contact.name,
            "({})".format(self.get_price_for_full_period()) if self.type == 'N' else "",
        ))

    def get_product_count(self):
        """
        Returns the amount of products in this subscription
        """
        return self.products.count()

    def edit_products_field(self):
        """
        Simple function that shows a link to edit the current subscription under a list of products.
        It's used to reduce clutter in the admin panel, only showing a small amount of information.
        """
        text = '<table style="padding:5px;">'
        subscription_products = SubscriptionProduct.objects.filter(subscription=self)
        for sp in subscription_products:
            text += (
                '<tr style="padding:5px;"><td style="padding:5px;">{}</td><td style="padding:5px;">{} un.</td>'
                '<td style="padding:5px;">{}</td></tr>'.format(
                    sp.product.name, sp.copies, sp.address
                )
            )
        text += "</table>"
        text += (
            "<a href='/admin/core/subscription/{}/' target='_blank'>Edit</a>".format(
                self.id
            )
        )
        return mark_safe(text)

    edit_products_field.allow_tags = True
    edit_products_field.short_description = "Products"

    def add_product(
        self,
        product,
        address,
        copies=1,
        message=None,
        instructions=None,
        route=None,
        order=None,
        seller_id=None,
        override_date=None,
        label_contact=None,
    ):
        """
        Used to add products to the current subscription. It is encouraged to always use this method when you want
        to add a product to a subscription, so you always have control of what happens here. This also creates a
        product history with the current subscription, product, and date, with the type 'A' (Activation).
        """
        sp = SubscriptionProduct.objects.create(
            subscription=self,
            product=product,
            address=address,
            copies=copies,
            label_message=message or None,
            special_instructions=instructions or None,
            label_contact=label_contact,
            seller_id=seller_id,
        )
        self.contact.add_product_history(
            subscription=self,
            product=product,
            new_status="A",
            campaign=self.campaign,
            seller=sp.seller,
            override_date=override_date,
        )
        return sp

    def remove_product(self, product):
        """
        Used to remove products from the current subscription. It is encouraged to always use this method when you want
        to remove a product from a subscription, so you always have control of what happens here. This also creates a
        product history with the current subscription, product, and date, with the type 'D' (De-activation)
        """
        try:
            sp = SubscriptionProduct.objects.get(subscription=self, product=product)
            sp.delete()
        except SubscriptionProduct.DoesNotExist:
            pass
        else:
            self.contact.add_product_history(self, product, "D")

    def get_billing_name(self):
        """
        Gets the billing name for the contact. If it doesn't have one, then the contact's name is returned.
        Used primarily in invoicing.
        """
        if self.billing_name:
            return self.billing_name
        else:
            return self.contact.name

    def get_billing_phone(self):
        """
        Gets the billing phone for the contact. If it doesn't have one, then the contact's phone is returned.
        Used primarily in invoicing.
        """
        if self.billing_phone:
            return self.billing_phone
        else:
            return self.contact.phone

    def get_billing_document(self):
        """
        Gets the billing id_document for the contact. It chooses between rut, id_document and the contact_id_document
        in that order.
        Used primarily in invoicing.
        """
        if self.rut:
            return self.rut
        elif self.billing_id_doc:
            return self.billing_id_doc
        else:
            return self.contact.id_document

    def get_billing_address(self):
        """
        Gets the billing address for the contact. If there is none set, then it will return the first address.
        It will return None given the case there's no available address in any products of the subscription.
        Used primaily in invoicing.
        """
        if self.billing_address:
            return self.billing_address.address_1
        else:
            subscription_products = SubscriptionProduct.objects.filter(
                subscription=self
            )
            addresses = [sp.address for sp in subscription_products if sp.address]
            if not addresses:
                return None
            else:
                return addresses[0].address_1

    def get_billing_state(self):
        """
        Gets the billing state for the contact. If it doesn't have one, it will chose the contact's first address'
        state.
        Used primarily in invoicing.
        """
        if self.billing_address and self.billing_address.state:
            return self.billing_address.state
        else:
            sub_prods = SubscriptionProduct.objects.filter(subscription=self)
            addresses = [sp.address for sp in sub_prods]
            if addresses:
                return addresses[0].state
            else:
                return ""

    def get_billing_city(self):
        """
        Gets the billing city for the contact. If it doesn't have one, it will chose the contact's first address'
        city.
        Used primarily in invoicing.
        """
        if self.billing_address and self.billing_address.city:
            return self.billing_address.city
        else:
            sub_prods = SubscriptionProduct.objects.filter(subscription=self)
            addresses = [sp.address for sp in sub_prods]
            if addresses:
                return addresses[0].city
            else:
                return ""

    def get_first_product_by_priority(self):
        """
        Returns the first product by priority
        """
        products = self.products.filter(type="S").order_by("billing_priority")
        if products.exists():
            return products.first()
        else:
            return None

    def get_billing_data_by_priority(self):
        """
        This will order products by their billing_priority attribute, and billing data included in the first
        SubscriptionProduct that matches that priority will be returned in a dictionary. This is used to complete the
        billing information for when invoices are created.

        Used primarily in invoicing.
        """
        result = {}
        product = self.get_first_product_by_priority()
        if product:
            sp = self.subscriptionproduct_set.filter(product=product).first()
            if sp.address:
                result = {
                    "route": sp.route_id,
                    "order": sp.order,
                    "address": sp.address.address_1 or sp.subscription.contact.email,
                    "state": sp.address.state,
                    "city": sp.address.city,
                    "name": self.get_billing_name(),
                }
        if not result:
            if getattr(settings, "FORCE_DUMMY_MISSING_BILLING_DATA", False):
                result = {}
        return result

    def get_full_address_by_priority(self):
        for product in Product.objects.filter(type="S").order_by("billing_priority"):
            if self.subscriptionproduct_set.filter(
                subscription=self, product=product
            ).exists():
                sp = self.subscriptionproduct_set.filter(
                    subscription=self, product=product
                ).first()
                if sp.address:
                    return sp.address
        return None

    def get_address_by_priority(self):
        for product in Product.objects.filter(type="S").order_by("billing_priority"):
            if self.subscriptionproduct_set.filter(
                subscription=self, product=product
            ).exists():
                sp = self.subscriptionproduct_set.filter(
                    subscription=self, product=product
                ).first()
                if sp.address:
                    return sp.address.address_1
        return None

    def get_address_2_by_priority(self):
        for product in Product.objects.filter(type="S").order_by("billing_priority"):
            if self.subscriptionproduct_set.filter(
                subscription=self, product=product
            ).exists():
                sp = self.subscriptionproduct_set.filter(
                    subscription=self, product=product
                ).first()
                if sp.address:
                    return sp.address.address_2
        return None

    def get_frequency_discount(self):
        """
        Returns the amount discounted for when the subscription is more than one month. Requires these settings to be
        set on the local settings.
        """
        if self.frequency == 3:
            return getattr(settings, "DISCOUNT_3_MONTHS", 0)
        elif self.frequency == 6:
            return getattr(settings, "DISCOUNT_6_MONTHS", 0)
        elif self.frequency == 12:
            return getattr(settings, "DISCOUNT_12_MONTHS", 0)
        else:
            return 0

    def get_first_day_of_the_week(self):
        """
        Returns an integer representing the first weekday (based on isoweekday) on the products this subscription has.
        """
        if SubscriptionProduct.objects.filter(
            subscription=self, product__weekday=1
        ).exists():
            return 1
        elif SubscriptionProduct.objects.filter(
            subscription=self, product__weekday=2
        ).exists():
            return 2
        elif SubscriptionProduct.objects.filter(
            subscription=self, product__weekday=3
        ).exists():
            return 3
        elif SubscriptionProduct.objects.filter(
            subscription=self, product__weekday=4
        ).exists():
            return 4
        elif SubscriptionProduct.objects.filter(
            subscription=self, product__weekday=5
        ).exists():
            return 5
        else:
            return 6

    def get_invoiceitems(self):
        """
        Returns invoiceitems for each product
        """
        from invoicing.models import InvoiceItem

        invoiceitem_list = []
        # First we get all the product invoiceitems
        for product in self.products:  # TODO: SOLVE BUNDLED PRODUCTS!
            item = InvoiceItem()
            # Get the copies for this product, when used on with_copies
            item.copies = product[1]
            # Add the amount of frequency if necessary
            frequency_extra = (
                _(" {} months".format(self.frequency)) if self.frequency > 1 else ""
            )
            item.description = product[0].name + frequency_extra
            item.price = product[0].price * self.frequency
            item.amount = item.price * item.copies
            item.product = product[0]
            item.subscription = self
            # TODO: Service from, service to
            invoiceitem_list.append(item)

        # Next, we append all discount invoiceitems
        for discount in self.get_discounts():
            discount_item = InvoiceItem()
            # Add the amount of frequency if necessary
            frequency_extra = (
                _(" {} months".format(self.frequency)) if self.frequency > 1 else ""
            )
            discount_item.description = discount["description"] + frequency_extra
            discount_item.amount = discount["amount"] * self.frequency
            discount_item.type_dr = discount["type_dr"]
            discount_item.type = discount["type"]
            discount_item.subscription = self
            invoiceitem_list.append(discount_item)

        return invoiceitem_list

    def product_summary(self):
        """
        Takes each product for this subscription and returns a list with the copies for each.
        """
        # products = self.products.filter(type='S')  # TODO: explain the usage of this commented line or remove it
        from .utils import process_products

        subscription_products = SubscriptionProduct.objects.filter(subscription=self)
        dict_all_products = {}
        for sp in subscription_products:
            dict_all_products[str(sp.product.id)] = str(sp.copies)
        return process_products(dict_all_products)

    def render_product_summary(self):
        output = "<ul>"
        for product_id, copies in self.product_summary().items():
            product = Product.objects.get(pk=product_id)
            output += "<li>{}</li>".format(product.name)
        return output + "</ul>"

    def get_price_for_full_period(self):
        """
        Returns the price for a single period on this customer, taking a view from invoicing as aid.
        """
        from .utils import calc_price_from_products

        summary_of_products = self.product_summary()
        frequency = self.frequency
        price = calc_price_from_products(summary_of_products, frequency)
        return price

    def get_current_period(self):
        """
        Returns two values, one for the start and one for the end of the period that's going to be paid on this
        subscription.
        """
        if not self.next_billing:
            return None
        assert self.type == "N", _("Subscription must be normal to use this method")
        start = self.next_billing - relativedelta(months=self.frequency)
        end = self.next_billing
        return start, end

    def amount_already_paid_in_period(self):
        """
        Divides the price of one period between the amount of days (frequency) to get the price for one day of
        this subscription. Then multiplies the value of this single day by the amount of days that have passed since
        the start of the period, giving as a result the amount that the customer has already paid.

        This is useful to add that amount as a discount for the next subscription when selling a new subscription to
        the customer, in the case the new subscription price is greater than the old one.
        """
        assert self.type == "N", _("Subscription must be normal to use this method")
        period_start, period_end = self.get_current_period()
        price_per_day = (
            self.get_price_for_full_period() / (period_end - period_start).days
        )
        days_already_used = (date.today() - period_start).days
        amount = int(price_per_day * days_already_used)
        if amount > self.get_price_for_full_period():
            amount = self.get_price_for_full_period()
        if amount < 0:
            amount = 0
        return amount

    def amount_to_pay_in_period(self):
        """
        Divides the price of one period between the amount of days (frequency) to get the price for one day of
        this subscription. Then multiplies the value of this single day by the amount of days that have passed since
        the start of the period, giving as a result the amount that the customer has yet to pay.
        """
        assert self.type == "N", _("Subscription must be normal to use this method")
        period_start, period_end = self.get_current_period()
        price_per_day = (
            self.get_price_for_full_period() / (period_end - period_start).days
        )
        days_not_used = 30 * self.frequency - (date.today() - period_start).days
        return int(price_per_day * days_not_used)

    def render_weekdays(self):
        """
        Shows an asterisk depending on which weekdays the subscription has products in. This is used in logistics.
        """
        products = self.products.filter(type="S")
        response = "<table><tr>"
        if products.filter(weekday=1).exists():
            response += "<td>*</td>"
        else:
            response += "<td></td>"
        if products.filter(weekday=2).exists():
            response += "<td>*</td>"
        else:
            response += "<td></td>"
        if products.filter(weekday=3).exists():
            response += "<td>*</td>"
        else:
            response += "<td></td>"
        if products.filter(weekday=4).exists():
            response += "<td>*</td>"
        else:
            response += "<td></td>"
        if products.filter(weekday=5).exists():
            response += "<td>*</td>"
        else:
            response += "<td></td>"
        response += "</tr></table>"
        return response

    def has_monday(self):
        """
        Returns true if the subscription has a Monday product.
        """
        return self.products.filter(type="S", weekday=1).exists()

    def has_tuesday(self):
        """
        Returns true if the subscription has a Tuesday product.
        """
        return self.products.filter(type="S", weekday=2).exists()

    def has_wednesday(self):
        """
        Returns true if the subscription has a Wednesday product.
        """
        return self.products.filter(type="S", weekday=3).exists()

    def has_thursday(self):
        """
        Returns true if the subscription has a Thursday product.
        """
        return self.products.filter(type="S", weekday=4).exists()

    def has_friday(self):
        """
        Returns true if the subscription has a Friday product.
        """
        return self.products.filter(type="S", weekday=5).exists()

    def has_weekend(self):
        """
        Returns true if the subscription has a Weekend product.
        """
        return self.products.filter(type="S", weekday=10).exists()

    def has_no_open_issues(self, category=None):
        """
        Checks if all this subscription's issues are finished based off the finished issue status slug list on the
        settings. Use any statuses you like as issue finishers.
        """
        if category:
            return (
                self.issue_set.exclude(
                    status__slug__in=FINISHED_ISSUE_STATUS_SLUG_LIST, category=category
                ).count()
                == self.issue_set.all().count()
            )
        else:
            return (
                self.issue_set.exclude(
                    status__slug__in=FINISHED_ISSUE_STATUS_SLUG_LIST
                ).count()
                == self.issue_set.all().count()
            )

    def show_products_html(self, ul=False, br=True):
        """
        Renders all the products into a list of products.
        """
        output = ""
        if ul:
            output += "<ul>"
        for sp in SubscriptionProduct.objects.filter(
                subscription=self, product__offerable=True).order_by('product_id'):
            count = self.products.filter(offerable=True).count()
            if ul:
                if sp.label_contact:
                    output += "<li>{} ({})</li>".format(sp.product.name, sp.label_contact.name)
                else:
                    output += "<li>{}</li>".format(sp.product.name)
            else:
                if sp.label_contact:
                    output += "{} ({})".format(sp.product.name, sp.label_contact.name)
                else:
                    output += "{}".format(sp.product.name)
                if count > 1:
                    if br:
                        output += "<br>"
                    else:
                        output += "\n"
        if ul:
            output += "</ul>"
        return output

    def get_unsubscription_reason(self):
        """
        Returns the unsubscription reason.
        """
        unsubscription_reasons = dict(settings.UNSUBSCRIPTION_REASONS)
        return unsubscription_reasons.get(self.unsubscription_reason, "N/A")

    def get_payment_type(self):
        """
        Returns the payment type.
        """
        payment_types = dict(settings.SUBSCRIPTION_PAYMENT_METHODS)
        return payment_types.get(self.payment_type, "N/A")

    def get_status(self):
        """
        Returns the status.
        """
        states = dict(SUBSCRIPTION_STATUS_CHOICES)
        return states.get(self.status, "N/A")

    def get_type(self):
        """
        Returns the type.
        """
        types = dict(SUBSCRIPTION_TYPE_CHOICES)
        return types.get(self.type, "N/A")

    def get_frequency(self):
        """
        Returns the frequency.
        """
        frequencies = dict(FREQUENCY_CHOICES)
        return frequencies.get(self.frequency, "N/A")

    def get_copies_for_product(self, product_id):
        try:
            sp = SubscriptionProduct.objects.get(
                subscription=self, product_id=product_id
            )
            return sp.copies or 1
        except SubscriptionProduct.DoesNotExist:
            return 1

    def get_message_for_product(self, product_id):
        try:
            sp = SubscriptionProduct.objects.get(
                subscription=self, product_id=product_id
            )
            return sp.label_message or ""
        except SubscriptionProduct.DoesNotExist:
            return ""

    def get_address_for_product(self, product_id):
        try:
            sp = SubscriptionProduct.objects.get(
                subscription=self, product_id=product_id
            )
            return sp.address
        except SubscriptionProduct.DoesNotExist:
            return None

    def get_instructions_for_product(self, product_id):
        try:
            sp = SubscriptionProduct.objects.get(
                subscription=self, product_id=product_id
            )
            return sp.special_instructions or ""
        except SubscriptionProduct.DoesNotExist:
            return ""

    def months_in_invoices_with_product(self, product_slug):
        months = 0
        for invoice in self.invoice_set.filter(invoiceitem__product__slug=product_slug):
            m = diff_month(invoice.service_to, invoice.service_from)
            months += m
        return months

    def get_subscriptionproducts(self, without_discounts=False):
        qs = SubscriptionProduct.objects.filter(subscription=self).select_related('product')
        if without_discounts:
            qs = qs.exclude(product__type='D')
        return qs

    class Meta:
        verbose_name = _("subscription")
        verbose_name_plural = _("subscriptions")


class Campaign(models.Model):
    """
    Model that controls sales campaigns, in which sellers can call contacts to offer your product.
    """

    name = models.CharField(max_length=255, verbose_name=_("name"))
    active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.SET_NULL
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    priority = models.PositiveSmallIntegerField(
        default=1, blank=True, null=True, verbose_name=_("Priority")
    )
    days = models.PositiveSmallIntegerField(default=5, blank=True, null=True)

    def __unicode__(self):
        return self.name

    def get_activities_by_seller(self, seller, status=None, type=None, datetime=None):
        """
        Returns all the activities on this campaign, for a specific seller. Activities on a campaign imply that the
        contact has been scheduled to be called in the future.
        """
        acts = Activity.objects.filter(campaign=self, seller=seller).order_by('datetime')
        if status:
            acts = acts.filter(status__in=status)
        if type:
            acts = acts.filter(activity_type__in=type)
        if date:
            acts = acts.filter(datetime__lte=datetime)
        return acts

    def get_not_contacted(self, seller_id):
        """
        Returns the ContactCampaignStatus objects for all Contacts that have not been called yet (status=1)
        """
        return self.contactcampaignstatus_set.filter(seller_id=seller_id, status=1)

    def get_not_contacted_count(self, seller_id):
        """
        Returns the count of ContactCampaignStatus objects for all Contacts that have not been called yet (status=1)
        """
        return self.get_not_contacted(seller_id).count()

    def get_already_contacted(self, seller_id):
        """
        Returns the ContactCampaignStatus objects for all Contacts that have already been called yet (status=2, 3)
        """
        return self.contactcampaignstatus_set.filter(
            seller_id=seller_id, status__in=[2, 3]
        )

    def get_already_contacted_count(self, seller_id):
        """
        Returns the count of ContactCampaignStatus objects for all Contacts that have already been called yet
        (status=2, 3)
        """
        return self.get_already_contacted(seller_id).count()

    def get_successful_count(self, seller_id):
        return self.contactcampaignstatus_set.filter(
            seller_id=seller_id, campaign_resolution__in=['S1', 'S2']
        ).count()

    class Meta:
        verbose_name = _("campaign")
        verbose_name_plural = _("campaigns")
        ordering = ("name",)


class Activity(models.Model):
    """
    Model that stores every interaction the company has with Contacts. They range from calls, to emails, in-place
    visits or comments on a website.
    """

    contact = models.ForeignKey(Contact, null=True, blank=True)
    campaign = models.ForeignKey(Campaign, null=True, blank=True)
    product = models.ForeignKey(Product, null=True, blank=True)
    seller = models.ForeignKey("support.Seller", blank=True, null=True, verbose_name=_("Seller"))
    issue = models.ForeignKey("support.Issue", blank=True, null=True, verbose_name=_("Issue"))
    datetime = models.DateTimeField(blank=True, null=True)
    asap = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)

    priority = models.SmallIntegerField(choices=PRIORITY_CHOICES, default=3)
    activity_type = models.CharField(choices=ACTIVITY_TYPES, max_length=1, null=True, blank=True)
    status = models.CharField(choices=ACTIVITY_STATUS_CHOICES, default="P", max_length=1)
    direction = models.CharField(choices=ACTIVITY_DIRECTION_CHOICES, default="O", max_length=1)

    def __unicode__(self):
        return unicode(_("Activity {} for contact {}".format(self.id, self.contact.id)))

    def get_contact_seller(self):
        """
        Returns the seller from the contact this activity is assigned for.
        """
        return self.contact.seller

    def get_priority(self):
        """
        Returns a description of the priority for this activity.
        """
        priorities = dict(PRIORITY_CHOICES)
        return priorities.get(self.priority, "N/A")

    def get_type(self):
        """
        Returns a description of the type for this activity.
        """
        types = dict(ACTIVITY_TYPES)
        return types.get(self.activity_type, "N/A")

    def get_status(self):
        """
        Returns a description of the status for this activity.
        """
        statuses = dict(ACTIVITY_STATUS_CHOICES)
        return statuses.get(self.status, "N/A")

    def get_direction(self):
        """
        Returns a description of the direction of the activity. That can be In or Out.
        """
        directions = dict(ACTIVITY_DIRECTION_CHOICES)
        return directions.get(self.direction, "N/A")

    class Meta:
        verbose_name = _("activity")
        verbose_name_plural = _("activities")


class ContactProductHistory(models.Model):
    """
    Stores the activation and deactivation log (and also other useful changes) history for a contact.
    TODO: This model should be renamed to SubscriptionProductHistory, also the subscription field can be set to None
          when the subscription is deleted (with the on_cascade option).
    """

    contact = models.ForeignKey(Contact)
    subscription = models.ForeignKey(
        Subscription, null=True, blank=True, on_delete=models.SET_NULL
    )
    product = models.ForeignKey(Product)
    campaign = models.ForeignKey(
        Campaign, null=True, blank=True, on_delete=models.SET_NULL
    )
    status = models.CharField(max_length=1, choices=PRODUCTHISTORY_CHOICES)
    seller = models.ForeignKey(
        "support.seller",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )  # To register who was the last seller
    date = models.DateField()

    def get_status(self):
        """
        Returns a description of the status for the history.
        """
        statuses = dict(PRODUCTHISTORY_CHOICES)
        return statuses.get(self.status, "N/A")


class ContactCampaignStatus(models.Model):
    """
    Controls what's the status of a contact inside of a campaign, so we can take statistics of them in the future.
    """

    contact = models.ForeignKey(Contact)
    campaign = models.ForeignKey(Campaign)
    status = models.SmallIntegerField(choices=CAMPAIGN_STATUS_CHOICES, default=1)
    campaign_resolution = models.CharField(choices=CAMPAIGN_RESOLUTION_CHOICES, null=True, blank=True, max_length=2)
    campaign_reject_reason = models.CharField(
        choices=CAMPAIGN_REJECT_REASONS_CHOICES, null=True, blank=True, max_length=1
    )
    seller = models.ForeignKey("support.Seller", null=True, blank=True)
    date_created = models.DateField(auto_now_add=True)
    last_action_date = models.DateField(auto_now=True)
    times_contacted = models.SmallIntegerField(default=0)
    resolution_reason = models.SmallIntegerField(
        choices=CAMPAIGN_RESOLUTION_REASONS_CHOICES, null=True, blank=True)

    class Meta:
        unique_together = ['contact', 'campaign']

    def get_last_activity(self):
        """
        Returns the last activity for the contact, on this exact campaign.
        """
        return Activity.objects.filter(campaign=self.campaign, status="P", contact=self.contact).latest("id")

    def get_status(self):
        """
        Returns a description of the status for this campaign on this contact.
        """
        return dict(CAMPAIGN_STATUS_CHOICES).get(self.status, "N/A")

    def get_campaign_resolution(self):
        """
        Returns a description of the resolution for this campaign on this contact.
        """
        campaign_resolutions = dict(CAMPAIGN_RESOLUTION_CHOICES)
        return campaign_resolutions.get(self.campaign_resolution, "N/A")

    def get_campaign_reject_reason(self):
        """
        Returns a description of the reject reason for this campaign on this contact, this only exists in the case
        the contact has rejected the campaign.
        """
        campaign_reject_reasons = dict(CAMPAIGN_REJECT_REASONS_CHOICES)
        return campaign_reject_reasons.get(self.campaign_reject_reason, "N/A")

    def get_resolution_reason(self):
        campaign_resolution_reasons = dict(CAMPAIGN_RESOLUTION_REASONS_CHOICES)
        return campaign_resolution_reasons.get(self.campaign_reject_reason, "N/A")


class PriceRule(models.Model):
    """
    Controls the price rules for bundled products and for different combinations of products, transforming one or more
    products into another at the moment of billing or defining what are the subscriptions product
    """

    # Controls if the rule is active.
    active = models.BooleanField(default=False)
    # Used so the function that checks the rules can check if the products exist.
    products_pool = models.ManyToManyField(
        Product, limit_choices_to={"offerable": True, "type": "S"}, related_name="pool"
    )
    # If any of the resulting products of the previous rules (by priority) or any of the products on the input products
    # that are still being checked for the rule are present, then the current check is discarded.
    products_not_pool = models.ManyToManyField(
        Product,
        limit_choices_to={"type__in": "DS"},
        related_name="not_pool",
        blank=True,
    )
    # How many of the products of the pool have to be in it for the rule to apply.
    amount_to_pick = models.PositiveSmallIntegerField(default=0)
    # 'What' are we going to do in the rule. Right now the choices are replacing all products foo, the pool, replacing
    # one product from the pool or adding one product to the output.
    mode = models.PositiveSmallIntegerField(default=1, choices=PRICERULE_MODE_CHOICES)
    # If this is selected, the price rule will be treated differently. The rule will check for the product on the pool
    # plus at least one more of ANY product. If it succeeds, then the rule will be applied.
    add_wildcard = models.BooleanField(default=False)
    # Select one product from the pool that will be replaced. This is only used in the 'replace one' mode.
    choose_one_product = models.ForeignKey(
        Product,
        null=True,
        blank=True,
        related_name="chosen_product",
        limit_choices_to={"offerable": True, "type": "S"},
    )
    # When the rule is applied, instead of modifying prices, it will result into a different product that will be
    # added to the output. The product can modify one, or even be added. What can be added can be a normal product or
    # even a discount, depending on what you need.
    # This is especially used when you have bundled products (packages of many products) that might have a different
    # price when selected together, or to add a discount instead of changing those products. Combine this with the
    # not_pool so you make sure you add the specific product you want.
    resulting_product = models.ForeignKey(
        Product,
        null=True,
        blank=True,
        related_name="resulting_product",
        limit_choices_to={"offerable": False},
    )
    # A field for leaving notes on this rule.
    notes = models.TextField(blank=True, null=True)
    # This is the order in which every rule will be checked, from lower to higher. This will probably be renamed to
    # something like "order" in the future.
    priority = models.PositiveSmallIntegerField(null=True, blank=True)


class DynamicContactFilter(models.Model):
    """
    Class to save contacts to be exported to a list or to dynamically tag for easier campaign management. More
    filtering options will be added in the future.

    Optionally you can synchronize these contacts to a mailtrain list by id
    """

    description = models.CharField(max_length=150, unique=True)

    products = models.ManyToManyField(
        Product,
        limit_choices_to={"offerable": True},
        related_name="products",
        blank=True,
    )
    newsletters = models.ManyToManyField(
        Product, limit_choices_to={"type": "N"}, related_name="newsletters", blank=True
    )
    allow_promotions = models.BooleanField(default=False)
    allow_polls = models.BooleanField(default=False)
    mode = models.PositiveSmallIntegerField(choices=DYNAMIC_CONTACT_FILTER_MODES)
    autosync = models.BooleanField(
        default=False, help_text=_("Automatically sync with Mailtrain")
    )
    mailtrain_id = models.CharField(max_length=9, blank=True)
    last_time_synced = models.DateTimeField(null=True, blank=True)

    def __unicode__(self):
        return self.description

    def get_subscriptions(self):
        if self.mode == 1:  # At least one product must match
            products = self.products.all()
            subscriptions = Subscription.objects.filter(active=True)
            for product in products:
                subscriptions = subscriptions.filter(products=product)
        elif self.mode == 2:  # All products must match
            products = self.products.all()
            subscriptions = Subscription.objects.annotate(
                count=Count("products")
            ).filter(active=True, count=products.count())
            for product in products:
                subscriptions = subscriptions.filter(products=product)
        elif self.mode == 3:  # Newsletters
            subscriptions = SubscriptionNewsletter.objects.all()
            for newsletter in self.newsletters.all():
                subscriptions = subscriptions.filter(product=newsletter)
        if self.allow_promotions:
            subscriptions = subscriptions.filter(contact__allow_promotions=True)
        if self.allow_polls:
            subscriptions = subscriptions.filter(contact__allow_polls=True)
        subscriptions = subscriptions.filter(contact__email__isnull=False)
        return subscriptions

    def get_email_count(self):
        return self.get_subscriptions().count()

    def get_emails(self):
        emails = []
        for subscription in self.get_subscriptions():
            if subscription.contact.email:
                emails.append(subscription.contact.email)
        return emails

    def sync_with_mailtrain_list(self):
        # We get all the lists first
        emails_in_filter = self.get_emails()
        emails_in_mailtrain = get_emails_from_mailtrain_list(self.mailtrain_id)

        print("synchronizing DCF {} with list {}".format(self.id, self.mailtrain_id))

        # First we're going to delete the ones that don't belong to the list
        for email_in_mailtrain in emails_in_mailtrain:
            if email_in_mailtrain not in emails_in_filter:
                delete_email_from_mailtrain_list(email_in_mailtrain, self.mailtrain_id)

        # Then we're going to add the ones that aren't in the list
        for email_in_filter in emails_in_filter:
            if email_in_filter not in emails_in_mailtrain:
                subscribe_email_to_mailtrain_list(email_in_filter, self.mailtrain_id)

        # Finally we'll add "now" as last time synced
        self.last_time_synced = datetime.now()
        self.save()

    def get_mode(self):
        modes = dict(DYNAMIC_CONTACT_FILTER_MODES)
        return modes.get(self.mode, "N/A")

    def get_products(self):
        if self.mode == 3:
            return self.newsletters.all()
        else:
            return self.products.all()

    def get_autosync(self):
        return _("Active") if self.autosync else _("Inactive")
