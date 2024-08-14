# coding=utf-8
from invoicing import views
from invoicing.views import (
    bill_subscription,
    contact_invoices,
    bill_subscriptions_for_one_contact,
    cancel_invoice,
    download_invoice,
    invoice_filter,
    force_cancel_invoice,
)

from django.urls import path, re_path

urlpatterns = [
    re_path(r'^bill_subscription/(\d+)/$', bill_subscription, name='bill_subscription'),
    re_path(r'^contact_invoices/(\d+)/$', contact_invoices, name='contact_invoices'),
    re_path(r'^bill_one_contact/(\d+)/$', bill_subscriptions_for_one_contact, name='bill_one_contact'),
    re_path(r'^cancel_invoice/(\d+)/$', cancel_invoice, name='cancel_invoice'),
    re_path(r'^invoicing/force_cancel_invoice/(\d+)/$', force_cancel_invoice, name='force_cancel_invoice'),
    re_path(r'^download_invoice/(\d+)/$', download_invoice, name='download_invoice'),
    path('invoice_filter/', invoice_filter, name='invoice_filter'),
    # path(
    #     'new_non_subscription/<int:contact_id>/',
    #     views.InvoiceNonSubscriptionCreateView.as_view(),
    #     name='create_non_subscription_invoice',
    # ),
]
