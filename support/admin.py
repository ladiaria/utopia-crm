# coding=utf-8


from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from simple_history.admin import SimpleHistoryAdmin

from .forms import SellerForm
from .models import (
    ScheduledTask,
    Issue,
    Seller,
    IssueStatus,
    IssueSubcategory,
    SalesRecord,
    SellerConsoleAction,
    IssueResolution,
)


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


@admin.register(IssueResolution)
class IssueResolutionAdmin(admin.ModelAdmin):
    list_editable = ["subcategory"]
    list_display = ["name", "slug", "subcategory"]


@admin.register(SalesRecord)
class SalesRecordAdmin(admin.ModelAdmin):
    list_display = [
        "date_time",
        "seller",
        "get_contact",
        "sale_type",
        "price",
        "total_commission_value",
        "can_be_commissioned",
        "campaign",
        "show_products",
    ]
    list_filter = ["sale_type", "can_be_commissioned", "seller", "campaign"]
    raw_id_fields = ["subscription"]
    search_fields = ["subscription__contact__name", "subscription__contact__id", "seller__name"]
    date_hierarchy = "date_time"
    ordering = ["-date_time"]
    list_per_page = 50
    list_max_show_all = 200
    readonly_fields = ["date_time", "products", "price", "seller", "subscription", "show_products_per_line"]
    fieldsets = [
        (None, {"fields": ["seller", "subscription", "date_time", "campaign", "sale_type"]}),
        (_("Products & price"), {"fields": ["show_products_per_line", "price"]}),
        (
            _("Commissions"),
            {
                "fields": [
                    "can_be_commissioned",
                    "commission_for_payment_type",
                    "commission_for_products_sold",
                    "commission_for_subscription_frequency",
                    "total_commission_value",
                ]
            },
        ),
    ]
    save_on_top = True


@admin.register(SellerConsoleAction)
class SellerConsoleActionAdmin(admin.ModelAdmin):
    list_display = ["slug", "name", "action_type", "campaign_status", "campaign_resolution"]
    list_display_links = ["slug"]
    list_editable = ["name", "action_type", "campaign_status", "campaign_resolution"]
