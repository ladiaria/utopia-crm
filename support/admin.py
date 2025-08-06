# coding=utf-8


from django.contrib import admin

from simple_history.admin import SimpleHistoryAdmin

from .forms import SellerForm
from .models import ScheduledTask, Issue, Seller, IssueStatus, IssueSubcategory, SalesRecord, SellerConsoleAction


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = ["name", "internal", "user"]
    ordering = ["-internal", "name"]
    raw_id_fields = ["user"]
    form = SellerForm


@admin.register(Issue)
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


@admin.register(ScheduledTask)
class ScheduledTaskAdmin(SimpleHistoryAdmin):
    list_display = ["contact", "execution_date", "category", "completed"]
    readonly_fields = ["subscription_products"]
    ordering = ["-execution_date"]
    raw_id_fields = ["address", "ends", "contact", "subscription"]


@admin.register(IssueStatus)
class IssueStatusAdmin(admin.ModelAdmin):
    list_editable = ["category"]
    list_display = ["name", "slug", "category"]
    readonly_fields = ["slug"]


@admin.register(IssueSubcategory)
class IssueSubcategoryAdmin(admin.ModelAdmin):
    list_editable = ["category"]
    list_display = ["name", "slug", "category"]
    readonly_fields = ["slug"]


@admin.register(SalesRecord)
class SalesRecordAdmin(admin.ModelAdmin):
    list_display = ["date_time", "seller", "get_contact", "price", "show_products"]
    list_filter = ["date_time"]
    raw_id_fields = ["subscription"]
    search_fields = ["contact__name"]
    date_hierarchy = "date_time"
    ordering = ["-date_time"]
    list_per_page = 50
    list_max_show_all = 100
    readonly_fields = ["date_time", "products", "price", "seller", "subscription"]
    fieldsets = [
        (None, {"fields": ["seller", "subscription", "date_time", "products", "price"]}),
    ]
    save_on_top = True
    save_as = True
    save_as_continue = True


@admin.register(SellerConsoleAction)
class SellerConsoleActionAdmin(admin.ModelAdmin):
    list_display = ["slug", "name", "action_type", "campaign_status"]
    list_display_links = ["slug"]
    list_editable = ["name", "action_type", "campaign_status"]
