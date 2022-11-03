# coding=utf-8


from django.contrib import admin
from django.utils.translation import ugettext_lazy as _

from simple_history.admin import SimpleHistoryAdmin

from .models import *


class CreditNoteAdmin(SimpleHistoryAdmin):
    model = CreditNote
    search_fields = ('numero', 'invoice__id', 'invoice__contact__id')
    list_display = ('invoice', 'serie', 'numero', 'get_contact_id')
    raw_id_fields = ['invoice']
    readonly_fields = ['invoice', 'uuid', 'serie', 'numero']
    ordering = ["-id"]


class InvoiceItemInline(admin.StackedInline):
    model = InvoiceItem
    fields = ['amount', 'product', 'description', 'price', 'copies', 'service_from', 'service_to', 'type']
    extra = 0


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
    readonly_fields = ['canceled', 'cancelation_date', 'uuid', 'serie', 'numero', 'pdf']
    ordering = ['-id']


class InvoiceItemAdmin(admin.ModelAdmin):
    pass


class BillingAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'start', 'amount_billed', 'count', 'progress', 'status')
    # readonly_fields = ['exclude']

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_staff:
            if request.user.is_superuser:
                return (
                    'id',
                    'start',
                    'exclude',
                    'errors',
                    'created_by',
                    'started_by',
                    'dpp',
                    'billing_date',
                    'end',
                    'subscriber_amount',
                )
            else:
                return [f.name for f in self.model._meta.fields]


admin.site.register(Invoice, InvoiceAdmin)
admin.site.register(Billing, BillingAdmin)
admin.site.register(InvoiceItem, InvoiceItemAdmin)
admin.site.register(CreditNote, CreditNoteAdmin)
