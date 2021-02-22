# coding=utf-8
from __future__ import unicode_literals

from django.contrib import admin

from .models import *


class CreditNoteAdmin(admin.ModelAdmin):
    model = CreditNote
    raw_id_fields = ['invoice']
    readonly_fields = ['serie', 'numero']


class InvoiceItemInline(admin.StackedInline):
    model = InvoiceItem
    fields = [
        'amount', 'product', 'description', 'price', 'copies', 'service_from', 'service_to'
    ]
    extra = 0


class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'contact', 'amount', 'paid', 'debited', 'canceled',
        'uncollectible')
    fields = [
        'contact', 'creation_date', 'expiration_date', 'service_from',
        'service_to', 'balance', 'amount', 'payment_type', 'debited', 'paid',
        'payment_date', 'payment_reference', 'notes', 'canceled',
        'cancelation_date', 'uncollectible', 'uuid', 'serie', 'numero',
        'pdf', 'old_pk', 'subscription',
        'billing_name', 'billing_address', 'billing_state', 'billing_city',
        'billing_document', 'route', 'order']
    raw_id_fields = ['contact', 'subscription']
    inlines = (InvoiceItemInline,)
    readonly_fields = [
        'canceled', 'cancelation_date', 'uuid', 'serie', 'numero', 'pdf']
    ordering = ['-id']


class InvoiceItemAdmin(admin.ModelAdmin):
    pass


class BillingAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'product', 'start', 'amount_billed', 'count',
        'progress', 'status')
    # readonly_fields = ['exclude']

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_staff:
            if request.user.is_superuser:
                return (
                    'id', 'start', 'exclude', 'errors', 'created_by',
                    'started_by', 'dpp', 'billing_date', 'end',
                    'subscriber_amount')
            else:
                return [f.name for f in self.model._meta.fields]


admin.site.register(Invoice, InvoiceAdmin)
admin.site.register(Billing, BillingAdmin)
admin.site.register(InvoiceItem, InvoiceItemAdmin)
admin.site.register(CreditNote, CreditNoteAdmin)
