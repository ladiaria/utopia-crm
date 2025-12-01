# coding=utf-8
from leaflet.admin import LeafletGeoAdmin
from taggit.models import TaggedItem, Tag
from taggit.admin import TagAdmin, TaggedItemInline
from simple_history.admin import SimpleHistoryAdmin

from django.conf import settings
from django.db.models.deletion import Collector
from django.http import HttpResponseRedirect
from django.contrib.admin import SimpleListFilter
from django.utils.translation import gettext_lazy as _
from django.contrib import admin
from django.contrib.messages import constants as messages
from django.urls import resolve, reverse
from django.forms import ValidationError

from community.models import ProductParticipation, Supporter
from invoicing.models import Invoice
from support.models import Issue
from .utils import logistics_is_installed, mercadopago_sdk
from .models import (
    Subscription,
    IdDocumentType,
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
    EmailBounceActionLog,
    MailtrainList,
    Country,
    State,
    ActivityTopic,
    ActivityResponse,
    ProductSubscriptionPeriod,
    TermsAndConditions,
    TermsAndConditionsProduct,
    PersonType,
    BusinessEntityType,
    PaymentMethod,
    PaymentType,
    City,
)
from .forms import SubscriptionAdminForm, ContactAdminForm


# unregister default TagAdmin to remove inlines (avoid timeout when many taggetitems), register it again changed
if Tag in admin.site._registry:
    admin.site.unregister(Tag)


class UtopiaTagAdmin(TagAdmin):
    inlines = [i for i in TagAdmin.inlines if i != TaggedItemInline]
    list_display = TagAdmin.list_display + ["item_count"]

    def item_count(self, instance):
        return instance.taggit_taggeditem_items.count()


admin.site.register(Tag, UtopiaTagAdmin)


# filters by tag
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
        ("order", "label_contact", "seller"),
        ("has_envelope", "active"),
        ("original_datetime")
    )
    raw_id_fields = ["label_contact", "seller"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if logistics_is_installed():
            self.fields = list(self.fields)
            self.fields[1] = ("route", "order", "label_contact", "seller")
            self.raw_id_fields.insert(0, "route")

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
            if request and self.get_parent_object_from_request(request):
                contact = self.get_parent_object_from_request(request).contact
                field.queryset = field.queryset.filter(contact=contact)
            else:
                field.queryset = field.queryset.none()
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


def contact_is_safe_to_delete(contact, ignore_movable=False, print_unsafe=False):
    if contact.has_active_subscription():
        if print_unsafe:
            print(f"contact_is_safe_to_delete (not safe): active subscriptions={contact.get_active_subscriptions()}")
        return False

    non_relevant_data_max_amounts = {
        Contact: 1,
        ContactCampaignStatus: 100,
        Address: 1,
        SubscriptionNewsletter: 20,
    }
    movable = [Tag, Address, Subscription, Invoice, Activity, Issue, ContactProductHistory]

    collector = Collector(using="default")
    collector.collect([contact])
    collector_data = collector.data
    safety = True
    for key in collector_data:
        key_count = len(collector_data[key])
        if key not in non_relevant_data_max_amounts or key_count > non_relevant_data_max_amounts[key]:
            if not ignore_movable or key not in movable:
                safety = False
                if print_unsafe:
                    print(f"contact_is_safe_to_delete, collector data item: {key} {key_count}")
                break
    return safety


@admin.register(Subscription)
class SubscriptionAdmin(SimpleHistoryAdmin):
    model = Subscription
    inlines = [SubscriptionProductInline]
    form = SubscriptionAdminForm

    def get_form(self, request, obj=None, **kwargs):
        # Store the request as an attribute of the form
        form = super().get_form(request, obj, **kwargs)
        form.request = request
        return form

    fieldsets = (
        (_("Contact data"), {"fields": ("contact",)}),
        (
            _("Subscription data"),
            {
                "fields": (
                    ("active", "type"),
                    ("start_date", "end_date"),
                    ("next_billing", "payment_type"),
                    ("balance", "frequency"),
                    ("status", "send_bill_copy_by_email", "send_pdf"),
                    ("payment_certificate"),
                    ("updated_from", "campaign"),
                    ("free_subscription_requested_by"),
                    ("validated", "validated_by", "validated_date"),
                    ("renewal_type", "purchase_date"),
                )
            },
        ),
        (
            _("Corporate subscription data"),
            {
                "fields": (("number_of_subscriptions", "override_price"),),
            },
        ),
        (
            _("Billing data"),
            {
                "classes": ("collapse",),
                "fields": (
                    ("billing_name", "billing_address"),
                    ("billing_phone", "billing_email"),
                    ("billing_id_doc",),
                    ("rut",),
                ),
            },
        ),
        (
            _("Inactivity"),
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
    raw_id_fields = ("contact",)
    readonly_fields = (
        "edit_products_field",
        "campaign",
        "updated_from",
        "unsubscription_products",
        "validated_by",
    )

    def save_model(self, request, obj, form, change):
        try:
            super().save_model(request, obj, form, change)
        except Exception as e:
            self.message_user(request, str(e), level=messages.WARNING)

    def get_readonly_fields(self, request, obj):
        readonly_fields = super().get_readonly_fields(request, obj)
        if obj:
            readonly_fields += ("contact",)
        return readonly_fields

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
        (
            _("Contact details"),
            {
                "fields": (
                    ("name", "last_name"),
                    "tags",
                    ("email", "no_email"),
                    ("id_document_type", "id_document"),
                    ("phone", "mobile"),
                    "work_phone",
                    ("gender", "education", "ranking"),
                    # TODO: include "occupation" right here after its name got fixed from single "c" to "cc"
                    ("birthdate", "private_birthdate"),
                    "notes",
                    "institution",
                    ("protected", "protection_reason"),
                    ("person_type", "business_entity_type"),
                ),
            },
        ),
    )
    list_display = ("id", "get_full_name", "get_full_id_document", "email", "tag_list")
    raw_id_fields = (
        "subtype",
        "referrer",
        "institution",
    )  # TODO: add "occupation" after its name got fixed from single "c" to "cc"
    list_filter = (TaggitListFilter,)
    search_fields = ("name", "last_name", "email", "id_document")
    ordering = ("id",)

    class Media:
        # jquery loaded again (admin uses custom js namespaces and we use jquery-ui)
        js = (
            'admin-lte/plugins/jquery/jquery%s.js' % ("" if settings.DEBUG else ".min"),
            'admin-lte/plugins/jquery-ui/jquery-ui%s.js' % ("" if settings.DEBUG else ".min"),
        )

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

    def change_view(self, request, object_id, form_url='', extra_context=None):
        result = None
        try:
            result = super().change_view(request, object_id, form_url, extra_context)
        except ValidationError as ve:
            self.message_user(request, ve.args[0], level=messages.ERROR)
            result = HttpResponseRedirect(request.get_full_path())
        return result

    def save_model(self, request, obj, form, change):
        # rising a flag (only on change) to skip call Contact.clean method again (called already in form validation)
        skip_clean_set = False
        if change and not getattr(obj, "_skip_clean", False):
            obj._skip_clean, skip_clean_set = True, True
        try:
            super().save_model(request, obj, form, change)
        except ValidationError:
            if skip_clean_set:
                del obj._skip_clean
            raise
        else:
            if skip_clean_set:
                del obj._skip_clean

    def delete_model(self, request, obj):
        try:
            return super().delete_model(request, obj)
        except Exception as e:
            self.message_user(request, "CMS sync: " + str(e), level=messages.WARNING)


class TermsAndConditionsProductInline(admin.TabularInline):
    model = TermsAndConditionsProduct
    fields = ("terms_and_conditions", "date")
    extra = 1


def build_mp_plan_data(obj, application_id):
    back_url = getattr(settings, "MERCADOPAGO_PLAN_BACK_URL", None)
    currency_id = getattr(settings, "MERCADOPAGO_PLAN_DEFAULT_CURRENCY", None)
    assert back_url and currency_id, (
        _("Settings variables MERCADOPAGO_PLAN_BACK_URL and MERCADOPAGO_PLAN_DEFAULT_CURRENCY must be set")
    )
    return {
        "reason": obj.name,
        "auto_recurring": {
            "frequency": obj.duration_months,
            "currency_id": currency_id,
            "frequency_type": "months",
            "transaction_amount": "%.2f" % obj.price,
        },
        "application_id": application_id,
        "payment_methods_allowed": getattr(
            settings,
            "MERCADOPAGO_PAYMENT_METHODS_ALLOWED",
            {
                'payment_types': [{'id': 'credit_card'}, {'id': 'debit_card'}],
                'payment_methods': [{'id': 'master'}, {'id': 'visa'}, {'id': 'debvisa'}, {'id': 'debmaster'}],
            },
        ),
        "back_url": back_url,
    }


def mp_product_sync(obj, disable_mp_plan=False):
    """
    Syncs the product with a MercadoPago Plan object for "app integration" mercadopago mode.
    The sync is performed only if:
    - MERCADOPAGO_PRODUCT_SYNC_ENABLED is True (default: False)
    - mercadopago_access_token() is not empty
    - The "app integration" mode in MercadoPago is used, the app id will be obtained from the access token
    - if MERCADOPAGO_PRODUCT_SYNC_CMS_SYNC_REQUIRED is True (default: False), obj.cms_subscription_type must be set
    """
    if getattr(settings, "MERCADOPAGO_PRODUCT_SYNC_ENABLED", False):
        if getattr(settings, "MERCADOPAGO_PRODUCT_SYNC_CMS_SYNC_REQUIRED", False) and not obj.cms_subscription_type:
            return
        sdk, app_id = mercadopago_sdk()
        if disable_mp_plan:
            if not obj.mercadopago_id:
                # we only can disable plans already linked to a product in CRM
                return
            try:
                sdk.plan().update(obj.mercadopago_id, {"status": "inactive"})
            except Exception as e:
                # TODO: spanish translation = "No se pudo deshabilitar el producto en MercadoPago"
                raise Exception(_("Failed to disable product in MercadoPago") + f": {e}")
        else:
            try:
                mp_data, mp_response = build_mp_plan_data(obj, app_id), ""
                if not obj.mercadopago_id:
                    # TODO: consider search by some field before creating the plan, for example the name but this can
                    #       be handled in "v2", a modal dialog to show mp's values and ask for confirmation
                    mp_response = sdk.plan().create(mp_data)
                    obj.mercadopago_id = mp_response["response"]["id"]
                    obj.save()
                else:
                    mp_response = sdk.plan().update(obj.mercadopago_id, mp_data)
            except Exception as e:
                if settings.DEBUG:
                    print(f"mp_product_sync error: {e}")
                    if mp_response:
                        print(f"MP response: {mp_response}")
                # TODO: spanish translation = "No se pudo sincronizar el producto en MercadoPago"
                raise Exception(_("Failed to sync product in MercadoPago") + f": {e}")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # Note: target_product is limited to active subscription products (type='S')
    # and is primarily used for discount products to specify which product they discount
    list_display = (
        "id",
        "name",
        "price",
        "active",
        "type",
        "weekday",
        "slug",
        "offerable",
        "target_product",
    )
    list_editable = [
        "name",
        "type",
        "price",
        "weekday",
        "offerable",
        "target_product",
    ]
    list_filter = ("active", "type", "renewal_type", "offerable", "subscription_period", "duration_months")
    readonly_fields = ("mercadopago_id",)
    raw_id_fields = ("target_product",)  # Makes it easier to see and set the value
    fieldsets = (
        (_("Information"), {"fields": ("name", "slug", "type")}),
        (
            _("Pricing & Discounts"),
            {
                "fields": (
                    "price",
                    "offerable",
                    "temporary_discount_months",
                    "renewal_type",
                    "has_implicit_discount",
                    "target_product",
                    "discount_category",
                ),
            },
        ),
        (_("Scheduling & Frequency"), {"fields": ("weekday", "subscription_period", "duration_months")}),
        (_("Billing & Priority"), {"fields": ("billing_priority", "active", "edition_frequency")}),
        (_("MercadoPago and others"), {"fields": ("mercadopago_id", "cms_subscription_type")}),
    )
    inlines = (TermsAndConditionsProductInline,)
    search_fields = ("name", "slug", "internal_code")
    # TODO: spanish translation = "No se pudo actualizar el producto en MercadoPago"
    no_mp_sync_msg_prefix = _("The product could not be updated in MercadoPago") + ": "
    actions = None
    list_display_links = ("id",)

    def delete_model(self, request, obj):
        print("delete_model", obj)
        try:
            mp_product_sync(obj, disable_mp_plan=True)
        except Exception as e:
            self.message_user(request, self.no_mp_sync_msg_prefix + str(e), level=messages.WARNING)
        super().delete_model(request, obj)

    def save_model(self, request, obj, form, change):
        try:
            mp_product_sync(obj)
        except Exception as e:
            self.message_user(request, self.no_mp_sync_msg_prefix + str(e), level=messages.WARNING)
        super().save_model(request, obj, form, change)

    class Media:
        css = {"all": ("css/product_admin.css",)}


class PlanAdmin(admin.ModelAdmin):
    pass


@admin.register(Address)
class AddressAdmin(SimpleHistoryAdmin, LeafletGeoAdmin):
    list_display = ("contact", "address_1", "city", "state", "country")
    raw_id_fields = ("contact",)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "active", "priority")
    list_editable = ("start_date", "end_date")
    search_fields = ("name",)


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


@admin.register(EmailReplacement)
class EmailReplacementAdmin(admin.ModelAdmin):
    list_display = ("domain", "replacement", "status")
    list_editable = ("status",)
    list_filter = ("status", "replacement")
    search_fields = ("domain", "replacement")


class DeleteOnlyModelAdmin(admin.ModelAdmin):
    """A delete-only modeladmin, only see and delete is allowed"""

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({'title': self.model._meta.verbose_name_plural.capitalize()})
        return super().changelist_view(request, extra_context=extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({'title': self.model._meta.verbose_name.capitalize()})
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ReadOnlyModelAdmin(DeleteOnlyModelAdmin):
    """A read-only modeladmin, no action can be performed, only see the object list"""

    list_display_links = None
    actions = None

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EmailBounceActionLog)
class EmailBounceActionLogAdmin(DeleteOnlyModelAdmin):
    list_display = ("created", "contact", "email", "action")
    list_filter = ("action",)
    search_fields = ("email",)
    date_hierarchy = "created"
    fieldsets = ((_("Bounce action log details"), {"fields": (("created", "action"), ("contact", "email"))}),)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "active")
    list_filter = ("state", "active")
    search_fields = ("name", "state__name")
    raw_id_fields = ("state",)


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "active")
    list_filter = ("active",)
    search_fields = ("name", "code")


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "country", "active")
    list_filter = ("country", "active")
    search_fields = ("name", "code", "country__name")
    raw_id_fields = ("country",)


@admin.register(TermsAndConditions)
class TermsAndConditionsAdmin(admin.ModelAdmin):
    list_display = ("code", "date")
    search_fields = ("code", )
    fields = ("date", "code", "text", "pdf_file")
    date_hierarchy = "date"


@admin.register(ActivityResponse)
class ActivityResponseAdmin(admin.ModelAdmin):
    list_display = ("name", "topic")
    list_filter = ("topic",)
    list_editable = ("topic",)
    search_fields = ("name", "topic__name")


admin.site.register(DynamicContactFilter)
admin.site.register(ProductBundle)
admin.site.register(AdvancedDiscount)
admin.site.register(DoNotCallNumber)
admin.site.register(MailtrainList)
admin.site.register(IdDocumentType)
admin.site.register(ActivityTopic)
admin.site.register(ProductSubscriptionPeriod)
admin.site.register(PersonType)
admin.site.register(BusinessEntityType)
admin.site.register(PaymentMethod)
admin.site.register(PaymentType)
