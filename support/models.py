# coding=utf-8

from __future__ import unicode_literals

from datetime import date

from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from autoslug import AutoSlugField
from core.models import Campaign

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
    user = models.ForeignKey(User, blank=True, null=True)
    old_pk = models.PositiveIntegerField(blank=True, null=True, db_index=True)

    def __unicode__(self):
        return self.name

    def get_contact_count(self):
        return self.contact_set.all().count()

    def get_unfinished_campaigns(self):
        seller_campaigns = Campaign.objects.filter(
            contactcampaignstatus__seller=self,
            contactcampaignstatus__status__lt=4,
        ).distinct()
        return seller_campaigns

    def get_campaigns_by_status(self, status):
        seller_campaigns = Campaign.objects.filter(
            contactcampaignstatus__seller=self,
            contactcampaignstatus__status__in=status,
        ).distinct()
        return seller_campaigns

    class Meta:
        verbose_name = _("seller")
        verbose_name_plural = _("sellers")
        ordering = ["name"]


class Issue(models.Model):
    """
    Description: Contains data about things that our contacts want from us.
    """

    date_created = models.DateField(auto_now_add=True)
    contact = models.ForeignKey("core.Contact", verbose_name=_("Contact"))
    date = models.DateField(default=date.today, verbose_name=_("Date"))
    category = models.CharField(
        max_length=1, blank=True, null=True, choices=ISSUE_CATEGORIES
    )
    subcategory = models.CharField(
        max_length=3, blank=True, null=True, choices=ISSUE_SUBCATEGORIES
    )
    inside = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)
    manager = models.ForeignKey(
        "auth.User", blank=True, null=True, related_name="issue_manager"
    )  # User who created the issue. Non-editable
    assigned_to = models.ForeignKey(
        "auth.User", blank=True, null=True, related_name="issue_assigned"
    )  # Editable, assigned to which user
    progress = models.TextField(blank=True, null=True)
    answer_1 = models.CharField(
        max_length=2, blank=True, null=True, choices=ISSUE_ANSWERS
    )
    answer_2 = models.TextField(blank=True, null=True)
    status = models.ForeignKey('support.IssueStatus', blank=True, null=True, on_delete=models.SET_NULL)
    end_date = models.DateField(blank=True, null=True)
    next_action_date = models.DateField(blank=True, null=True)
    closing_date = models.DateField(blank=True, null=True)
    copies = models.PositiveSmallIntegerField(default=0)
    # Optional attributes
    subscription_product = models.ForeignKey(
        "core.SubscriptionProduct", null=True, blank=True
    )
    subscription = models.ForeignKey("core.Subscription", null=True, blank=True)
    product = models.ForeignKey("core.Product", null=True, blank=True)

    class Meta:
        pass

    def get_category(self):
        categories = dict(ISSUE_CATEGORIES)
        return categories.get(self.category, "N/A")

    def get_subcategory(self):
        subcategories = dict(ISSUE_SUBCATEGORIES)
        return subcategories.get(self.subcategory, "N/A")

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

    def mark_solved(self):
        self.status = IssueStatus.objects.get(slug=settings.SOLVED_ISSUE_STATUS_SLUG)
        self.closing_date = date.today()
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

    def __unicode__(self):
        return "Issue of category {} for {} with status {}".format(
            self.get_category(), self.contact.name, self.get_status()
        )


class ScheduledTask(models.Model):
    """
    Description: This is used to execute certain tasks in the future, it replaces events
    """

    contact = models.ForeignKey("core.Contact", verbose_name=_("Contact"))
    category = models.CharField(
        max_length=2, choices=SCHEDULED_TASK_CATEGORIES, verbose_name=_("Type")
    )
    address = models.ForeignKey(
        "core.Address", verbose_name=_("Address"), null=True, blank=True
    )
    completed = models.BooleanField(default=False, verbose_name=_("Completed"))
    execution_date = models.DateField(verbose_name=_("Date of execution"))

    subscription = models.ForeignKey("core.Subscription", blank=True, null=True)
    subscription_products = models.ManyToManyField("core.SubscriptionProduct")

    creation_date = models.DateField(auto_now_add=True, verbose_name=_("Creation date"))
    modification_date = models.DateField(
        auto_now=True, verbose_name=_("Modification date"), blank=True, null=True
    )
    ends = models.ForeignKey("support.ScheduledTask", blank=True, null=True, on_delete=models.SET_NULL)

    def get_category(self):
        categories = dict(SCHEDULED_TASK_CATEGORIES)
        return categories.get(self.category, "N/A")

    class Meta:
        pass


class IssueStatus(models.Model):
    name = models.CharField(max_length=60)
    slug = AutoSlugField(populate_from='name', always_update=True, null=True, blank=True)

    def __unicode__(self):
        return self.name

    def natural_key(self):
        return (self.name, self.slug)

    class Meta:
        pass
