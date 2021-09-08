# coding=utf-8
from __future__ import unicode_literals

from django.forms import forms
from django.contrib.admin import SimpleListFilter
from django.utils.translation import ugettext_lazy as _
from django.contrib import admin
from django.urls import resolve

from taggit.models import TaggedItem
from tabbed_admin import TabbedModelAdmin

from community.models import ProductParticipation, Supporter
from .models import *
from .forms import *


class TaggitListFilter(SimpleListFilter):
    """
    A custom filter class that can be used to filter by taggit tags in the admin.
    """

    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _('tags')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'tag'

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
        ('product', 'copies', 'address'),
        ('route', 'order', 'label_contact', 'seller'),
        ('has_envelope', ),
    )
    raw_id_fields = ['route', 'label_contact', 'seller']
    extra = 1

    def get_parent_object_from_request(self, request):
        """
        Returns the parent object from the request or None.
        Note that this only works for Inlines, because the `parent_model`
        is not available in the regular admin.ModelAdmin as an attribute.
        """
        resolved = resolve(request.path_info)
        if resolved.args:
            return self.parent_model.objects.get(pk=resolved.args[0])
        return None

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        field = super(
            SubscriptionProductInline, self).formfield_for_foreignkey(
            db_field, request, **kwargs)
        if db_field.name == 'address':
            if request:
                contact = self.get_parent_object_from_request(request).contact
                field.queryset = field.queryset.filter(contact=contact)
        return field


class SubscriptionInline(admin.StackedInline):
    model = Subscription
    # TODO: remove or explain the next commented line
    # form = SubscriptionAdminForm
    extra = 0
    fieldsets = (
        (None, {
            'fields': (
                ('id', 'active'),
                ('frequency', 'status'),
                ('campaign', ),
                ('type', 'next_billing',),
                ('edit_products_field',),
                ('start_date', 'end_date'),
            )
        }),
        (None, {
            'fields': ('directions', ),
        }),
        (_('Billing data'), {
            'fields': (
                ('payment_type'),
                ('billing_address', 'billing_name'),
                ('billing_id_doc',),
                ('rut',),
                ('billing_phone', 'billing_email'),
                ('balance', 'send_bill_copy_by_email'))}),
        (_('Unsubscription'), {
            'classes': ('collapse', ),
            'fields': (
                ('inactivity_reason', 'unsubscription_date'),
                ('unsubscription_reason', ),
                ('unsubscription_addendum', )),
        }),
    )
    readonly_fields = ('id', 'web_comments', 'edit_products_field')
    raw_id_fields = ['campaign']

    def get_parent_object_from_request(self, request):
        """
        Returns the parent object from the request or None.
        Note that this only works for Inlines, because the `parent_model`
        is not available in the regular admin.ModelAdmin as an attribute.
        """
        resolved = resolve(request.path_info)
        if resolved.args:
            return self.parent_model.objects.get(pk=resolved.args[0])
        return None

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        field = super(
            SubscriptionInline, self).formfield_for_foreignkey(
            db_field, request, **kwargs)
        if db_field.name in ('delivery_address', 'billing_address'):
            if request:
                contact = self.get_parent_object_from_request(request)
                field.queryset = field.queryset.filter(contact=contact)
        return field


class SubscriptionAdminForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super(SubscriptionAdminForm, self).__init__(*args, **kwargs)
        if 'instance' in kwargs:
            self.fields['billing_address'].queryset = Address.objects.filter(
                contact=kwargs['instance'].contact)


class SubscriptionAdmin(admin.ModelAdmin):
    model = Subscription
    inlines = [SubscriptionProductInline]
    form = SubscriptionAdminForm
    fieldsets = (
        ('Contact data', {'fields': ('contact', )}),
        ('Subscription data', {'fields': (
            ('active', 'type'),
            ('start_date', 'end_date'),
            ('next_billing', 'payment_type'),
            ('balance', 'frequency'),
            ('status', 'send_bill_copy_by_email'),
            ('updated_from'),
        )}),
        ('Billing data', {
            'classes': ('collapse',),
            'fields': (
                ('billing_name', 'billing_address',),
                ('billing_phone', 'billing_email'),
                ('billing_id_doc',),
                ('rut',),
            )}),
        ('Inactivity', {
            'classes': ('collapse',),
            'fields': (
                ('inactivity_reason',),
                ('unsubscription_channel', 'unsubscription_type'),
                'unsubscription_reason',
                'unsubscription_addendum',
                ('unsubscription_date', 'unsubscription_manager'),
            )}),
    )
    list_display = ('contact', 'active', 'payment_type', 'campaign', 'product_summary')
    list_editable = ('active', 'payment_type')
    list_filter = ('campaign', 'active', 'payment_type')
    readonly_fields = ('contact', 'edit_products_field', 'campaign', 'updated_from')

    class Media:
        pass


class AddressInline(admin.StackedInline):
    raw_id_fields = ('geo_ref_address')
    model = Address
    extra = 0


class ProductParticipationInline(admin.StackedInline):
    model = ProductParticipation
    fields = ('product', 'description')
    verbose_name_plural = u'participaciones'
    extra = 1


class SubscriptionNewsletterInline(admin.TabularInline):
    model = SubscriptionNewsletter
    fields = ('product', 'active')
    verbose_name_plural = _('Newsletters')
    extra = 1


class SupporterInline(admin.StackedInline):
    model = Supporter
    fields = ('support', 'description')
    verbose_name_plural = _('Supporters')
    extra = 1


class ContactAdmin(TabbedModelAdmin):
    form = ContactAdminForm
    tab_overview = (
        (None, {'fields': (('name', 'tags'), )}),
        (None, {'fields': (('subtype', 'id_document'), )}),
        (None, {'fields': (
            ('email', 'no_email'),
            ('phone', 'mobile'),
            ('gender', 'education'),
            ('birthdate', 'private_birthdate'),
            ('protected',), 'protection_reason', 'notes')}),)
    tab_subscriptions = (SubscriptionInline, )
    tab_addresses = (AddressInline, )
    tab_newsletters = (SubscriptionNewsletterInline, )
    tab_community = (SupporterInline, ProductParticipationInline)
    tabs = [
        ('Overview', tab_overview),
        ('Subscriptions', tab_subscriptions),
        ('Newsletters', tab_newsletters),
        ('Address', tab_addresses),
        ('Community', tab_community)
    ]
    list_display = ('id', 'name', 'id_document', 'subtype', 'tag_list')
    list_filter = ('subtype', TaggitListFilter)
    ordering = ('id', )
    raw_id_fields = ('subtype', )
    change_form_template = 'admin/core/contact/change_form.html'

    def get_queryset(self, request):
        return super(ContactAdmin, self).get_queryset(request).prefetch_related('tags')

    def tag_list(self, obj):
        return u", ".join(o.name for o in obj.tags.all())


class ContactAdmin2(admin.ModelAdmin):
    form = ContactAdminForm
    fieldsets = (
        (None, {'fields': (('name', 'referring', 'tags'), )}),
        (None, {'fields': (('subtype', 'id_document'), )}),
        (None, {'fields': (
            ('phone', 'mobile'),
            ('gender', 'education', 'birthdate', 'private_birthdate'),
            ('ocupation'),
            ('protected',), 'protection_reason', 'notes')}))
    inlines = (
        SubscriptionInline,
        AddressInline,
        ProductParticipationInline,
        SupporterInline,
        SubscriptionNewsletterInline)
    raw_id_fields = ('referring', )
    list_display = ('id', 'name', 'subtype', 'tag_list')
    list_filter = ('subtype', TaggitListFilter)
    ordering = ('id',)

    def get_queryset(self, request):
        return super(
            ContactAdmin, self).get_queryset(request).prefetch_related('tags')

    def tag_list(self, obj):
        return u", ".join(o.name for o in obj.tags.all())


class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'price', 'active', 'type', 'weekday', 'slug', 'offerable', 'billing_priority')
    list_editable = ['name', 'type', 'price', 'weekday', 'billing_priority', 'offerable']
    readonly_fields = ('slug',)
    # prepopulated_fields = {'slug': ('name',)}


class PlanAdmin(admin.ModelAdmin):
    pass


class AddressAdmin(admin.ModelAdmin):
    raw_id_fields = ('contact', 'geo_ref_address')


class CampaignAdmin(admin.ModelAdmin):
    pass


class OcupationAdmin(admin.ModelAdmin):
    pass


class InstitutionAdmin(admin.ModelAdmin):
    pass


class VariableAdmin(admin.ModelAdmin):
    list_display = ('name', 'value', 'type')


class SubtypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


class ActivityAdmin(admin.ModelAdmin):
    raw_id_fields = ['contact', 'issue', 'seller', 'campaign']
    date_hierarchy = "datetime"
    list_display = ('id', 'contact', 'seller', 'datetime', 'activity_type', 'campaign', 'seller', 'status')
    list_filter = ('seller', 'campaign', 'status')
    search_fields = ('contact__id', 'contact__name')


class ContactProductHistoryAdmin(admin.ModelAdmin):
    list_display = ('contact', 'product', 'date', 'status')
    search_fields = ('contact__name', )
    raw_id_fields = ('contact', 'subscription')


class ContactCampaignStatusAdmin(admin.ModelAdmin):
    raw_id_fields = ['contact']
    list_display = ('contact', 'campaign', 'status', 'seller', 'times_contacted')
    list_filter = ('campaign', 'status', 'seller')
    search_fields = ('contact__name', )


class PriceRuleAdmin(admin.ModelAdmin):
    list_display = ('id', 'active', 'priority', 'amount_to_pick', 'mode', 'resulting_product')
    list_editable = ('active', 'priority')
    ordering = ('priority',)


class SubscriptionProductAdmin(admin.ModelAdmin):
    list_display = ('subscription_id', 'product', 'copies', 'address', 'route', 'order', 'seller')
    raw_id_fields = ('subscription', 'address', 'label_contact')


admin.site.register(Subscription, SubscriptionAdmin)
admin.site.register(Contact, ContactAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Address, AddressAdmin)
admin.site.register(Variable, VariableAdmin)
admin.site.register(Campaign, CampaignAdmin)
admin.site.register(Institution, InstitutionAdmin)
admin.site.register(Ocupation, OcupationAdmin)
admin.site.register(Subtype, SubtypeAdmin)
admin.site.register(Activity, ActivityAdmin)
admin.site.register(ContactProductHistory, ContactProductHistoryAdmin)
admin.site.register(ContactCampaignStatus, ContactCampaignStatusAdmin)
admin.site.register(PriceRule, PriceRuleAdmin)
admin.site.register(SubscriptionProduct, SubscriptionProductAdmin)
admin.site.register(DynamicContactFilter)
