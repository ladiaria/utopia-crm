# coding=utf-8
from __future__ import unicode_literals

from django.contrib import admin

from .forms import SellerForm
from .models import *


class SellerAdmin(admin.ModelAdmin):
    list_display = ["name", "internal", "user"]
    ordering = ["-internal", "name"]
    raw_id_fields = ["user"]
    form = SellerForm


class IssueAdmin(admin.ModelAdmin):
    raw_id_fields = ["contact", "address_1", "address_2", "subscription"]


class ScheduledTaskAdmin(admin.ModelAdmin):
    list_display = ["contact", "execution_date", "category", "completed"]
    readonly_fields = ["subscription_products"]
    ordering = ["-execution_date"]
    raw_id_fields = ["address", "issue", "contact", "subscription"]


admin.site.register(ScheduledTask, ScheduledTaskAdmin)
admin.site.register(Issue, IssueAdmin)
admin.site.register(Seller, SellerAdmin)
