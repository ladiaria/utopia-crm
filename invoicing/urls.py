# coding=utf-8
from invoicing.views import (
    bill_subscription, contact_invoices, bill_subscriptions_for_one_contact,
    cancel_invoice, download_invoice, invoice_filter, force_cancel_invoice)

from django.conf.urls import url

urlpatterns = [
    url(r'^bill_subscription/(\d+)/$', bill_subscription, name='bill_subscription'),
    url(r'^contact_invoices/(\d+)/$', contact_invoices, name='contact_invoices'),
    url(r'^bill_one_contact/(\d+)/$', bill_subscriptions_for_one_contact, name='bill_one_contact'),
    url(r'^cancel_invoice/(\d+)/$', cancel_invoice, name='cancel_invoice'),
    url(r'^invoicing/force_cancel_invoice/(\d+)/$', force_cancel_invoice, name='force_cancel_invoice'),
    url(r'^download_invoice/(\d+)/$', download_invoice, name='download_invoice'),
    url(r'^invoice_filter/$', invoice_filter, name='invoice_filter'),
]
