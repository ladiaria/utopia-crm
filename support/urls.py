# coding=utf-8
from support import views
from support.views import (
    assign_campaigns,
    list_campaigns_with_no_seller,
    assign_seller,
    seller_console_list_campaigns,
    seller_console,
    seller_console_special_routes,
    scheduled_activities,
    edit_address,
    import_contacts,
    send_promo,
    new_subscription,
    default_newsletters_dialog,
    product_change,
    partial_unsubscription,
    book_unsubscription,
    edit_products,
    contact_list,
    contact_detail,
    api_new_address,
    api_dynamic_prices,
    list_issues,
    invoicing_issues,
    debtor_contacts,
    new_issue,
    new_scheduled_task_total_pause,
    new_scheduled_task_address_change,
    new_scheduled_task_partial_pause,
    view_issue,
    dynamic_contact_filter_new,
    dynamic_contact_filter_edit,
    dynamic_contact_filter_list,
    export_dcf_emails,
    advanced_export_dcf_list,
    sync_with_mailtrain,
    register_activity,
    edit_contact,
    edit_newsletters,
    edit_envelopes,
    upload_payment_certificate,
    campaign_statistics_list,
    campaign_statistics_detail,
    campaign_statistics_per_seller,
    seller_performance_by_time,
    unsubscription_statistics,
    release_seller_contacts,
    release_seller_contacts_by_campaign,
    scheduled_task_filter,
    edit_address_complementary_information,
    upload_do_not_call_numbers,
    tag_contacts,
    email_suggestion,
    api_get_addresses,
)

from django.urls import path, re_path


urlpatterns = [
    path("assign_campaigns/", assign_campaigns, name="assign_campaigns"),
    path("assign_sellers/", list_campaigns_with_no_seller, name="assign_to_seller"),
    re_path(r"^assign_sellers/(\d+)/$", assign_seller, name="assign_sellers"),
    path(
        "seller_console/",
        seller_console_list_campaigns,
        name="seller_console_list_campaigns",
    ),
    re_path(r"^seller_console/(\w+)/(\d+)/$", seller_console, name="seller_console"),
    re_path(r"^special_routes/(\d+)/$", seller_console_special_routes, name="seller_console_special_routes"),
    path("scheduled_activities/", scheduled_activities, name="scheduled_activities"),
    re_path(r"^edit_address/(\d+)/$", edit_address),
    re_path(r"^edit_address/(\d+)/(\d+)/$", edit_address),
    path("import/", import_contacts, name="import_contacts"),
    re_path(r"^send_promo/(\d+)/$", send_promo, name="send_promo"),
    re_path(r"^new_subscription/(\d+)/$", new_subscription, name="new_subscription"),
    path(
        "default_newsletters_dialog/<int:contact_id>/",
        default_newsletters_dialog,
        name="default_newsletters_dialog",
    ),
    re_path(r"^product_change/(\d+)/$", product_change, name="product_change"),
    re_path(r"^partial_unsubscription/(\d+)/$", partial_unsubscription, name="partial_unsubscription"),
    re_path(r"^book_unsubscription/(\d+)/$", book_unsubscription, name="book_unsubscription"),
    re_path(r"^edit_products/(\d+)/$", edit_products, name="edit_products"),
    path("contacts/", contact_list, name="contact_list"),
    re_path(r"^contacts/(\d+)/$", contact_detail, name="contact_detail"),
    re_path(r"^contacts/(\d+)/history$", views.history_extended, name="history_extended"),
    re_path(r"^api_new_address/(\d+)/$", api_new_address),
    path("api_dynamic_prices/", api_dynamic_prices),
    path("api_get_addresses/<int:contact_id>/", api_get_addresses, name="api_get_addresses"),
    # Issues
    path("list_issues/", list_issues, name="list_issues"),
    path("invoicing_issues/", invoicing_issues, name="invoicing_issues"),
    path("debtor_contacts/", debtor_contacts, name="debtor_contacts"),
    re_path(r"^new_issue/(\d+)/(\w+)/$", new_issue, name="new_issue"),
    re_path(
        r"^new_scheduled_task/total_pause/(\d+)/$",
        new_scheduled_task_total_pause,
        name="new_scheduled_task_total_pause",
    ),
    re_path(
        r"^new_scheduled_task/address_change/(\d+)/$",
        new_scheduled_task_address_change,
        name="new_scheduled_task_address_change",
    ),
    re_path(
        r"^new_scheduled_task/partial_pause/(\d+)/$",
        new_scheduled_task_partial_pause,
        name="new_scheduled_task_partial_pause",
    ),
    re_path(r"^view_issue/(\d+)/$", view_issue, name="view_issue"),
    path(
        "add_dynamic_contact_filter/",
        dynamic_contact_filter_new,
        name="dynamic_contact_filter_add",
    ),
    path(
        "dynamic_contact_filter_list/",
        dynamic_contact_filter_list,
        name="dynamic_contact_filter_list",
    ),
    re_path(
        r"^dynamic_contact_filter/(\d+)/$",
        dynamic_contact_filter_edit,
        name="dynamic_contact_filter_edit",
    ),
    re_path(r"^export_dcf_emails/(\d+)/$", export_dcf_emails, name="export_dcf_emails"),
    re_path(r"^export_dcf_contacts/(\d+)/$", advanced_export_dcf_list, name="advanced_export_dcf_list"),
    re_path(r"^sync_with_mailtrain/(\d+)/$", sync_with_mailtrain, name="sync_with_mailtrain"),
    path("register_activity/", register_activity, name="register_activity"),
    re_path(r"^contacts/(\d+)/edit/$", edit_contact, name="edit_contact"),
    re_path(r"^edit_newsletters/(\d+)/$", edit_newsletters, name="edit_newsletters"),
    re_path(r"^edit_envelopes/(\d+)/$", edit_envelopes, name="edit_envelopes"),
    re_path(r"^upload_payment_certificate/(\d+)/$", upload_payment_certificate, name="upload_payment_certificate"),
    re_path(
        r"^address_complementary_information/(\d+)/$",
        edit_address_complementary_information,
        name="edit_address_complementary_information",
    ),
    path("campaign_statistics/", campaign_statistics_list, name="campaign_statistics_list"),
    re_path(r"^campaign_statistics/(\d+)/$", campaign_statistics_detail, name="campaign_statistics_detail"),
    re_path(
        r"^campaign_statistics/by_seller/(\d+)/$",
        campaign_statistics_per_seller,
        name="campaign_statistics_per_seller",
    ),
    path("campaign_statistics/performance_by_time/", seller_performance_by_time, name="seller_performance_by_time"),
    path("unsubscription_statistics/", unsubscription_statistics, name="unsubscription_statistics"),
    path("release_seller_contacts/", release_seller_contacts, name="release_seller_contacts"),
    re_path(r"^release_seller_contacts/(\d+)/$", release_seller_contacts, name="release_seller_contacts"),
    path(
        "release_seller_contacts_by_campaign/<int:seller_id>/",
        release_seller_contacts_by_campaign,
        name="release_seller_contacts_by_campaign",
    ),
    path(
        "release_seller_contacts_by_campaign/<int:seller_id>/<int:campaign_id>/",
        release_seller_contacts_by_campaign,
        name="release_seller_contacts_by_campaign",
    ),
    path("scheduled_task_filter/", scheduled_task_filter, name="scheduled_task_filter"),
    path("upload_do_not_call_numbers/", upload_do_not_call_numbers, name="upload_do_not_call_numbers"),
    path("tag_contacts/", tag_contacts, name="tag_contacts"),
    path("api_email_suggestion/", email_suggestion, name="email_suggestion"),
]
