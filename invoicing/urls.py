# coding=utf-8
from django.urls import path, re_path

from . import views


urlpatterns = [
    re_path(r'^contact_invoices/(\d+)/$', views.contact_invoices, name='contact_invoices'),
    re_path(r'^bill_one_contact/(\d+)/$', views.bill_subscriptions_for_one_contact, name='bill_one_contact'),
    re_path(r'^cancel_invoice/(\d+)/$', views.cancel_invoice, name='cancel_invoice'),
    re_path(r'^invoicing/force_cancel_invoice/(\d+)/$', views.force_cancel_invoice, name='force_cancel_invoice'),
    re_path(r'^download_invoice/(\d+)/$', views.download_invoice, name='download_invoice'),
    path('invoice_filter/', views.invoice_filter, name='invoice_filter'),
    path('invoice_detail/<int:pk>/', views.InvoiceDetailView.as_view(), name='invoice_detail'),
    # WIP: UI for creating invoices, unfinished. Uncomment when ready.
    # path(
    #     'new_non_subscription/<int:contact_id>/',
    #     views.InvoiceNonSubscriptionCreateView.as_view(),
    #     name='create_non_subscription_invoice',
    # ),
]
