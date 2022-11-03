# coding=utf-8


from django.contrib import admin

from simple_history.admin import SimpleHistoryAdmin

from .forms import SellerForm
from .models import ScheduledTask, Issue, Seller, IssueStatus, IssueSubcategory


class SellerAdmin(admin.ModelAdmin):
    list_display = ["name", "internal", "user"]
    ordering = ["-internal", "name"]
    raw_id_fields = ["user"]
    form = SellerForm


class IssueAdmin(SimpleHistoryAdmin):
    date_hierarchy = "date"
    list_display = ["id", "date", "contact", "status", "category", "sub_category"]
    raw_id_fields = [
        "contact",
        "subscription",
        "manager",
        "assigned_to",
        "product",
        "subscription_product",
        "address",
    ]
    exclude = ["subcategory"]
    list_filter = ["category", "subcategory", "status"]


class ScheduledTaskAdmin(SimpleHistoryAdmin):
    list_display = ["contact", "execution_date", "category", "completed"]
    readonly_fields = ["subscription_products"]
    ordering = ["-execution_date"]
    raw_id_fields = ["address", "ends", "contact", "subscription"]


class IssueStatusAdmin(admin.ModelAdmin):
    list_editable = ["category"]
    list_display = ["name", "slug", "category"]
    readonly_fields = ["slug"]


class IssueSubcategoryAdmin(admin.ModelAdmin):
    list_editable = ["category"]
    list_display = ["name", "slug", "category"]
    readonly_fields = ["slug"]


admin.site.register(ScheduledTask, ScheduledTaskAdmin)
admin.site.register(Issue, IssueAdmin)
admin.site.register(Seller, SellerAdmin)
admin.site.register(IssueStatus, IssueStatusAdmin)
admin.site.register(IssueSubcategory, IssueSubcategoryAdmin)
