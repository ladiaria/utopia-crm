# coding=utf-8
from support.views import *

from django.conf.urls import url
from django.views.generic import TemplateView


urlpatterns = [
    url(r'^assign_campaigns/$', assign_campaigns, name="assign_campaigns"),
    url(r'^assign_sellers/$', list_campaigns_with_no_seller, name="assign_to_seller"),
    url(r'^assign_sellers/(\d+)/$', assign_seller, name="assign_sellers"),
    url(r'^seller_console/$', seller_console_list_campaigns, name="seller_console_list_campaigns"),
    url(r'^seller_console/(\w+)/(\d+)/$', seller_console, name="seller_console"),
    url(r'^edit_address/(\d+)/$', edit_address),
    url(r'^edit_address/(\d+)/(\d+)/$', edit_address),
    url(r'^import/$', import_contacts, name="import_contacts"),
    url(r'^send_promo/(\d+)/$', send_promo, name="send_promo"),
    url(r'^new_subscription/(\d+)/$', new_subscription, name="new_subscription"),
    url(r'^edit_products/(\d+)/$', edit_products, name="edit_products"),
    url(r'^contacts/$', contact_list, name="contact_list"),
    url(r'^contacts/(\d+)/$', contact_detail, name="contact_detail"),
    url(r'^api_new_address/(\d+)/$', api_new_address),
    url(r'^api_dynamic_prices/$', api_dynamic_prices),
    # Issues
    url(r'^list_issues/$', list_issues, name='list_issues'),
    url(r'^new_issue/(\d+)/$', new_issue, name="new_issue"),
    url(r'^new_scheduled_task/(\d+)/(\w+)/$', new_scheduled_task, name="new_scheduled_task"),
    url(r'^view_issue/(\d+)/$', view_issue, name="view_issue"),
    url(r'^add_dynamic_contact_filter/$', dynamic_contact_filter_new, name="dynamic_contact_filter_add"),
    url(r'^dynamic_contact_filter_list/$', dynamic_contact_filter_list, name="dynamic_contact_filter_list"),
    url(r'^dynamic_contact_filter/(\d+)/$', dynamic_contact_filter_edit, name="dynamic_contact_filter_edit"),
    url(r'^export_dcf_emails/(\d+)/$', export_dcf_emails, name="export_dcf_emails"),
    url(r'^sync_with_mailtrain/(\d+)/$', sync_with_mailtrain, name="sync_with_mailtrain"),
    url(r'^register_activity/$', register_activity, name="register_activity"),
    url(r'^create_contact/$', login_required(TemplateView.as_view(template_name="create_contact.html")), name='create_contact'),
]
