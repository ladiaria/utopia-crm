# coding=utf-8
from datetime import date

from django.db import models
from django.db.models import Q
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe
from autoslug import AutoSlugField


from core.models import Campaign
from core.utils import process_products

from simple_history.models import HistoricalRecords

from support.choices import (
    ISSUE_CATEGORIES,
    ISSUE_ANSWERS,
    ISSUE_SUBCATEGORIES,
    SCHEDULED_TASK_CATEGORIES,
)


class Seller(models.Model):
    """
    Stores information about the sellers. An user should be assigned to them so that user can access their own seller
    dashboard.
    """

    name = models.CharField(max_length=40, verbose_name=_("Name"))
    internal = models.BooleanField(default=False, verbose_name=_("Is internal?"))
    user = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
    old_pk = models.PositiveIntegerField(blank=True, null=True, db_index=True)

    def __str__(self):
        return self.name

    def get_contact_count(self):
        return self.contact_set.all().count()

    def get_unfinished_campaigns(self):
        seller_campaigns = Campaign.objects.filter(
            Q(end_date__isnull=True) | Q(end_date__gte=timezone.now()),
            contactcampaignstatus__seller=self,
            contactcampaignstatus__status__lt=4,
        ).distinct()
        return seller_campaigns

    def get_campaigns_by_status(self, status):
        seller_campaigns = Campaign.objects.filter(
            Q(end_date__isnull=True) | Q(end_date__gte=timezone.now()),
            contactcampaignstatus__seller=self,
            contactcampaignstatus__status__in=status,
        ).distinct()
        return seller_campaigns

    def upcoming_activity(self):
        return (
            self.activity_set.filter(
                Q(campaign__end_date__isnull=True) | Q(campaign__end_date__gte=timezone.now()),
                status="P",
                activity_type="C",
            )
            .order_by("datetime", "id")
            .first()
        )

    def total_pending_activities(self):
        return self.activity_set.filter(
            Q(campaign__end_date__isnull=True) | Q(campaign__end_date__gte=timezone.now()),
            status="P",
            activity_type="C",
        )

    def total_pending_activities_count(self):
        return self.activity_set.filter(
            Q(campaign__end_date__isnull=True) | Q(campaign__end_date__gte=timezone.now()),
            status="P",
            activity_type="C",
        ).count()

    class Meta:
        verbose_name = _("seller")
        verbose_name_plural = _("sellers")
        ordering = ["name"]


class Issue(models.Model):
    """
    Description: Contains data about things that our contacts want from us.
    """

    date_created = models.DateField(auto_now_add=True)
    contact = models.ForeignKey("core.Contact", on_delete=models.CASCADE, verbose_name=_("Contact"))
    date = models.DateField(default=date.today, verbose_name=_("Date"))
    category = models.CharField(max_length=1, blank=True, null=True, choices=ISSUE_CATEGORIES)
    subcategory = models.CharField(max_length=3, blank=True, null=True, choices=ISSUE_SUBCATEGORIES)
    inside = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)
    manager = models.ForeignKey(
        "auth.User",
        blank=True,
        null=True,
        related_name="issue_manager",
        on_delete=models.SET_NULL,
    )  # User who created the issue. Non-editable
    assigned_to = models.ForeignKey(
        "auth.User",
        blank=True,
        null=True,
        related_name="issue_assigned",
        on_delete=models.SET_NULL,
    )  # Editable, assigned to which user
    progress = models.TextField(blank=True, null=True)
    answer_1 = models.CharField(max_length=2, blank=True, null=True, choices=ISSUE_ANSWERS)
    answer_2 = models.TextField(blank=True, null=True)
    status = models.ForeignKey("support.IssueStatus", blank=True, null=True, on_delete=models.SET_NULL)
    sub_category = models.ForeignKey("support.IssueSubcategory", blank=True, null=True, on_delete=models.SET_NULL)
    end_date = models.DateField(blank=True, null=True)
    next_action_date = models.DateField(blank=True, null=True)
    closing_date = models.DateField(blank=True, null=True)
    copies = models.PositiveSmallIntegerField(default=0)
    # Optional attributes
    subscription_product = models.ForeignKey(
        "core.SubscriptionProduct", null=True, blank=True, on_delete=models.SET_NULL
    )
    subscription = models.ForeignKey("core.Subscription", on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey("core.Product", on_delete=models.CASCADE, null=True, blank=True)
    address = models.ForeignKey("core.Address", on_delete=models.CASCADE, null=True, blank=True)
    envelope = models.BooleanField(default=False, verbose_name=_("Envelope"), null=True)
    history = HistoricalRecords()

    class Meta:
        pass

    def get_category(self):
        categories = dict(ISSUE_CATEGORIES)
        return categories.get(self.category, "N/A")

    def get_subcategory(self):
        return self.sub_category or ""

    def get_status(self):
        if self.status:
            return self.status.name
        else:
            return None

    def get_address(self):
        if self.subscription_product and self.subscription_product.address:
            return self.subscription_product.address.address_1
        elif self.subscription:
            return self.subscription.get_address_by_priority()
        else:
            return None

    def mark_solved(self, answer_2):
        self.status = IssueStatus.objects.get(slug=settings.ISSUE_STATUS_SOLVED)
        self.closing_date = date.today()
        if answer_2:
            if self.answer_2:
                self.answer_2 = "{}\n\n{}".format(self.answer_2, answer_2)
            else:
                self.answer_2 = answer_2
        self.save()

    def set_status(self, slug):
        try:
            self.status = IssueStatus.objects.get(slug=slug)
        except IssueStatus.DoesNotExist:
            return None
        else:
            self.save()

    def activity_count(self):
        return self.activity_set.count()

    def get_assigned_to(self):
        if self.assigned_to:
            return self.assigned_to.username
        else:
            return None

    def get_answer_1(self):
        answers = dict(ISSUE_ANSWERS)
        return answers.get(self.answer_1, "N/A")

    def __str__(self):
        return str(
            _(
                "Issue of category {} for {} with status {}".format(
                    self.get_category(), self.contact.name, self.get_status()
                )
            )
        )


class ScheduledTask(models.Model):
    """
    Description: This is used to execute certain tasks in the future, it replaces events
    """

    contact = models.ForeignKey("core.Contact", on_delete=models.CASCADE, verbose_name=_("Contact"))
    category = models.CharField(max_length=2, choices=SCHEDULED_TASK_CATEGORIES, verbose_name=_("Type"))
    address = models.ForeignKey(
        "core.Address", on_delete=models.CASCADE, verbose_name=_("Address"), null=True, blank=True
    )
    completed = models.BooleanField(default=False, verbose_name=_("Completed"))
    execution_date = models.DateField(verbose_name=_("Date of execution"))

    subscription = models.ForeignKey("core.Subscription", on_delete=models.CASCADE, blank=True, null=True)
    subscription_products = models.ManyToManyField("core.SubscriptionProduct")

    creation_date = models.DateField(auto_now_add=True, verbose_name=_("Creation date"))
    modification_date = models.DateField(auto_now=True, verbose_name=_("Modification date"), blank=True, null=True)
    ends = models.ForeignKey("support.ScheduledTask", blank=True, null=True, on_delete=models.SET_NULL)
    label_message = models.CharField(max_length=40, blank=True, null=True)
    special_instructions = models.TextField(blank=True, null=True)
    history = HistoricalRecords()

    def get_category(self):
        categories = dict(SCHEDULED_TASK_CATEGORIES)
        return categories.get(self.category, "N/A")

    class Meta:
        pass


class IssueStatus(models.Model):
    name = models.CharField(max_length=60)
    slug = AutoSlugField(populate_from="name", always_update=True, null=True, blank=True)
    category = models.CharField(max_length=2, blank=True, null=True, choices=ISSUE_CATEGORIES)

    def __str__(self):
        return self.name

    def natural_key(self):
        return (self.name, self.slug)

    class Meta:
        ordering = ["category", "name"]


class IssueSubcategory(models.Model):
    name = models.CharField(max_length=60)
    slug = AutoSlugField(populate_from="name", always_update=True, null=True, blank=True)
    category = models.CharField(max_length=2, blank=True, null=True, choices=ISSUE_CATEGORIES)

    def __str__(self):
        return self.name

    def natural_key(self):
        return (self.name, self.slug)

    class Meta:
        ordering = ["category", "name"]


class SalesRecord(models.Model):
    """
    Description: This model is used to store the sales records of the contacts, and the seller who made the sale.
    It stores all the products that were sold to the contact, the seller, the date of the sale, and
    the subscription.
    """

    class SALE_TYPE(models.TextChoices):
        FULL = "F", _("Full")
        PARTIAL = "P", _("Partial")

    seller = models.ForeignKey("support.Seller", on_delete=models.CASCADE, verbose_name=_("Seller"))
    subscription = models.ForeignKey("core.Subscription", on_delete=models.CASCADE, verbose_name=_("Subscription"))
    date_time = models.DateTimeField(auto_now_add=True, verbose_name=_("Date and time"))
    products = models.ManyToManyField("core.Product", verbose_name=_("Products"))
    # This is the price at the moment of the sale, because it can change in the future.
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Price"))
    sale_type = models.CharField(max_length=1, choices=SALE_TYPE.choices, default=SALE_TYPE.FULL)
    campaign = models.ForeignKey("core.Campaign", on_delete=models.CASCADE, verbose_name=_("Campaign"), null=True)
    commission_for_payment_type = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Commission for payment type"), default=0
    )
    commission_for_products_sold = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Commission for products sold"), default=0
    )
    commission_for_subscription_frequency = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Commission for subscription frequency"), default=0
    )

    class Meta:
        verbose_name = _("Sales record")
        verbose_name_plural = _("Sales records")
        ordering = ["-date_time"]

    def __str__(self):
        return f"{self.seller.name} - {self.subscription.contact.name} - {self.date_time}"

    def show_products(self):
        return ", ".join([p.name for p in self.products.all()])

    show_products.short_description = _("Products")

    def show_products_per_line(self):
        # Show an html list of products
        return mark_safe("<br>".join([p.name for p in self.products.all()]))

    def get_contact(self):
        return self.subscription.contact

    get_contact.short_description = _("Contact")

    def set_generic_seller(self):
        self.seller = Seller.objects.get(name=settings.GENERIC_SELLER_NAME)
        self.save()

    def add_products(self) -> None:
        product_list = self.subscription.product_summary_list()
        self.products.add(*product_list)

    def set_commission_for_products_sold(self, save=False) -> None:
        # For amount of products sold. Doesn't save unless specified
        if hasattr(settings, "SELLER_COMMISSION_PRODUCTS_COUNT"):
            products_count = self.products.filter(type="S").count()
            if hasattr(settings, "SPECIAL_PRODUCT_FOR_COMMISSION_SLUG"):
                special_product_slug = settings.SPECIAL_PRODUCT_FOR_COMMISSION_SLUG
                if self.products.filter(slug=special_product_slug).exists():
                    products_count += 1
            max_count = max(settings.SELLER_COMMISSION_PRODUCTS_COUNT.keys())
            if products_count > max_count:
                products_count = max_count
            self.commission_for_products_sold = settings.SELLER_COMMISSION_PRODUCTS_COUNT.get(products_count, 0)
            if save:
                self.save()

    def set_commission_for_payment_type(self, save=False) -> None:
        # For payment type
        if hasattr(settings, "SELLER_COMMISSION_PAYMENT_TYPE"):
            payment_type = self.subscription.payment_type
            self.commission_for_payment_type = settings.SELLER_COMMISSION_PAYMENT_TYPE.get(payment_type, 0)
            if save:
                self.save()

    def set_commission_for_subscription_frequency(self, save=False) -> None:
        # For subscription frequency
        if hasattr(settings, "SELLER_COMMISSION_SUBSCRIPTION_FREQUENCY"):
            frequency = self.subscription.frequency
            self.commission_for_subscription_frequency = settings.SELLER_COMMISSION_SUBSCRIPTION_FREQUENCY.get(
                frequency, 0
            )
            if save:
                self.save()

    def set_commissions(self) -> None:
        self.set_commission_for_products_sold(self)
        self.set_commission_for_payment_type(self)
        self.set_commission_for_subscription_frequency(self)
        self.save()
