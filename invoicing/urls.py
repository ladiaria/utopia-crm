# coding=utf-8
from invoicing.views import (
    bill_subscription, contact_invoices, bill_subscriptions_for_one_contact, billings_control_panel, billing_invoices,
    cancel_invoice, print_invoice_pdf, print_duplicate, billing_progress, download_invoice)

from django.conf.urls import url

urlpatterns = [
    url(r'^bill_subscription/(\d+)/$', bill_subscription, name='bill_subscription'),
    url(r'^contact_invoices/(\d+)/$', contact_invoices, name='contact_invoices'),
    url(r'^bill_one_contact/(\d+)/$', bill_subscriptions_for_one_contact, name='bill_one_contact'),
    url(r'^billings_control_panel/$', billings_control_panel, name='billings_control_panel'),
    url(r'^billing_invoices/(\d+)/$', billing_invoices, name='billing_invoices'),
    url(r'^cancel_invoice/(\d+)/$', cancel_invoice, name='cancel_invoice'),
    url(r'^print_invoice/(\d+)/$', print_invoice_pdf, name='print_invoice'),
    url(r'^download_invoice/(\d+)/$', download_invoice, name='download_invoice'),
    url(r'^print_duplicate/(\d+)/$', print_duplicate, name='print_duplicate'),
    url(r'^billing_progress/$', billing_progress),
]
