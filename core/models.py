# coding=utf-8
from importlib import import_module
from pydoc import locate
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
from requests.exceptions import RequestException

from django.contrib.auth.models import User
from django.contrib.gis.db import models as gismodels
from django.contrib.gis.geos import Point
from django.conf import settings
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q, Sum, Count, Max, Prefetch
from django.forms import ValidationError
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField
from django.utils.html import mark_safe
from django.utils.functional import cached_property
from django.urls import reverse
from django.utils import timezone

from taggit.managers import TaggableManager
from simple_history.models import HistoricalRecords
from phonenumber_field.modelfields import PhoneNumberField

from util.dates import get_default_next_billing, get_default_start_date, diff_month

from .managers import ProductManager
from .choices import (
    ACTIVITY_DIRECTION_CHOICES,
    ACTIVITY_STATUS_CHOICES,
    ACTIVITY_TYPES,
    ADDRESS_TYPE_CHOICES,
    CAMPAIGN_RESOLUTION_CHOICES,
    CAMPAIGN_RESOLUTION_REASONS_CHOICES,
    CAMPAIGN_STATUS_CHOICES,
    DEBTOR_CONCACTS_CHOICES,
    DYNAMIC_CONTACT_FILTER_MODES,
    EDUCATION_CHOICES,
    ENVELOPE_CHOICES,
    FREQUENCY_CHOICES,
    GENDERS,
    INACTIVITY_REASONS,
    PRICERULE_MODE_CHOICES,
    PRICERULE_WILDCARD_MODE_CHOICES,
    PRICERULE_AMOUNT_TO_PICK_CONDITION_CHOICES,
    PRIORITY_CHOICES,
    PRODUCT_BILLING_FREQUENCY_CHOICES,
    PRODUCT_EDITION_FREQUENCY,
    PRODUCT_WEEKDAYS,
    PRODUCTHISTORY_CHOICES,
    SUBSCRIPTION_STATUS_CHOICES,
    SUBSCRIPTION_TYPE_CHOICES,
    UNSUBSCRIPTION_TYPE_CHOICES,
    VARIABLE_TYPES,
    DISCOUNT_PRODUCT_MODE_CHOICES,
    DISCOUNT_VALUE_MODE_CHOICES,
    EMAIL_REPLACEMENT_STATUS_CHOICES,
    EMAIL_BOUNCE_ACTIONLOG_CHOICES,
    EMAIL_BOUNCE_ACTION_MAXREACH,
    FreeSubscriptionRequestedBy,
)
from .utils import (
    delete_email_from_mailtrain_list,
    subscribe_email_to_mailtrain_list,
    get_emails_from_mailtrain_list,
    validateEmailOnWeb,
    updatewebuser,
)


regex_alphanumeric = r"^[@A-Za-z0-9ñüáéíóúÑÜÁÉÍÓÚ _'.\-]*$"  # noqa
regex_alphanumeric_msg = _(
    "This field only supports alphanumeric characters, at, apostrophes, spaces, hyphens, underscores, and periods."
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

    def __str__(self):
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

    def __str__(self):
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

    def __str__(self):
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
    value = models.CharField(max_length=500, verbose_name=_("value"))
    type = models.CharField(max_length=255, blank=True, choices=VARIABLE_TYPES, verbose_name=_("type"))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("variable")
        verbose_name_plural = _("variables")
        ordering = ("name",)


class ProductSubscriptionPeriod(models.Model):
    """
    Represents a period of time for a product. This is used mainly to categorize the product by its duration.
    """

    name = models.CharField(max_length=255, unique=True)
    months_duration = models.PositiveIntegerField(help_text=_("Number of months this period represents."))
    description = models.TextField(blank=True, help_text=_("Optional description for this period, if needed."))

    class Meta:
        verbose_name = _("Product Subscription Period")
        verbose_name_plural = _("Product Subscription Periods")
        ordering = ['months_duration']

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Products that a subscription can have. (They must have a billing priority to be billed).
    """

    class RenewalTypeChoices(models.TextChoices):
        """Choices for the renewal type"""

        AUTOMATIC = "A", _("Automatic")
        MANUAL = "M", _("Manual")
        BOTH = "X", _("Both")

    class ProductTypeChoices(models.TextChoices):
        """Choices for the product type"""

        SUBSCRIPTION = "S", _("Subscription")
        NEWSLETTER = "N", _("Newsletter")
        DISCOUNT = "D", _("Discount")
        PERCENTAGE_DISCOUNT = "P", _("Percentage discount")
        ADVANCED_DISCOUNT = "A", _("Advanced discount")
        OTHER = "O", _("Other")

    name = models.CharField(max_length=100, verbose_name=_("Name"), db_index=True)
    slug = AutoSlugField(populate_from="name", null=True, blank=True, editable=True)
    active = models.BooleanField(default=False, verbose_name=_("Active"))
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    type = models.CharField(max_length=1, default="O", choices=ProductTypeChoices.choices, db_index=True)
    weekday = models.IntegerField(default=None, choices=PRODUCT_WEEKDAYS, null=True, blank=True)
    offerable = models.BooleanField(
        default=False,
        verbose_name=_("Allow offer"),
        help_text=_("Allow product to be shown in the new subscription forms"),
    )
    has_implicit_discount = models.BooleanField(default=False, verbose_name=_("Has implicit discount"))
    billing_priority = models.PositiveSmallIntegerField(null=True, blank=True)
    digital = models.BooleanField(default=False, verbose_name=_("Digital"))
    edition_frequency = models.IntegerField(default=None, choices=PRODUCT_EDITION_FREQUENCY, null=True, blank=True)
    temporary_discount_months = models.PositiveSmallIntegerField(null=True, blank=True)
    target_product = models.ForeignKey(
        "self", blank=True, null=True, on_delete=models.SET_NULL, limit_choices_to={"offerable": True, "type": "S"}
    )
    old_pk = models.PositiveIntegerField(blank=True, null=True)
    internal_code = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Internal code"))
    billing_days = models.PositiveSmallIntegerField(
        default=30,
        verbose_name=_("Billing frequency"),
        choices=PRODUCT_BILLING_FREQUENCY_CHOICES,
        null=True,
        blank=True,
    )
    renewal_type = models.CharField(
        max_length=1,
        default=RenewalTypeChoices.AUTOMATIC,
        choices=RenewalTypeChoices.choices,
        verbose_name=_("Renewal type"),
        null=True,
        blank=True,
    )
    duration_months = models.PositiveSmallIntegerField(
        default=1,
        verbose_name=_("Duration in months"),
        null=True,
        blank=True,
    )
    subscription_period = models.ForeignKey(
        ProductSubscriptionPeriod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    terms_and_conditions = models.ManyToManyField(
        "core.TermsAndConditions",
        through="core.TermsAndConditionsProduct",
    )
    mercadopago_id = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("MercadoPago ID"))
    objects = ProductManager()

    def __str__(self):
        name = self.name
        if self.type == "N":
            name += ", newsletter"
        return "%s" % name

    def natural_key(self):
        return (self.slug,)

    def get_weekday(self):
        """
        Returns the weekday of the product. Used only for products that are bound to a specific day.
        """
        weekdays = dict(PRODUCT_WEEKDAYS)
        return weekdays.get(self.weekday, "N/A")

    def get_last_terms_and_conditions(self):
        return self.terms_and_conditions.order_by("-date").first()

    def has_terms_and_conditions(self):
        return self.terms_and_conditions.exists()

    class Meta:
        verbose_name = _("product")
        verbose_name_plural = _("products")
        ordering = ("id",)


class EmailBounceActionLog(models.Model):
    created = models.DateField(editable=False, auto_now_add=True)
    contact = models.ForeignKey("Contact", blank=True, null=True, on_delete=models.SET_NULL)
    email = models.EmailField(editable=False)
    action = models.PositiveSmallIntegerField(choices=EMAIL_BOUNCE_ACTIONLOG_CHOICES)

    @staticmethod
    def email_is_bouncer(email):
        """Returns last created date iff the email given has a 'bounce detection' in the past 90 days"""
        if email:
            email = email.lower()
        return (
            email
            and EmailBounceActionLog.objects.filter(
                created__gt=date.today() - timedelta(90), email=email, action=EMAIL_BOUNCE_ACTION_MAXREACH
            ).aggregate(created_max=Max("created"))["created_max"]
        )

    class Meta:
        unique_together = ("created", "contact", "email", "action")
        ordering = ("-created", "email")


class IdDocumentType(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class Contact(models.Model):
    """Holds people personal information"""

    class ContactTypeChoices(models.TextChoices):
        """Choices for the contact type"""

        PERSON = "P", _("Person")
        COMPANY = "C", _("Company")

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
    last_name = models.CharField(
        max_length=100, validators=[alphanumeric], blank=True, null=True, verbose_name=_("Last name")
    )
    contact_type = models.CharField(
        max_length=1,
        choices=ContactTypeChoices.choices,
        default="P",
        verbose_name=_("Contact type"),
        null=True,
        blank=True,
    )
    id_document = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Identifcation Document"))
    id_document_type = models.ForeignKey(
        "core.IdDocumentType",
        blank=True,
        null=True,
        verbose_name=_("Document type"),
        on_delete=models.SET_NULL,
    )
    phone = PhoneNumberField(blank=True, default="", verbose_name=_("Phone"), db_index=True)
    phone_extension = models.CharField(blank=True, default="", max_length=16, verbose_name=_("Phone extension"))
    work_phone = PhoneNumberField(blank=True, default="", verbose_name=_("Work phone"), db_index=True)
    work_phone_extension = models.CharField(
        blank=True,
        default="",
        max_length=16,
        verbose_name=_("Work phone extension"),
    )
    mobile = PhoneNumberField(blank=True, default="", verbose_name=_("Mobile"), db_index=True)
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
    cms_date_joined = models.DateTimeField(blank=True, null=True, verbose_name=_("CMS join date"))
    ranking = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name=_("Ranking"))
    history = HistoricalRecords()

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('contact_detail', args=[str(self.id)])

    def get_normalized_email(self):
        """
        Returns the normalized (lowercased) email if it exists.
        """
        return self.email.lower() if self.email else None

    def get_old_email(self):
        """
        Returns the old email in lowercase if it exists.
        """
        if self.id:
            old_email = self.__class__.objects.get(id=self.id).email
            return old_email.lower() if old_email else None

    def clean(self, debug=False):
        email = self.get_normalized_email()

        if self.id:
            old_email = self.get_old_email()
            if old_email and old_email != email:
                if EmailBounceActionLog.email_is_bouncer(email):
                    raise ValidationError(
                        {"email": f"El email '{email}' registra exceso de rebotes, no se permite su utilización"}
                    )

        if settings.WEB_UPDATE_USER_ENABLED and email and self.id:
            self.custom_clean(email, debug)

    def custom_clean(self, email, debug):
        # TODO: a good improvement will be to receive also the old_email and include it in the api call for trying to
        #       dedupe this scneario: no subscriber has my contact_id but there are two subscribers with two different
        #       contact ids, one with the old email and the other with the new email.
        resp = validateEmailOnWeb(self.id, email)
        if resp in ("TIMEOUT", "ERROR"):
            # TODO: Alert user about web timeout or error
            if debug:
                print("%s calling validatiion email CMS api for contact %d" % (resp, self.id))
        else:
            msg = resp.get("msg")
            if msg != "OK":
                retval = resp.get("retval")
                # calling a "dedupe" custom api if available (not opensourced yet in utopia-cms)
                custom_validation_module_name = getattr(settings, "WEB_UPDATE_USER_VALIDATION_MODULE", None)
                if custom_validation_module_name and retval > 0:
                    dedupe_resp = locate(custom_validation_module_name).dedupeOnWeb(self.id, retval, email)
                    if dedupe_resp in ("TIMEOUT", "ERROR"):
                        # TODO: Alert user about web timeout or error
                        if debug:
                            print("%s calling dedupe CMS api with: %d, %d, %s" % (dedupe_resp, self.id, retval, email))
                        raise ValidationError({"email": msg})
                    elif dedupe_resp.get("retval") != 1:
                        raise ValidationError({"email": msg})
                    else:
                        # calling "me" again for security reasons (maybe another user in web can be in conflict)
                        self.custom_clean(email, debug)
                else:
                    raise ValidationError({"email": msg})

    def save(self, *args, **kwargs):
        if not getattr(self, "updatefromweb", False) and not getattr(self, "_skip_clean", False):
            self.clean(debug=settings.DEBUG_CONTACT_CLEAN)
        # TODO: next line breaks test_subscriptor.TestContact.test2_cliente_que_no_tiene_email_debe_tener_email_en_...
        #       Fix the test and explain why the field is not needed anymore or submit a different solution.
        self.no_email = self.email is None
        return super().save(*args, **kwargs)

    def is_debtor(self):
        """
        Checks if the contact has expired invoices, returns True or False
        """
        return bool(self.expired_invoices_count())

    def get_pending_invoices(self):
        """
        Returns a queryset with the pending invoices for the contact.
        """
        return self.invoice_set.filter(paid=False, debited=False, canceled=False, uncollectible=False)

    def pending_invoices_count(self):
        return self.get_pending_invoices().count()

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
        return self.invoice_set.count()

    def get_paid_invoices_count(self):
        return self.invoice_set.filter(Q(paid=True) | Q(debited=True)).count()

    def get_latest_invoice(self):
        if self.invoice_set.exists():
            return self.invoice_set.latest("id")
        else:
            return None

    def add_to_campaign(self, campaign_id):
        """
        Adds a contact to a campaign if not already added.

        Args:
            campaign_id (int): The ID of the campaign to add the contact to.

        Returns:
            str: A success message if the contact was added.

        Raises:
            Campaign.DoesNotExist: If the campaign with the given ID doesn't exist.
            ContactAlreadyInCampaignError: If the contact is already in the campaign.
        """
        try:
            campaign = Campaign.objects.get(pk=campaign_id)
        except Campaign.DoesNotExist:
            raise Campaign.DoesNotExist(f"Campaign with ID {campaign_id} does not exist.")

        contact_campaign_status, created = ContactCampaignStatus.objects.get_or_create(contact=self, campaign=campaign)

        if created:
            return _("Contact %(name)s (ID: %(id)s) added to campaign %(campaign)s") % {
                "name": self.get_full_name(),
                "id": self.id,
                "campaign": campaign.name,
            }
        else:
            raise Exception(
                _("Contact %(name)s (ID: %(id)s) is already in campaign %(campaign)s")
                % {
                    "name": self.get_full_name(),
                    "id": self.id,
                    "campaign": campaign.name,
                }
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
                    status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST,
                    category=category,
                ).count()
                == self.issue_set.filter(category=category).count()
            )
        else:
            return (
                self.issue_set.filter(status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST).count()
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
        return (
            SubscriptionProduct.objects.filter(subscription__active=True, subscription__contact=self)
            .select_related('product')  # Assumes `product` is a ForeignKey
            .prefetch_related(
                Prefetch(
                    'label_contact',
                    queryset=Contact.objects.only('id', 'name', 'last_name'),  # Customize fields as needed
                )
            )
            .order_by("product__billing_priority", "product__id")
        )

    def get_subscriptions_with_expired_invoices(self):
        """
        Returns a list with the distinct subscriptions that have expired invoices
        """
        subscriptions = []
        for invoice in self.get_expired_invoices():
            for invoice_item in invoice.invoiceitem_set.all():
                if invoice_item.subscription and invoice_item.subscription not in subscriptions:
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

    def get_last_activity_formatted(self):
        last_activity = self.last_activity()
        if last_activity:
            msg = ' '.join(
                [last_activity.datetime.date().strftime("%d/%m/%Y"), last_activity.get_activity_type_display() or '']
            )
            return msg
        else:
            return None

    def get_gender(self):
        """
        Gets the description of the gender (Male, Female, Other)
        """
        genders = dict(GENDERS)
        return genders.get(self.gender, "N/A")

    def add_newsletter(self, newsletter_id):
        sn, created = SubscriptionNewsletter.objects.get_or_create(
            contact=self, product=Product.objects.get(id=newsletter_id, type="N")
        )
        if not created and not sn.active:
            sn.active = True
            sn.save()

    def add_newsletter_by_slug(self, newsletter_slug):
        try:
            sn, created = SubscriptionNewsletter.objects.get_or_create(
                contact=self, product=Product.objects.get(slug=newsletter_slug, type="N")
            )
            if not created and not sn.active:
                sn.active = True
                sn.save()
        except (Product.DoesNotExist, SubscriptionNewsletter.MultipleObjectsReturned):
            pass

    def get_newsletters(self):
        """
        Returns a queryset with all the newsletters that this contact has subscriptions in (active or inactive).
        """
        return self.subscriptionnewsletter_set.all()

    def get_active_newsletters(self):
        """
        Returns a queryset with all the newsletters that this contact has subscriptions in (active only).
        """
        return self.get_newsletters().filter(active=True)

    def remove_newsletter(self, newsletter_id):
        try:
            newsletter = Product.objects.get(id=newsletter_id, type="N")
        except Product.DoesNotExist:
            raise _("Invalid product id")
        else:
            self.get_active_newsletters().filter(product=newsletter).delete()

    def remove_newsletters(self):
        """Remove all contac's active newsletters"""
        self.get_active_newsletters().delete()

    def has_newsletter(self, newsletter_id):
        return self.get_active_newsletters().filter(product_id=newsletter_id).exists()

    def get_newsletter_products(self):
        return Product.objects.filter(
            type="N", subscriptionnewsletter__contact=self, subscriptionnewsletter__active=True
        )

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

        history_of_this_product = subscription.contactproducthistory_set.filter(product=product)

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
        return self.issue_set.filter(status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST).count()

    def get_open_issues_count(self):
        return self.get_total_issues_count() - self.get_finished_issues_count()

    def get_open_issues_by_subcategory_count(self, sub_category_slug):
        return (
            self.issue_set.filter(sub_category__slug=sub_category_slug)
            .exclude(status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST)
            .count()
        )

    def get_finished_issues_by_subcategory_count(self, sub_category_slug):
        return (
            self.issue_set.filter(sub_category__slug=sub_category_slug)
            .exclude(status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST)
            .count()
        )

    def get_open_issues_by_category_count(self, category):
        return (
            self.issue_set.filter(category=category)
            .exclude(status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST)
            .count()
        )

    def get_finished_issues_by_category_count(self, category):
        return (
            self.issue_set.filter(category=category)
            .exclude(status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST)
            .count()
        )

    def get_total_scheduledtask_count(self):
        return self.scheduledtask_set.count()

    def get_total_activities_count(self):
        return self.activity_set.count()

    def offer_default_newsletters_condition(self):
        return all(
            (
                getattr(settings, "CORE_DEFAULT_NEWSLETTERS", {}),
                self.email,
                not self.get_newsletters(),
                self.get_active_subscriptions(),
            )
        )

    def add_default_newsletters(self):
        computed_slug_set, result = set(), []
        for func_path, nl_slugs in list(getattr(settings, "CORE_DEFAULT_NEWSLETTERS", {}).items()):
            func_module, func_name = func_path.rsplit(".", 1)
            func_def = getattr(import_module(func_module), func_name, None)
            if func_def and func_def(self):
                computed_slug_set = computed_slug_set.union(set(nl_slugs))
        for product_slug in computed_slug_set:
            try:
                self.add_newsletter_by_slug(product_slug)
            except Exception as exc:
                if settings.DEBUG:
                    print(f"DEBUG: error in add_default_newsletters: {exc}")
            else:
                result.append(product_slug)
        return result

    def do_not_call(self, phone_att="phone"):
        number = getattr(self, phone_att)
        if number is None or number.national_number is None:
            return False
        return DoNotCallNumber.objects.filter(number__contains=number.national_number).exists()

    def do_not_call_phone(self):
        return self.do_not_call("phone")

    def do_not_call_work_phone(self):
        return self.do_not_call("work_phone")

    def do_not_call_mobile(self):
        return self.do_not_call("mobile")

    def date_of_first_invoice(self):
        if self.invoice_set.exists():
            return self.invoice_set.first().creation_date
        else:
            return None

    def merge_other_contact_into_this(
        self,
        source: "Contact",
        name: str = None,
        last_name: str = None,
        id_document: str = None,
        phone: str = None,
        mobile: str = None,
        work_phone: str = None,
        email: str = None,
        gender: str = None,
        subtype_id: str = None,
        education: str = None,
        ocupation_id: str = None,
        birthdate: str = None,
    ) -> list:
        """Takes a source contact and merges it within this one. It allows the manual overriding of data.

        Args:
            source (Contact): The contact whose data is going to be deleted and merged into this one.
            name (str, optional): Override name. Defaults to None.
            last_name (str, optional): Override last name. Defaults to None.
            id_document (str, optional): Override id document. Defaults to None.
            phone (str, optional): Override phone. Defaults to None.
            mobile (str, optional): Override mobie. Defaults to None.
            work_phone (str, optional): Override work phone. Defaults to None.
            email (str, optional): Override email address. Defaults to None.
            gender (str, optional): Override gender. Defaults to None.
            subtype_id (str, optional): Override subtype_id. Defaults to None.
            education (str, optional): Override education choice. Defaults to None.
            ocupation_id (str, optional): Override ocupation_id. Defaults to None.
            birthdate (str, optional): Override birthdate. Defaults to None.
        """
        errors = []
        try:
            if email:
                source.email = None
                source.no_email = True
                source.save()
            if not email or email == "":
                self.email = None
                self.not_email = True
            else:
                self.email = email.strip()
                self.not_email = False
            self.save()  # check for the try
            if name:
                self.name = name.strip()
            if last_name:
                self.last_name = last_name.strip()
            if id_document:
                if source.id_document == id_document.strip():
                    source.id_document = None
                    source.save()
                self.id_document = id_document.strip()
            if self.id_document == "":
                self.id_document = None
            if phone:
                self.phone = phone.strip()
            if work_phone:
                self.work_phone = phone.strip()
            if mobile:
                self.mobile = mobile.strip()
            if gender:
                self.gender = gender.strip()
            if subtype_id:
                self.subtype_id = int(subtype_id.strip())
            if education:
                self.education = education.strip()
            if ocupation_id:
                self.ocupation_id = int(ocupation_id.strip())
            if birthdate:
                self.birthdate = birthdate.strip()
            self.notes = (
                f"Combined from {source.id} - {source.get_full_name()} at {date.today()}" + f"\n{self.notes or ''}"
            )
            if source.notes:
                self.notes += f"\n\nNotes imported from {source.id} - {source.get_full_name()}\n\n"
                self.notes += source.notes
            for tag in source.tags.all():
                self.tags.add(tag.name)
            self.save()
            source.addresses.update(contact=self)
            source.subscriptions.update(contact=self)
            source.invoice_set.update(contact=self)
            # We need to delete the activities that have a campaign and are yet to be resolved
            source.activity_set.filter(campaign__isnull=False, status__in=["A", "P"]).delete()
            # Then we update the contact of the remaining activities
            source.activity_set.update(contact=self)
            source.issue_set.update(contact=self)
            # ContactCampaignStatus have a unique constraint on (contact, campaign)
            # so we need to delete the source's ContactCampaignStatus and keep the ones from the target if they exist.
            if self.contactcampaignstatus_set.exists():
                source.contactcampaignstatus_set.all().delete()
            source.contactproducthistory_set.update(contact=self)
            source.tags.add("eliminar")

        except Exception as e:
            errors.append(e)

        return errors

    def add_single_invoice_with_products(self, products, payment_type, expiration_days=30):
        from invoicing.models import Invoice

        invoice = Invoice.objects.create(
            contact=self,
            payment_type=payment_type,
            creation_date=date.today(),
            expiration_date=date.today() + timedelta(days=expiration_days),
            service_to=date.today(),
            service_from=date.today(),
            amount=0,
        )
        for product in products:
            invoice.add_item(product)
        invoice.amount = invoice.get_total_amount()
        invoice.save()
        return invoice

    def get_full_name(self):
        return " ".join(filter(None, (self.name, self.last_name)))

    get_full_name.short_description = _("Full name")

    def get_full_id_document(self):
        return " ".join(
            filter(None, (self.id_document_type.name if self.id_document_type else None, self.id_document))
        )

    get_full_id_document.short_description = _("Full ID document")

    def create_address_from_email(self):
        if self.email:
            address = Address.objects.create(
                address_1=self.email,
                city=getattr(settings, "DEFAULT_CITY", None),
                state=State.objects.get(name=getattr(settings, "DEFAULT_STATE", None)),
                address_type="digital",
                contact=self,
            )
            return address
        return None

    class Meta:
        verbose_name = _("contact")
        verbose_name_plural = _("contacts")
        ordering = ("-id",)


class Country(models.Model):
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=2, unique=True)  # ISO 3166-1 alpha-2 codes
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("country")
        verbose_name_plural = _("countries")
        ordering = ('name',)


class State(models.Model):
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=10)  # State/region code
    country = models.ForeignKey(Country, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("state")
        verbose_name_plural = _("states")
        ordering = ('name',)
        unique_together = [['code', 'country']]


class Address(models.Model):
    """
    Model that contains all the addresses for each contact. They're reused throughout the subscriptions,
    issues, and more models. This uses settings.
    """

    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("Contact"),
        related_name="addresses",
    )
    address_1 = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Address 1"))
    address_2 = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Address 2"))
    city = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        default=getattr(settings, "DEFAULT_CITY", None),
        verbose_name=_("City"),
    )
    email = models.EmailField(blank=True, null=True, verbose_name=_("Email"))
    address_type = models.CharField(max_length=50, choices=ADDRESS_TYPE_CHOICES, verbose_name=_("Address type"))
    notes = models.TextField(blank=True, null=True, verbose_name=_("Notes"))
    default = models.BooleanField(default=False, verbose_name=_("Default"))
    # history = HistoricalRecords()
    picture = models.FileField(upload_to="address_pictures/", blank=True, null=True)
    google_maps_url = models.CharField(max_length=2048, null=True, blank=True)
    do_not_show = models.BooleanField(default=False, help_text=_("Do not show in picture/google maps list"))

    # GEOREF fields
    georef_point = gismodels.PointField(blank=True, null=True)
    latitude = models.DecimalField(null=True, blank=True, max_digits=10, decimal_places=6)
    longitude = models.DecimalField(null=True, blank=True, max_digits=10, decimal_places=6)
    verified = models.BooleanField(null=True, default=False)
    needs_georef = models.BooleanField(null=True, default=False)
    # These last three fields are here for debug reasons. The first one is totally unused
    address_georef_id = models.IntegerField(null=True, blank=True)
    state_georef_id = models.IntegerField(null=True, blank=True)
    city_georef_id = models.IntegerField(null=True, blank=True)
    country_old = models.CharField(
        verbose_name=_("Country (old)"),
        max_length=50,
        blank=True,
        null=True,
    )
    state_old = models.CharField(
        verbose_name=_("State (old)"),
        max_length=50,
        blank=True,
        null=True,
        default=getattr(settings, "DEFAULT_STATE", None),
    )
    if settings.USE_STATES_CHOICE:
        state_old.choices = settings.STATES

    # New fields with explicit column names
    country = models.ForeignKey(
        'core.Country',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("Country"),
        db_column='country_fk',  # Explicit different column name
    )
    state = models.ForeignKey(
        'core.State',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("State"),
        db_column='state_fk',  # Explicit different column name
    )

    @cached_property
    def country_name(self):
        return self.country.name if self.country else None

    @cached_property
    def state_name(self):
        return self.state.name if self.state else None

    def __str__(self):
        return ' '.join(filter(None, (self.address_1, self.address_2, self.city, self.state_name, self.country_name)))

    def add_note(self, note):
        self.notes = f"{note}" if not self.notes else self.notes + f"\n{note}"
        self.save()

    def get_routes(self):
        sps = SubscriptionProduct.objects.filter(address=self.id).order_by('route')
        routes = []
        for sp in sps:
            if sp.route:
                routes.append(str(sp.route.number))
        if len(routes) > 0:
            routes = list(set(routes))
            return ", ".join(routes)
        else:
            return "N/A"

    def reset_georef(self):
        self.latitude, self.longitude, self.georef_point = None, None, None
        self.needs_georef = True
        self.verified = False
        self.save()

    def save(self, *args, **kwargs):
        if self.latitude and self.longitude:
            self.georef_point = Point(float(self.longitude), float(self.latitude), srid=4326)
        if self.georef_point and not (self.latitude and self.longitude):
            self.latitude = self.georef_point.y
            self.longitude = self.georef_point.x
        if self.state_georef_id and self.city_georef_id and self.georef_point:
            self.verified = True
        super(Address, self).save(*args, **kwargs)

    class Meta:
        verbose_name = _("address")
        verbose_name_plural = _("addresses")


class SubscriptionProduct(models.Model):
    """
    Contains a single product of type 'S' (subscription) inside of a subscription for a single contact.
    This allows contacts to have more than one product with its respective amount of copies, address where the product
    is delivered, and route/order.
    """

    product = models.ForeignKey("core.Product", on_delete=models.CASCADE, null=True)
    subscription = models.ForeignKey("core.Subscription", on_delete=models.CASCADE)
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
    active = models.BooleanField(default=True)

    def __str__(self):
        # TODO: result translation (i18n)
        if self.address:
            address = self.address.address_1
        else:
            address = ""

        return "{} - {} - (Suscripción de ${})".format(
            self.product, address, self.subscription.get_price_for_full_period()
        )

    def get_subscription_active(self):
        return self.subscription.active


class SubscriptionNewsletter(models.Model):
    """
    Similar to SubscriptionProduct, this contains a single product of type 'N' (newsletter) for a single contact, but
    inside of the same contact. So one contact can only have one set of newsletters which they will receive.
    """

    product = models.ForeignKey("core.Product", on_delete=models.CASCADE, limit_choices_to={"type": "N"})
    contact = models.ForeignKey("core.Contact", on_delete=models.CASCADE)
    active = models.BooleanField(default=True)

    def __str__(self):
        return str(self.product)


class Subscription(models.Model):
    """
    Model that holds a contract in which the contact will be able to receive one or more products (see
    SubscriptionProduct). This will allow you to bill the contact for this service (invoicing app) if the subscription
    has a paid type.
    """

    class RENEWAL_TYPE_CHOICES(models.TextChoices):
        AUTOMATIC = "A", _("Auto-renewal")
        MANUAL = "M", _("One-time")

    campaign = models.ForeignKey(
        "core.Campaign", blank=True, null=True, verbose_name=_("Campaign"), on_delete=models.SET_NULL
    )
    active = models.BooleanField(default=True, verbose_name=_("Active"))
    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, verbose_name=_("Contact"), related_name="subscriptions"
    )
    type = models.CharField(max_length=1, default="N", choices=SUBSCRIPTION_TYPE_CHOICES)
    status = models.CharField(default="OK", max_length=2, choices=SUBSCRIPTION_STATUS_CHOICES)

    # Billing information. This is added in case it's necessary.
    billing_name = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Billing name"))
    billing_id_doc = models.CharField(
        max_length=20, blank=True, null=True, verbose_name=_("Billing Identification Document")
    )
    rut = models.CharField(max_length=12, blank=True, null=True, verbose_name=_("R.U.T."))
    billing_phone = PhoneNumberField(blank=True, default="", verbose_name=_("Billing phone"), db_index=True)
    billing_phone_extension = models.CharField(
        blank=True, default="", max_length=16, verbose_name=_("Billing phone extension")
    )
    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_("Balance"),
        help_text=_("Positive for discount, negative for surcharge"),
    )
    send_bill_copy_by_email = models.BooleanField(default=True, verbose_name=_("Send bill copy by email"))
    billing_address = models.ForeignKey(
        Address,
        blank=True,
        null=True,
        verbose_name=_("Billing address"),
        related_name="billing_contacts",
        on_delete=models.SET_NULL,
    )
    billing_email = models.EmailField(blank=True, null=True, verbose_name=_("Billing email"))
    envelope = models.BooleanField(default=False, verbose_name=_("Envelope"), null=True)
    free_envelope = models.BooleanField(default=False, verbose_name=_("Free envelope"), null=True)
    start_date = models.DateField(blank=True, null=True, default=get_default_start_date, verbose_name=_("Start date"))
    end_date = models.DateField(blank=True, null=True, verbose_name=_("End date"))
    next_billing = models.DateField(
        default=get_default_next_billing, blank=True, null=True, verbose_name=_("Next billing")
    )
    highlight_in_listing = models.BooleanField(default=False, verbose_name=_("Highlight in listing"))
    send_pdf = models.BooleanField(default=False, verbose_name=_("Send pdf"))
    inactivity_reason = models.IntegerField(
        choices=INACTIVITY_REASONS, blank=True, null=True, verbose_name=_("Inactivity reason")
    )
    pickup_point = models.ForeignKey(
        "logistics.PickupPoint", on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("Pickup point")
    )

    # Unsubscription
    unsubscription_date = models.DateField(blank=True, null=True, verbose_name=_("Unsubscription date"))
    unsubscription_manager = models.ForeignKey(
        User, verbose_name=_("Unsubscription manager"), null=True, blank=True, on_delete=models.SET_NULL
    )
    unsubscription_reason = models.PositiveSmallIntegerField(
        choices=settings.UNSUBSCRIPTION_REASON_CHOICES, blank=True, null=True, verbose_name=_("Unsubscription reason")
    )
    unsubscription_channel = models.PositiveSmallIntegerField(
        choices=settings.UNSUBSCRIPTION_CHANNEL_CHOICES,
        blank=True,
        null=True,
        verbose_name=_("Unsubscription channel"),
    )
    unsubscription_type = models.PositiveSmallIntegerField(
        choices=UNSUBSCRIPTION_TYPE_CHOICES,
        blank=True,
        null=True,
        verbose_name=_("Unsubscription type"),
    )
    unsubscription_addendum = models.TextField(blank=True, null=True, verbose_name=_("Unsubscription addendum"))
    unsubscription_products = models.ManyToManyField(
        Product,
        related_name="unsubscriptions",
    )

    # Product
    products = models.ManyToManyField(Product, through="SubscriptionProduct")
    frequency = models.PositiveSmallIntegerField(default=1, choices=FREQUENCY_CHOICES)
    payment_type = models.CharField(
        max_length=2,
        choices=settings.SUBSCRIPTION_PAYMENT_METHODS,
        null=True,
        blank=True,
        verbose_name=_("Payment type"),
    )

    updated_from = models.OneToOneField("core.Subscription", on_delete=models.SET_NULL, blank=True, null=True)
    payment_certificate = models.FileField(upload_to="certificates/", blank=True, null=True)

    free_subscription_requested_by = models.CharField(
        max_length=2,
        choices=FreeSubscriptionRequestedBy.choices,
        null=True,
        blank=True,
        verbose_name=_("Free subscription requested by"),
    )
    validated = models.BooleanField(default=False, verbose_name=_("Validated"))
    validated_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        verbose_name=_("Validated by"),
        on_delete=models.SET_NULL,
        related_name="validated_subscriptions",
    )
    validated_date = models.DateTimeField(blank=True, null=True, verbose_name=_("Validated date"))
    renewal_type = models.CharField(
        max_length=2,
        choices=RENEWAL_TYPE_CHOICES.choices,
        default="A",
        verbose_name=_("Renewal type"),
    )

    history = HistoricalRecords()

    billing_contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='billed_subscriptions',
        verbose_name=_("Billing Contact"),
    )
    terms_and_conditions = models.ForeignKey(
        "core.TermsAndConditions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Terms and conditions"),
    )
    number_of_subscriptions = models.IntegerField(
        default=1,
        help_text="Number of subscriptions to create, more than 1 for corporate subscriptions",
        verbose_name=_("Number of subscriptions"),
    )
    override_price = models.IntegerField(
        null=True,
        blank=True,
        help_text="Override the price of the subscription, useful for corporate subscriptions",
        verbose_name=_("Override price"),
    )
    parent_subscription = models.ForeignKey(
        "core.Subscription",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Parent subscription"),
        related_name="affiliate_subscriptions",
    )

    def __str__(self):
        return str(
            _("{active} subscription for the contact {contact} with {products} products").format(
                active=_("Active") if self.active else _("Inactive"),
                contact=self.contact.get_full_name(),
                products=self.get_product_count(),
            )
        )

    def get_product_count(self):
        """
        Returns the amount of products in this subscription
        """
        return self.products.count()

    def get_used_affiliate_slots(self):
        """
        Returns the number of used affiliate slots for the parent subscription. It already adds the current
        subscription.
        """
        return self.affiliate_subscriptions.count() + 1

    def get_available_affiliate_slots(self):
        """
        Returns the number of available affiliate slots for the parent subscription. It already subtracts the current
        subscription from the total number of subscriptions.
        """
        return self.number_of_subscriptions - self.affiliate_subscriptions.count() - 1

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
                '<td style="padding:5px;">{}</td></tr>'.format(sp.product.name, sp.copies, sp.address)
            )
        text += "</table>"
        text += "<a href='/admin/core/subscription/{}/' target='_blank'>Edit</a>".format(self.id)
        return mark_safe(text)

    edit_products_field.allow_tags = True
    edit_products_field.short_description = "Products"

    def add_product(
        self,
        product,
        address=None,
        copies=1,
        message=None,
        instructions=None,
        route=None,
        order=None,
        seller_id=None,
        override_date=None,
        label_contact=None,
        tag=False,
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
            route=route,
            order=order,
        )
        self.contact.add_product_history(
            subscription=self,
            product=product,
            new_status="A",
            campaign=self.campaign,
            seller=sp.seller,
            override_date=override_date,
        )
        if product.edition_frequency == 4 and tag:
            self.contact.tags.add(product.slug + "-added")
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

    def get_billing_contact(self):
        """
        Returns the contact to bill for this subscription.
        If no specific billing contact is set, returns the subscription's contact.
        """
        return self.billing_contact or self.contact

    def get_billing_name(self):
        """
        Gets the billing name for the contact. If it doesn't have one, then the contact's name is returned.
        Used primarily in invoicing.
        """
        billing_contact = self.get_billing_contact()
        if self.billing_name:
            return self.billing_name
        else:
            return billing_contact.get_full_name()

    def get_billing_phone(self):
        """
        Gets the billing phone for the contact. If it doesn't have one, then the contact's phone is returned.
        Used primarily in invoicing.
        """
        billing_contact = self.get_billing_contact()
        if self.billing_phone:
            return self.billing_phone
        else:
            return billing_contact.phone

    def get_billing_document(self):
        """
        Gets the billing id_document for the contact. It chooses between rut, id_document and the contact_id_document
        in that order.
        Used primarily in invoicing.
        """
        billing_contact = self.get_billing_contact()
        if self.rut:
            return self.rut
        elif self.billing_id_doc:
            return self.billing_id_doc
        else:
            return billing_contact.id_document

    def get_billing_address(self):
        """
        Gets the billing address for the contact. If there is none set, then it will return the first address.
        It will return None given the case there's no available address in any products of the subscription.
        Used primaily in invoicing.
        """
        if self.billing_address:
            return self.billing_address.address_1
        else:
            subscription_products = SubscriptionProduct.objects.filter(subscription=self)
            addresses = [sp.address for sp in subscription_products if sp.address]
            if not addresses:
                if self.contact.email:
                    return self.contact.email
                else:
                    return None
            else:
                return addresses[0].address_1

    def get_billing_state(self):
        """
        Gets the billing state for the contact. If it doesn't have one, it will chose the contact's first address'
        state.
        Used primarily in invoicing.
        """
        if self.billing_address and self.billing_address.state_name:
            return self.billing_address.state_name
        else:
            sub_prods = SubscriptionProduct.objects.filter(subscription=self)
            addresses = [sp.address for sp in sub_prods]
            if addresses:
                return addresses[0].state_name
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
        products = self.products.filter(
            type__in=[Product.ProductTypeChoices.SUBSCRIPTION, Product.ProductTypeChoices.OTHER]
        ).order_by("billing_priority")
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
            if sp.product.edition_frequency == 4 and self.contact.email:
                route = 56
                address = self.contact.email
                state = getattr(settings, "DEFAULT_STATE", None)
                city = getattr(settings, "DEFAULT_CITY", None)
            elif sp.product.digital and self.contact.email:
                route = 56
                address = self.contact.email
                state = getattr(settings, "DEFAULT_STATE", None)
                city = getattr(settings, "DEFAULT_CITY", None)
            elif sp.address and sp.address.address_1:
                address = sp.address.address_1
                state = sp.address.state_name
                city = sp.address.city
                route = sp.route_id
            else:
                route, address, state, city = None, None, None, None
            if address:
                result = {
                    "route": route,
                    "order": sp.order,
                    "address": address,
                    "state": state,
                    "city": city,
                    "name": self.get_billing_name(),
                }
                if settings.DEBUG:
                    print(f"DEBUG: get_billing_data_by_priority (if address) result: {result}")
            elif not address and getattr(settings, "DEFAULT_BILLING_ADDRESS", None):
                result = getattr(settings, "DEFAULT_BILLING_ADDRESS", None)
                result["name"] = self.get_billing_name()
            elif settings.DEBUG:
                print(("DEBUG: No address found in the billing data for subscription %d." % self.id))
        elif settings.DEBUG:
            print(("DEBUG: No product found in the billing data for subscription %d." % self.id))
        if not result and getattr(settings, "FORCE_DUMMY_MISSING_BILLING_DATA", False):
            result = {}
        return result

    def get_full_address_by_priority(self):
        for product in Product.objects.filter(type="S").order_by("billing_priority"):
            if self.subscriptionproduct_set.filter(subscription=self, product=product).exists():
                sp = self.subscriptionproduct_set.filter(subscription=self, product=product).first()
                if sp.address:
                    return sp.address
        return None

    def get_address_by_priority(self):
        for product in Product.objects.filter(type="S").order_by("billing_priority"):
            if self.subscriptionproduct_set.filter(subscription=self, product=product).exists():
                sp = self.subscriptionproduct_set.filter(subscription=self, product=product).first()
                if sp.address:
                    return sp.address.address_1
        return None

    def get_address_2_by_priority(self):
        for product in Product.objects.filter(type="S").order_by("billing_priority"):
            if self.subscriptionproduct_set.filter(subscription=self, product=product).exists():
                sp = self.subscriptionproduct_set.filter(subscription=self, product=product).first()
                if sp.address:
                    return sp.address.address_2
        return None

    def get_frequency_discount(self):
        """
        Returns the amount discounted configured in settings, for this subscription frequency
        """
        return getattr(settings, "DISCOUNT_%d_MONTHS" % self.frequency, 0)

    def get_first_day_of_the_week(self):
        """
        Returns an integer representing the first weekday (based on isoweekday) on the products this subscription has.
        Returns 6 if no weekday products are found.
        """
        # Check weekdays 1-5 in order and return the first match
        for weekday in range(1, 6):
            if SubscriptionProduct.objects.filter(subscription=self, product__weekday=weekday).exists():
                return weekday
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
            frequency_extra = _(" {} months".format(self.frequency)) if self.frequency > 1 else ""
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
            frequency_extra = _(" {} months".format(self.frequency)) if self.frequency > 1 else ""
            discount_item.description = discount["description"] + frequency_extra
            discount_item.amount = discount["amount"] * self.frequency
            discount_item.type_dr = discount["type_dr"]
            discount_item.type = discount["type"]
            discount_item.subscription = self
            invoiceitem_list.append(discount_item)

        return invoiceitem_list

    def product_summary(self, with_pauses=False):
        """
        Takes each product for this subscription and returns a list with the copies for each.
        """
        # products = self.products.filter(type='S')  # TODO: explain the usage of this commented line or remove it
        from .utils import process_products

        subscription_products = SubscriptionProduct.objects.filter(subscription=self)
        if with_pauses:
            subscription_products = subscription_products.filter(active=True)

        dict_all_products = {str(sp.product.id): str(sp.copies) for sp in subscription_products}
        return process_products(dict_all_products)

    # def product_summary(self):  TODO: explain why this is commented or remove it
    #     """Cached version of product summary to avoid repeated queries"""
    #     subscription_products = self.subscriptionproduct_set.select_related('product').all()
    #     dict_all_products = {str(sp.product.id): str(sp.copies) for sp in subscription_products}
    #     from .utils import process_products

    #     return process_products(dict_all_products)

    def product_summary_list(self, with_pauses=False) -> list:
        summary = self.product_summary(with_pauses)
        filtered_products = Product.objects.filter(pk__in=summary.keys(), type="S")
        return filtered_products

    def render_product_summary(self):
        output = "<ul>"
        for product_id, copies in list(self.product_summary().items()):
            product = Product.objects.get(pk=product_id)
            output += "<li>{}</li>".format(product.name)
        return output + "</ul>"

    def get_price_for_full_period(self, debug_id=""):
        """Returns the price for a single period on this customer"""
        from .utils import calc_price_from_products

        return calc_price_from_products(self.product_summary(), self.frequency, debug_id)

    def get_price_for_full_period_with_pauses(self, debug_id=""):
        """
        Same as the previous one, but uses the pauses. repeated some code just to use it directly on templates.
        """
        from .utils import calc_price_from_products

        return calc_price_from_products(self.product_summary(with_pauses=True), self.frequency, debug_id)

    def period_start(self):
        if not self.next_billing:
            return None
        return self.next_billing - relativedelta(months=self.frequency)

    def period_end(self):
        return self.next_billing

    def get_current_period(self):
        """
        Returns two values, one for the start and one for the end of the period that's going to be paid on this
        subscription.
        """
        return self.period_start(), self.period_end()

    def price_per_day(self):
        return self.get_price_for_full_period() / (self.period_end() - self.period_start()).days

    def days_elapsed_since_period_start(self):
        return (date.today() - self.period_start()).days

    def days_remaining_in_period(self):
        return (self.period_end() - date.today()).days

    def amount_already_paid_in_period(self):
        """
        Divides the price of one period between the amount of days (frequency) to get the price for one day of
        this subscription. Then multiplies the value of this single day by the amount of days that have passed since
        the start of the period, giving as a result the amount that the customer has already paid.

        This is useful to add that amount as a discount for the next subscription when selling a new subscription to
        the customer, in the case the new subscription price is greater than the old one.
        """
        assert self.type == "N", _("Subscription must be normal to use this method")
        period_start = self.period_start()
        days_already_used = (date.today() - period_start).days
        amount = int(self.price_per_day() * days_already_used)
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
        price_per_day = self.get_price_for_full_period() / (period_end - period_start).days
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

    def has_all_days(self):
        return (
            self.has_monday()
            and self.has_tuesday()
            and self.has_wednesday()
            and self.has_thursday()
            and self.has_friday()
        )

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
                self.issue_set.exclude(status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST, category=category).count()
                == self.issue_set.all().count()
            )
        else:
            return (
                self.issue_set.exclude(status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST).count()
                == self.issue_set.all().count()
            )

    def show_products_html(self, ul=False, br=True):
        """
        Renders all the products into a list of products.
        """
        output = ""
        if ul:
            output += "<ul>"
        for sp in SubscriptionProduct.objects.filter(subscription=self, product__offerable=True).order_by(
            "product_id"
        ):
            count = self.products.filter(offerable=True).count()
            if ul:
                if sp.label_contact:
                    output += "<li>{} ({})</li>".format(sp.product.name, sp.label_contact.get_full_name())
                else:
                    output += "<li>{}</li>".format(sp.product.name)
            else:
                if sp.label_contact:
                    output += "{} ({})".format(sp.product.name, sp.label_contact.get_full_name())
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

    def get_inactivity_reason(self):
        """
        Returns the unsubscription reason.
        """
        inactivity_reasons = dict(INACTIVITY_REASONS)
        return inactivity_reasons.get(self.inactivity_reason, "N/A")

    def get_unsubscription_reason(self):
        """
        Returns the unsubscription reason.
        """
        unsubscription_reasons = dict(settings.UNSUBSCRIPTION_REASON_CHOICES)
        return unsubscription_reasons.get(self.unsubscription_reason, "N/A")

    def get_unsubscription_channel(self):
        """
        Returns the unsubscription reason.
        """
        unsubscription_channels = dict(settings.UNSUBSCRIPTION_CHANNEL_CHOICES)
        return unsubscription_channels.get(self.unsubscription_channel, "N/A")

    def get_unsubscription_type(self):
        """
        Returns the unsubscription reason.
        """
        unsubscription_types = dict(UNSUBSCRIPTION_TYPE_CHOICES)
        return unsubscription_types.get(self.unsubscription_type, "N/A")

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

    def get_frequency(self):
        """
        Returns the frequency.
        """
        frequencies = dict(FREQUENCY_CHOICES)
        return frequencies.get(self.frequency, "N/A")

    def get_copies_for_product(self, product_id):
        try:
            sp = SubscriptionProduct.objects.get(subscription=self, product_id=product_id)
            return sp.copies or 1
        except SubscriptionProduct.DoesNotExist:
            return 1

    def get_message_for_product(self, product_id):
        try:
            sp = SubscriptionProduct.objects.get(subscription=self, product_id=product_id)
            return sp.label_message or ""
        except SubscriptionProduct.DoesNotExist:
            return ""

    def get_address_for_product(self, product_id):
        try:
            sp = SubscriptionProduct.objects.get(subscription=self, product_id=product_id)
            return sp.address
        except SubscriptionProduct.DoesNotExist:
            return None

    def get_instructions_for_product(self, product_id):
        try:
            sp = SubscriptionProduct.objects.get(subscription=self, product_id=product_id)
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
        qs = SubscriptionProduct.objects.filter(subscription=self).select_related("product")
        if without_discounts:
            qs = qs.exclude(product__type="D")
        return qs

    def is_obsolete(self):
        return Subscription.objects.filter(updated_from=self).exists()

    def get_updated_subscription(self):
        if self.is_obsolete():
            return Subscription.objects.get(updated_from=self)
        else:
            return None

    def balance_abs(self):
        return abs(self.balance)

    def paused_until(self):
        if self.scheduledtask_set.filter(completed=False, category="PA").exists():
            return (
                self.scheduledtask_set.filter(subscription=self, completed=False, category="PA").first().execution_date
            )
        else:
            return None

    def get_permanency_invoice_set(self):
        invoice_set = self.invoice_set.all()
        subscription = self
        while subscription.updated_from:
            subscription = subscription.updated_from
            invoice_set = invoice_set | subscription.invoice_set.all()
        return invoice_set

    def get_permanency_invoice_count(self):
        invoices_count = 0
        invoices_count += self.invoice_set.count()
        subscription = self
        while subscription.updated_from:
            subscription = subscription.updated_from
            invoices_count += subscription.invoice_set.count()
        return invoices_count

    def get_permanency_months_count(self):
        months_count = 0
        months_count += self.invoice_set.count() * self.frequency
        subscription = self
        while subscription.updated_from:
            subscription = subscription.updated_from
            months_count += subscription.invoice_set.count() * subscription.frequency
        return months_count

    def get_original_start_date(self):
        start_date = self.start_date
        subscription = self
        while subscription.updated_from:
            subscription = subscription.updated_from
            start_date = subscription.start_date
        return start_date

    def has_paused_products(self):
        return self.subscriptionproduct_set.filter(active=False).exists()

    def has_subscriptionproduct_in_special_route(self):
        if not hasattr(self, 'subscriptionproduct_set'):
            return False
        if not hasattr(settings, 'SPECIAL_ROUTES_FOR_SELLERS_LIST'):
            return False
        return self.subscriptionproduct_set.filter(route__pk__in=settings.SPECIAL_ROUTES_FOR_SELLERS_LIST).exists()

    def never_paid_first_invoice(self):
        # Used to check if the user has never paid a single invoice in this subscription and its ancestors
        invoices = self.get_permanency_invoice_set()
        # Check if all invoices are overdue
        return (
            invoices.filter(
                expiration_date__lte=date.today(), paid=False, debited=False, canceled=False, uncollectible=False
            ).count()
            == invoices.count()
        )

    def get_first_seller(self):
        # Used to retrieve the first seller that sold this subscription
        if self.subscriptionproduct_set.filter(seller__isnull=False).exists():
            return self.subscriptionproduct_set.filter(seller__isnull=False).first().seller
        else:
            return None

    def has_sales_record(self):
        return self.salesrecord_set.exists()

    def validate(self, user):
        self.validated = True
        self.validated_by = user
        self.validated_date = timezone.now()
        self.save()

    @property
    def unsubscription_manager_name(self):
        if not self.unsubscription_manager:
            return None
        if self.unsubscription_manager.get_full_name():
            return self.unsubscription_manager.get_full_name()
        else:
            return self.unsubscription_manager.username

    def billing_requirements_met(self):
        pass

    def bill(self, billing_date=None, dpp=10):
        from invoicing.bill_subscription import bill_subscription
        return bill_subscription(self, billing_date, dpp)

    class Meta:
        verbose_name = _("subscription")
        verbose_name_plural = _("subscriptions")
        permissions = [
            ("can_add_free_subscription", _("Can add free subscription")),
            ("can_add_corporate_subscription", _("Can add corporate subscription")),
        ]


class Campaign(models.Model):
    """
    Model that controls sales campaigns, in which sellers can call contacts to offer your product.
    """

    class Priorities(models.IntegerChoices):
        HIGHEST = 1, _("1 - Highest")
        HIGH = 2, _("2 - High")
        MID = 3, _("3 - Mid")
        LOW = 4, _("4 - Low")
        LOWEST = 5, _("5 - Lowest")

    name = models.CharField(max_length=255, verbose_name=_("name"))
    active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    priority = models.PositiveSmallIntegerField(
        default=3, blank=True, null=True, verbose_name=_("Priority"), choices=Priorities.choices
    )
    days = models.PositiveSmallIntegerField(default=5, blank=True, null=True)

    def __str__(self):
        return self.name

    def get_activities_by_seller(self, seller, status=None, type=None, datetime=None):
        """
        Returns all the activities on this campaign, for a specific seller. Activities on a campaign imply that the
        contact has been scheduled to be called in the future.
        """
        acts = Activity.objects.filter(campaign=self, seller=seller).order_by("datetime")
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

        lower_priority_contacts are those that have a campaign with a priority lower than the current one

        same_priority_contacts are those that have a campaign with the same priority as the current one

        contacts_with_current_activities are those that have an activity with a campaign that is active and has a
        status of "P" (Pending)

        contacts_with_lower_priority_activities are those that have an activity with a campaign that is active and has
        a priority lower than the current one

        contacts_with_same_priority_activities are those that have an activity with a campaign that is active and has
        the same priority as the current one

        All of those are excluded from the final queryset
        """
        lower_priority_contacts = Contact.objects.filter(
            contactcampaignstatus__campaign__priority__lt=self.priority,
            contactcampaignstatus__campaign__active=True,
            contactcampaignstatus__status=1,
        )
        same_priority_contacts = Contact.objects.filter(
            contactcampaignstatus__campaign__pk__lt=self.pk,
            contactcampaignstatus__campaign__priority=self.priority,
            contactcampaignstatus__campaign__active=True,
            contactcampaignstatus__status=1,
        ).exclude(contactcampaignstatus__campaign__pk=self.pk)
        contacts_with_current_activities = Contact.objects.filter(
            activity__campaign__isnull=False,
            activity__campaign__active=True,
            activity__status="P",
        )
        """
        # TODO: remove or explain why not used
        contacts_with_lower_priority_activities = Contact.objects.filter(
            activity__campaign=self,
            activity__campaign__priority__lt=self.priority,
            activity__campaign__active=True,
        )
        contacts_with_same_priority_activities = Contact.objects.filter(
            activity__campaign=self,
            activity__campaign__priority=self.priority,
            activity__campaign__active=True,
        ).exclude(activity__campaign__pk=self.pk)
        """

        return (
            self.contactcampaignstatus_set.filter(seller_id=seller_id, status__in=[1, 3])
            .exclude(contact__id__in=lower_priority_contacts.values('pk'))
            .exclude(contact__id__in=same_priority_contacts.values('pk'))
            .exclude(contact__id__in=contacts_with_current_activities.values('pk'))
            # TODO: @ prev TODO
            # .exclude(contact__id__in=contacts_with_lower_priority_activities.values('pk'))
            # .exclude(contact__id__in=contacts_with_same_priority_activities.values('pk'))
        )

    def get_not_contacted_count(self, seller_id):
        """
        Returns the count of ContactCampaignStatus objects for all Contacts that have not been called yet (status=1)
        """
        return self.get_not_contacted(seller_id).count()

    def get_already_contacted(self, seller_id):
        """
        Returns the ContactCampaignStatus objects for all Contacts that have already been called yet (status=2, 3)
        """
        return self.contactcampaignstatus_set.filter(seller_id=seller_id, status=2)

    def get_already_contacted_count(self, seller_id):
        """
        Returns the count of ContactCampaignStatus objects for all Contacts that have already been called yet
        (status=2, 3)
        """
        return self.get_already_contacted(seller_id).count()

    def get_successful_count(self, seller_id):
        return self.contactcampaignstatus_set.filter(seller_id=seller_id, campaign_resolution__in=["S1", "S2"]).count()

    class Meta:
        verbose_name = _("campaign")
        verbose_name_plural = _("campaigns")
        ordering = (
            "-active",
            "priority",
            "name",
        )


class ActivityTopic(models.Model):
    """
    Model to store the topics for activities.
    """

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class ActivityResponse(models.Model):
    """
    Model to store the responses for activities.
    """

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Activity(models.Model):
    """
    Model that stores every interaction the company has with Contacts. They range from calls, to emails, in-place
    visits or comments on a website.
    """

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, null=True, blank=True)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    seller = models.ForeignKey(
        "support.Seller", on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("Seller")
    )
    issue = models.ForeignKey(
        "support.Issue", on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("Issue")
    )
    datetime = models.DateTimeField(blank=True, null=True)
    asap = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)

    priority = models.SmallIntegerField(choices=PRIORITY_CHOICES, default=3)
    activity_type = models.CharField(choices=ACTIVITY_TYPES, max_length=1, null=True, blank=True)
    status = models.CharField(choices=ACTIVITY_STATUS_CHOICES, default="P", max_length=1)
    direction = models.CharField(choices=ACTIVITY_DIRECTION_CHOICES, default="O", max_length=1)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Created by")
    )
    topic = models.ForeignKey(ActivityTopic, on_delete=models.SET_NULL, null=True, blank=True)
    response = models.ForeignKey(ActivityResponse, on_delete=models.SET_NULL, null=True, blank=True)
    history = HistoricalRecords()

    def __str__(self):
        return str(_("Activity {} for contact {}".format(self.id, self.contact.id)))

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

    def mark_as_sale(self, register_activity, campaign, subscription=None):
        # Update the activity
        self.status = "C"
        activity_notes = _("Success in sale after scheduling {}\n{}").format(
            datetime.now().strftime("%Y-%m-%d %H:%M"), register_activity
        )
        self.notes = self.notes + "\n" + activity_notes if self.notes else activity_notes
        self.save()

        # Update the related ContactCampaignStatus
        ccs = ContactCampaignStatus.objects.get(campaign=campaign, contact=self.contact)
        ccs.campaign_resolution = "S2"  # success with direct sale
        ccs.status = 4  # Ended with contact
        ccs.save()

        if subscription:
            subscription.campaign = campaign
            subscription.save()

    @property
    def created_by_name(self):
        if self.created_by:
            # Return the full name if it exists, otherwise return the username
            return self.created_by.get_full_name() or self.created_by.username
        # If created_by is None, return an empty string
        return ""

    class Meta:
        verbose_name = _("activity")
        verbose_name_plural = _("activities")
        get_latest_by = "id"


class ContactProductHistory(models.Model):
    """
    Stores the activation and deactivation log (and also other useful changes) history for a contact.
    TODO: This model should be renamed to SubscriptionProductHistory, also the subscription field can be set to None
          when the subscription is deleted (with the on_cascade option).
    """

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)
    subscription = models.ForeignKey(Subscription, null=True, blank=True, on_delete=models.SET_NULL)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    campaign = models.ForeignKey(Campaign, null=True, blank=True, on_delete=models.SET_NULL)
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

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    status = models.SmallIntegerField(choices=CAMPAIGN_STATUS_CHOICES, default=1)
    campaign_resolution = models.CharField(choices=CAMPAIGN_RESOLUTION_CHOICES, null=True, blank=True, max_length=2)
    seller = models.ForeignKey("support.Seller", on_delete=models.CASCADE, null=True, blank=True)
    date_created = models.DateField(auto_now_add=True)
    date_assigned = models.DateField(null=True, blank=True)
    last_action_date = models.DateField(auto_now=True)
    times_contacted = models.SmallIntegerField(default=0)
    resolution_reason = models.SmallIntegerField(choices=CAMPAIGN_RESOLUTION_REASONS_CHOICES, null=True, blank=True)

    class Meta:
        unique_together = ["contact", "campaign"]

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

    def get_resolution_reason(self):
        campaign_resolution_reasons = dict(CAMPAIGN_RESOLUTION_REASONS_CHOICES)
        return campaign_resolution_reasons.get(self.resolution_reason, "N/A")

    def handle_direct_sale(self, register_activity, subscription=None):
        self.campaign_resolution = "S2"  # this is a success with direct sale
        self.status = 4  # Ended with contact
        self.save()

        # Prepare the activity notes
        activity_notes = _("Success in direct sale {}\n{}").format(
            datetime.now().strftime("%Y-%m-%d %H:%M"), register_activity
        )

        # Create the activity
        Activity.objects.create(
            activity_type="C",
            seller=self.seller,
            contact=self.contact,
            status="C",
            direction="O",
            datetime=datetime.now(),
            campaign=self.campaign,
            notes=activity_notes,
        )

        if subscription:
            subscription.campaign = self.campaign
            subscription.save()


class PriceRule(models.Model):
    """
    Controls the price rules for bundled products and for different combinations of products, transforming one or more
    products into another at the moment of billing or defining what are the subscriptions product
    """

    # Controls if the rule is active.
    active = models.BooleanField(default=False)

    # Used so the function that checks the rules can check if the products exist.
    products_pool = models.ManyToManyField(
        Product, limit_choices_to={"offerable": True, "type__in": "DS"}, related_name="pool"
    )

    # If any of the resulting products of the previous rules (by priority) or any of the products on the input products
    # that are still being checked for the rule are present, then the current check is discarded.
    products_not_pool = models.ManyToManyField(
        Product,
        limit_choices_to={"type__in": "DSAP"},
        related_name="not_pool",
        blank=True,
    )

    # How many of the products of the pool have to be in it for the rule to apply.
    amount_to_pick = models.PositiveSmallIntegerField(default=0)

    # How to compare the amount of products in the pool against amount_to_pick.
    amount_to_pick_condition = models.CharField(
        max_length=2, choices=PRICERULE_AMOUNT_TO_PICK_CONDITION_CHOICES, default="eq"
    )

    # 'What' are we going to do in the rule. Right now the choices are replacing all products foo, the pool, replacing
    # one product from the pool or adding one product to the output.
    mode = models.PositiveSmallIntegerField(default=1, choices=PRICERULE_MODE_CHOICES)

    # - Pool AND ANY: The rule will check for the product on the pool plus at least one more of ANY product.
    # - Pool OR ANY: The rule will check for the product on the pool OR ANY product. (An empty pool can also succed).
    # If it succeeds, then the rule will be applied.
    wildcard_mode = models.CharField(max_length=12, choices=PRICERULE_WILDCARD_MODE_CHOICES, blank=True, null=True)

    # Select one product from the pool that will be replaced. This is only used in the 'replace one' mode.
    choose_one_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
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
        on_delete=models.CASCADE,
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

    # TODO: describe this field
    ignore_product_bundle = models.ManyToManyField("core.ProductBundle", blank=True)

    # TODO: describe this field
    history = HistoricalRecords()


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
    autosync = models.BooleanField(default=False, help_text=_("Automatically sync with Mailtrain"))
    mailtrain_id = models.CharField(max_length=9, blank=True)
    last_time_synced = models.DateTimeField(null=True, blank=True)
    debtor_contacts = models.PositiveSmallIntegerField(null=True, blank=True, choices=DEBTOR_CONCACTS_CHOICES)

    def __str__(self):
        return self.description

    def get_subscriptions(self):
        if self.mode == 1:  # At least one product must match
            products = self.products.all()
            subscriptions = Subscription.objects.filter(active=True, products__in=products)
        elif self.mode == 2:  # All products must match
            products = self.products.all()
            subscriptions = Subscription.objects.annotate(count=Count("products")).filter(
                active=True, count=products.count()
            )
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
        if self.debtor_contacts:
            only_debtors = subscriptions.filter(
                contact__invoice__expiration_date__lte=date.today(),
                contact__invoice__paid=False,
                contact__invoice__debited=False,
                contact__invoice__canceled=False,
                contact__invoice__uncollectible=False,
            ).prefetch_related("contact__invoice_set")
            if self.debtor_contacts == 1:
                subscriptions = subscriptions.exclude(pk__in=only_debtors.values('pk'))
            elif self.debtor_contacts == 2:
                subscriptions = only_debtors
        if self.mode == 1:
            subscriptions = subscriptions.filter(contact__email__isnull=False).distinct("contact")
        else:
            subscriptions = subscriptions.filter(contact__email__isnull=False)

        return subscriptions

    def get_email_count(self):
        return self.get_subscriptions().count()

    def get_contacts(self):
        if self.mode == 1:
            return Contact.objects.filter(subscriptions__in=self.get_subscriptions()).distinct()
        else:
            return Contact.objects.filter(subscriptions__in=self.get_subscriptions())

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

        if settings.DEBUG:
            print(f"DEBUG: synchronizing DCF {self.id} with list {self.mailtrain_id}")

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


class ProductBundle(models.Model):
    products = models.ManyToManyField(Product)

    def __str__(self):
        return_str = "Bundle: "
        for index, product in enumerate(self.products.all()):
            if index > 0:
                return_str += " + {}".format(product.name)
            else:
                return_str += "{}".format(product.name)
        return return_str


class AdvancedDiscount(models.Model):
    # TODO: analize if "limit choices" should be set in fk and m2m fields
    discount_product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="discount", null=True)
    find_products = models.ManyToManyField(Product, related_name="find_products_discount")
    products_mode = models.PositiveSmallIntegerField(choices=DISCOUNT_PRODUCT_MODE_CHOICES)
    value_mode = models.PositiveSmallIntegerField(choices=DISCOUNT_VALUE_MODE_CHOICES)
    value = models.PositiveSmallIntegerField(default=0)

    def __str__(self):
        if self.value_mode == 2:
            value = "{}%".format(self.value)
        else:
            value = "${}".format(self.value)
        return "{} ({})".format(self.discount_product.name, value)


class DoNotCallNumber(models.Model):
    number = models.CharField(max_length=20, primary_key=True)

    @staticmethod
    def delete_all_numbers():
        DoNotCallNumber.objects.all().delete()

    @staticmethod
    def upload_new_numbers(numbers_list):
        objs = []
        for number in numbers_list:
            objs.append(DoNotCallNumber(number=number[0]))
        DoNotCallNumber.objects.bulk_create(objs)

    def __str__(self):
        return self.number

    class Meta:
        ordering = ["number"]


class EmailReplacement(models.Model):
    domain = models.CharField(max_length=252, unique=True)
    replacement = models.CharField(max_length=252)
    status = models.CharField(max_length=15, choices=EMAIL_REPLACEMENT_STATUS_CHOICES, default="suggested")

    @staticmethod
    def approved():
        return dict(EmailReplacement.objects.filter(status="approved").values_list("domain", "replacement"))

    @staticmethod
    def is_rejected(domain, replacement):
        return EmailReplacement.objects.filter(domain=domain, replacement=replacement, status="rejected").exists()

    def __str__(self):
        return "%s -> %s (%s)" % (self.domain, self.replacement, self.get_status_display())

    class Meta:
        ordering = ("status", "domain")


def update_customer(cust, newmail, field, value):
    # TODO: rename to update_contact or similar, rename cust arg accordingly also
    if settings.DEBUG:
        print("DEBUG: core.models.update_customer(%s[id=%d], %s, %s, %s)" % (cust, cust.id, newmail, field, value))
    if not getattr(cust, 'updatefromweb', False):
        cust.updatefromweb = True
    if field:
        if field in ("newsletters", "area_newsletters", "newsletters_remove", "area_newsletters_remove"):
            map_setting = getattr(
                settings, "WEB_UPDATE_%sNEWSLETTER_MAP" % ("AREA_" if field.startswith("area_") else "")
            )
            if field in ("newsletters", "area_newsletters"):
                if not value:
                    # delete only those that are mapped (newsletters only)
                    cust.subscriptionnewsletter_set.filter(product__slug__in=list(map_setting.values())).delete()
                else:
                    for obj_id in json.loads(value):
                        try:
                            cust.add_newsletter_by_slug(map_setting[obj_id])
                        except KeyError:
                            pass
            else:
                # special call for only remove one newsletter. TODO: recheck this assumption
                obj_id = json.loads(value)[0]
                try:
                    cust.subscriptionnewsletter_set.filter(product__slug=map_setting[obj_id]).delete()
                except (KeyError, SubscriptionNewsletter.DoesNotExist):
                    pass
        else:
            mfield = getattr(settings, "WEB_UPDATE_SUBSCRIBER_MAP", {}).get(field, None)
            if mfield:
                setattr(cust, mfield, eval(value) if type(getattr(cust, mfield)) is bool else value)
                cust.save()
    else:
        cust.email = newmail or None
        cust.save()


def update_web_user(contact, target_email=None, newsletter_data=None, area_newsletters=False, method="PUT"):
    """
    Sync some fields from contact with the web CMS linked subscriptor target reference.
    If newsletter_data is given, newsletters will be sent to websync.
    @param contact: Contact object store the previous state of the contact
    @param target_email: Email used to set the connection. If not, use given contact's email
    @param newsletter_data: field data for newsletters.
    @param area_newsletters: field name for newsletters.
    """
    if settings.WEB_UPDATE_USER_ENABLED and not getattr(contact, "updatefromweb", False) and contact.id:
        fields_to_update = {}
        try:
            if newsletter_data:
                field = ("area_" if area_newsletters else "") + "newsletters"
                fields_to_update.update({field: newsletter_data})

            current_saved_contact = Contact.objects.get(pk=contact.id)
            # TODO: change this 1-field-per-request approach to a new 1-request-only approach with all chanmges
            for f in getattr(settings, "WEB_UPDATE_USER_CHECKED_FIELDS", []):
                before_saved_value = getattr(contact, f)
                current_saved_value = getattr(current_saved_contact, f)
                if before_saved_value is not None and current_saved_value != before_saved_value:
                    fields_to_update.update({f: current_saved_value})
            # call for sync if there are fields to update
            api_result = updatewebuser(
                contact.id, target_email, contact.email, contact.name, contact.last_name, fields_to_update, method
            )
        except RequestException as e:
            raise ValidationError("{}: {}".format(_("CMS sync error"), e))
        except Contact.DoesNotExist:
            pass
        else:
            if api_result in ("TIMEOUT", "ERROR"):
                contact.sync_error = api_result  # TODO: try to get more info from the error


def update_web_user_newsletters(contact):
    """
    Update web user newsletters when they are edited
    @params contact: Contact instance
    """
    try:
        newsletters_slugs = list(contact.get_active_newsletters().values_list('product__slug', flat=True))
        update_web_user(contact, contact.email, json.dumps(newsletters_slugs))
    except Exception as exc:
        if settings.DEBUG:
            print(f"DEBUG: Error sending the request to CMS: {exc}")


class MailtrainList(models.Model):
    """
    Stores Mailtrain lists to use when updating contacts in the Mailtrain system. This is also used in the CMS
    and should be synced to the model in the CMS.

    In the future this could be used to sync the lists to Mailtrain, but for now it's only used to store the list id.
    """

    cid = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Mailtrain List")
        verbose_name_plural = _("Mailtrain Lists")


class TermsAndConditions(models.Model):
    version = models.CharField(max_length=255)
    date = models.DateField()
    code = models.CharField(max_length=255)
    pdf_file = models.FileField(upload_to="terms_and_conditions", null=True, blank=True)
    text = models.TextField()

    def __str__(self) -> str:
        return f"T&C {self.version} ({self.date})"


class TermsAndConditionsProduct(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    terms_and_conditions = models.ForeignKey(TermsAndConditions, on_delete=models.CASCADE)
    date = models.DateField()

    def __str__(self) -> str:
        return f"T&C {self.terms_and_conditions.version} ({self.date}) for {self.product.name}"
