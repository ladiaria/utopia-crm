# coding=utf-8

from __future__ import unicode_literals

from datetime import date

from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

from core.models import Campaign

from support.choices import (
    ISSUE_CATEGORIES,
    ISSUE_ANSWERS,
    ISSUE_STATUS,
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
    address_1 = models.ForeignKey(
        "core.Address", blank=True, null=True, related_name="issue_address_1"
    )
    address_2 = models.ForeignKey(
        "core.Address", blank=True, null=True, related_name="issue_address_2"
    )
    route = models.ForeignKey(
        "logistics.Route", blank=True, null=True
    )  # Only for logistics
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
    status = models.CharField(
        max_length=1, blank=True, null=True, choices=ISSUE_STATUS, default="P"
    )
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
        statuses = dict(ISSUE_STATUS)
        return statuses.get(self.status, "N/A")

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
    issue = models.ForeignKey(Issue, blank=True, null=True)
    execution_date = models.DateField(verbose_name=_("Date of execution"))

    subscription = models.ForeignKey("core.Subscription", blank=True, null=True)
    subscription_products = models.ManyToManyField("core.SubscriptionProduct")

    creation_date = models.DateField(auto_now_add=True, verbose_name=_("Creation date"))
    modification_date = models.DateField(
        auto_now=True, verbose_name=_("Modification date"), blank=True, null=True
    )

    def get_category(self):
        categories = dict(SCHEDULED_TASK_CATEGORIES)
        return categories.get(self.category, "N/A")

    class Meta:
        pass
