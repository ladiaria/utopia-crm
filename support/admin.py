# coding=utf-8
from __future__ import unicode_literals

from django.contrib import admin

from .forms import SellerForm
from .models import ScheduledTask, Issue, Seller, IssueStatus


class SellerAdmin(admin.ModelAdmin):
    list_display = ["name", "internal", "user"]
    ordering = ["-internal", "name"]
    raw_id_fields = ["user"]
    form = SellerForm


class IssueAdmin(admin.ModelAdmin):
    list_display = ["id", "contact", "status"]
    raw_id_fields = [
        "contact", "subscription", "manager", "assigned_to", "product",
        "subscription_product"
    ]


class ScheduledTaskAdmin(admin.ModelAdmin):
    list_display = ["contact", "execution_date", "category", "completed"]
    readonly_fields = ["subscription_products"]
    ordering = ["-execution_date"]
    raw_id_fields = ["address", "ends", "contact", "subscription"]


class IssueStatusAdmin(admin.ModelAdmin):
    list_editable = ["category"]
    list_display = ["name", "slug", "category"]
    readonly_fields = ["slug"]


admin.site.register(ScheduledTask, ScheduledTaskAdmin)
admin.site.register(Issue, IssueAdmin)
admin.site.register(Seller, SellerAdmin)
admin.site.register(IssueStatus, IssueStatusAdmin)
