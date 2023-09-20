# coding=utf-8


from django.http import HttpResponseRedirect
from django.contrib.admin import SimpleListFilter
from django.utils.translation import gettext_lazy as _
from django.contrib import admin
from django.urls import resolve, reverse
from leaflet.admin import LeafletGeoAdmin

from taggit.models import TaggedItem

# from tabbed_admin import TabbedModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from community.models import ProductParticipation, Supporter
from .models import (
    Subscription,
    Contact,
    Product,
    Address,
    Variable,
    Campaign,
    Institution,
    Ocupation,
    Subtype,
    Activity,
    ContactProductHistory,
    ContactCampaignStatus,
    PriceRule,
    SubscriptionProduct,
    SubscriptionNewsletter,
    DynamicContactFilter,
    ProductBundle,
    AdvancedDiscount,
    DoNotCallNumber,
    EmailReplacement,
)
from .forms import SubscriptionAdminForm, ContactAdminForm


class TaggitListFilter(SimpleListFilter):
    """
    A custom filter class that can be used to filter by taggit tags in the admin.
    """

    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _("tags")

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "tag"

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each tuple is the coded value
        for the option that will appear in the URL query. The second element is the
        human-readable name for the option that will appear in the right sidebar.
        """
        list = []
        tags = TaggedItem.tags_for(model_admin.model)
        for tag in tags:
            list.append((tag.name, _(tag.name)))
        return list

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value provided in the query
        string and retrievable via `self.value()`.
        """
        if self.value():
            return queryset.filter(tags__name__in=[self.value()])


class SubscriptionProductInline(admin.TabularInline):
    model = SubscriptionProduct
    fields = (
        ("product", "copies", "address"),
        ("route", "order", "label_contact", "seller"),
        ("has_envelope", "active"),
    )
    raw_id_fields = ["route", "label_contact", "seller"]
    extra = 1

    def get_parent_object_from_request(self, request):
        """
        Returns the parent object from the request or None.
        Note that this only works for Inlines, because the `parent_model`
        is not available in the regular admin.ModelAdmin as an attribute.
        """
        resolved = resolve(request.path_info)
        if resolved.kwargs:
            return self.parent_model.objects.get(pk=resolved.kwargs["object_id"])
        return None

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        field = super(SubscriptionProductInline, self).formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "address":
            if request:
                contact = self.get_parent_object_from_request(request).contact
                field.queryset = field.queryset.filter(contact=contact)
        return field


def response_add_or_change_next_url(request, obj):
    """Returns the next_url to be used in the response_add and response_change method redefinitions"""
    opts = obj._meta
    reverse_begin = "admin:%s_%s_" % (opts.app_label, opts.model_name)
    if "_continue" in request.POST:
        return reverse(reverse_begin + "change", args=(obj.id,))
    return reverse(reverse_begin + ("add" if "_addanother" in request.POST else "changelist"))


def default_newsletters_dialog_redirect(request, obj, contact_id_attr_name):
    """Returns the redirect to be used for the default newsletters dialog page"""
    return HttpResponseRedirect(
        "%s?next_page=%s"
        % (
            reverse("default_newsletters_dialog", kwargs={"contact_id": getattr(obj, contact_id_attr_name)}),
            response_add_or_change_next_url(request, obj),
        )
    )


@admin.register(Subscription)
class SubscriptionAdmin(SimpleHistoryAdmin):
    model = Subscription
    inlines = [SubscriptionProductInline]
    form = SubscriptionAdminForm
    fieldsets = (
        ("Contact data", {"fields": ("contact",)}),
        (
            "Subscription data",
            {
                "fields": (
                    ("active", "type"),
                    ("start_date", "end_date"),
                    ("next_billing", "payment_type"),
                    ("balance", "frequency"),
                    ("status", "send_bill_copy_by_email", "send_pdf"),
                    ("payment_certificate"),
                    ("updated_from", "campaign"),
                )
            },
        ),
        (
            "Billing data",
            {
                "classes": ("collapse",),
                "fields": (
                    (
                        "billing_name",
                        "billing_address",
                    ),
                    ("billing_phone", "billing_email"),
                    ("billing_id_doc",),
                    ("rut",),
                ),
            },
        ),
        (
            "Inactivity",
            {
                "classes": ("collapse",),
                "fields": (
                    ("inactivity_reason",),
                    ("unsubscription_channel", "unsubscription_type"),
                    "unsubscription_products",
                    "unsubscription_reason",
                    "unsubscription_addendum",
                    ("unsubscription_date", "unsubscription_manager"),
                ),
            },
        ),
    )
    list_display = ("contact", "active", "payment_type", "campaign", "product_summary")
    list_editable = ("active", "payment_type")
    list_filter = ("campaign", "active", "payment_type")
    readonly_fields = ("contact", "edit_products_field", "campaign", "updated_from", "unsubscription_products")

    def response_add(self, request, obj, post_url_continue=None):
        if obj.contact.offer_default_newsletters_condition():
            return default_newsletters_dialog_redirect(request, obj, "contact_id")
        return super(SubscriptionAdmin, self).response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if obj.contact.offer_default_newsletters_condition():
            return default_newsletters_dialog_redirect(request, obj, "contact_id")
        return super(SubscriptionAdmin, self).response_change(request, obj)

    class Media:
        pass


class AddressInline(admin.StackedInline):
    raw_id_fields = "geo_ref_address"
    model = Address
    extra = 0


class ProductParticipationInline(admin.StackedInline):
    model = ProductParticipation
    fields = ("product", "description")
    verbose_name_plural = "participaciones"
    extra = 1


class SubscriptionNewsletterInline(admin.TabularInline):
    model = SubscriptionNewsletter
    fields = ("product", "active")
    verbose_name_plural = _("Newsletters")
    extra = 1


class SupporterInline(admin.StackedInline):
    model = Supporter
    fields = ("support", "description")
    verbose_name_plural = _("Supporters")
    extra = 1


@admin.register(Contact)
class ContactAdmin(SimpleHistoryAdmin):
    form = ContactAdminForm
    fieldsets = (
        (None, {"fields": (("name", "tags", "subtype"),)}),
        (
            None,
            {
                "fields": (
                    ("email", "no_email", "id_document"),
                    ("phone", "mobile", "work_phone"),
                    ("gender", "education"),
                    ("birthdate", "private_birthdate"),
                    ("protected",),
                    "protection_reason",
                    "notes",
                )
            },
        ),
    )
    list_display = ("id", "name", "id_document", "subtype", "tag_list")
    raw_id_fields = "subtype"
    list_filter = ("subtype", TaggitListFilter)
    ordering = ("id",)
    raw_id_fields = ("subtype", "referrer")

    def get_queryset(self, request):
        return super(ContactAdmin, self).get_queryset(request).prefetch_related("tags")

    def tag_list(self, obj):
        return ", ".join(o.name for o in obj.tags.all())

    def response_add(self, request, obj, post_url_continue=None):
        if obj.offer_default_newsletters_condition():
            return default_newsletters_dialog_redirect(request, obj, "id")
        return super(ContactAdmin, self).response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if obj.offer_default_newsletters_condition():
            return default_newsletters_dialog_redirect(request, obj, "id")
        return super(ContactAdmin, self).response_change(request, obj)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # TODO: validations, for example target_product only makes sense on discount products
    list_display = (
        "id",
        "name",
        "price",
        "active",
        "type",
        "weekday",
        "slug",
        "offerable",
        "billing_priority",
        "edition_frequency",
        "temporary_discount_months",
    )
    list_editable = [
        "name",
        "type",
        "price",
        "weekday",
        "billing_priority",
        "offerable",
        "edition_frequency",
        "temporary_discount_months",
    ]
    readonly_fields = ("slug", )


class PlanAdmin(admin.ModelAdmin):
    pass


@admin.register(Address)
class AddressAdmin(SimpleHistoryAdmin, LeafletGeoAdmin):
    raw_id_fields = ("contact", "geo_ref_address")


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date")
    list_editable = ("start_date", "end_date")


@admin.register(Ocupation)
class OcupationAdmin(admin.ModelAdmin):
    pass


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    pass


@admin.register(Variable)
class VariableAdmin(admin.ModelAdmin):
    list_display = ("name", "value", "type")


@admin.register(Subtype)
class SubtypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Activity)
class ActivityAdmin(SimpleHistoryAdmin):
    raw_id_fields = ["contact", "issue", "seller", "campaign"]
    date_hierarchy = "datetime"
    list_display = ("id", "contact", "seller", "datetime", "activity_type", "campaign", "seller", "status")
    list_filter = ("seller", "campaign", "status")
    search_fields = ("contact__id", "contact__name")


@admin.register(ContactProductHistory)
class ContactProductHistoryAdmin(admin.ModelAdmin):
    list_display = ("contact", "product", "date", "status")
    search_fields = ("contact__name",)
    raw_id_fields = ("contact", "subscription")


@admin.register(ContactCampaignStatus)
class ContactCampaignStatusAdmin(admin.ModelAdmin):
    raw_id_fields = ["contact"]
    list_display = (
        "contact",
        "campaign",
        "status",
        "seller",
        "times_contacted",
        "date_created",
        "date_assigned",
        "last_action_date",
    )
    readonly_fields = ("date_created", "date_assigned", "last_action_date")
    list_filter = ("campaign", "status", "seller")
    search_fields = ("contact__name",)


@admin.register(PriceRule)
class PriceRuleAdmin(SimpleHistoryAdmin):
    list_display = ("id", "active", "priority", "amount_to_pick", "mode", "resulting_product")
    list_editable = ("active", "priority")
    ordering = ("priority",)


@admin.register(SubscriptionProduct)
class SubscriptionProductAdmin(admin.ModelAdmin):
    # TODO: improve get_subscription_active UX
    list_display = (
        "subscription_id",
        "get_subscription_active",
        "active",
        "product",
        "copies",
        "address",
        "route",
        "order",
        "seller",
    )
    raw_id_fields = ("subscription", "address", "label_contact")


@admin.register(EmailReplacement)
class EmailReplacementAdmin(admin.ModelAdmin):
    list_display = ("domain", "replacement", "status")
    list_editable = ("status", )
    list_filter = ("status", "replacement")
    search_fields = ("domain", "replacement")


admin.site.register(DynamicContactFilter)
admin.site.register(ProductBundle)
admin.site.register(AdvancedDiscount)
admin.site.register(DoNotCallNumber)
