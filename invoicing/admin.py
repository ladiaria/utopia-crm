# coding=utf-8
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from simple_history.admin import SimpleHistoryAdmin

from invoicing.models import CreditNote, Invoice, InvoiceItem, TransactionType


@admin.register(CreditNote)
class CreditNoteAdmin(SimpleHistoryAdmin):
    model = CreditNote
    search_fields = ('numero', 'invoice__id', 'invoice__contact__id')
    list_display = ('invoice', 'serie', 'numero', 'get_contact_id', 'amount')
    raw_id_fields = ['invoice']
    readonly_fields = ['invoice', 'uuid', 'serie', 'numero']
    ordering = ["-id"]


class InvoiceItemInline(admin.StackedInline):
    model = InvoiceItem
    fields = ['amount', 'product', 'description', 'price', 'copies', 'service_from', 'service_to', 'type', 'type_dr']
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(SimpleHistoryAdmin):
    search_fields = ('contact__id', 'contact__name')
    list_display = ('id', 'contact', 'amount', 'paid', 'debited', 'canceled', 'uncollectible', 'serie', 'numero')
    fieldsets = (
        (
            "",
            {
                "fields": (
                    'contact',
                    'subscription',
                    ('creation_date', 'expiration_date'),
                    ('service_from', 'service_to'),
                    ('amount', 'payment_type'),
                    ('debited', 'paid'),
                    ('payment_date', 'payment_reference'),
                    'notes',
                    ('canceled', 'cancelation_date'),
                    'uncollectible',
                    ('uuid', 'serie', 'numero'),
                    ('pdf', 'balance'),
                    ('route', 'order'),
                    'print_date',
                )
            },
        ),
        (
            _('Billing data'),
            {
                'fields': (
                    ('billing_name', 'billing_address'),
                    ('billing_state', 'billing_city'),
                    'billing_document',
                )
            },
        ),
    )
    raw_id_fields = ['contact', 'subscription']
    inlines = (InvoiceItemInline,)
    readonly_fields = [
        'canceled',
        'cancelation_date',
        'uuid',
        'serie',
        'numero',
        'pdf',
        'payment_method_name',
        'payment_type_name',
        "consecutive_payment",
    ]
    ordering = ['-id']


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    pass


@admin.register(TransactionType)
class TransactionTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')
    ordering = ['-id']
