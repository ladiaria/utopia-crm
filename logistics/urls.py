# coding=utf-8

from logistics.views import (
    assign_routes, order_route, change_route, list_routes, route_details, issues_labels, print_labels_for_product,
    print_labels_from_csv, edition_time, print_labels, logistics_issues_statistics, issues_per_route,
    issues_route_list, print_routes_simple, list_routes_detailed, convert_orders_to_tens, print_unordered_subscriptions,
    print_labels_for_day, assign_routes_future, order_route_list, print_labels_for_product_date,
    addresses_with_complementary_information,
    )

from django.urls import path, re_path

urlpatterns = [
    path('assign_routes/', assign_routes, name='assign_routes'),
    path('assign_routes_future/', assign_routes_future, name='assign_routes_future'),
    path('change_route/', change_route, name='change_route_default'),
    path('order_route/', order_route_list, name='order_route_list'),
    re_path(r'^order_route/(\d+)/$', order_route, name='order_route'),
    path('print_unordered_subscriptions/', print_unordered_subscriptions, name='print_unordered_subscriptions'),
    re_path(r'^change_route/(\d+)/$', change_route, name='change_route'),
    re_path(r'^convert_orders_to_tens/(\d+)/$', convert_orders_to_tens, name='convert_orders_to_tens'),
    re_path(r'^convert_orders_to_tens/(\d+)/(\d+)/$', convert_orders_to_tens, name='convert_orders_to_tens_by_product'),
    path('routes/', list_routes, name='list_routes'),
    path('routes_detailed/', list_routes_detailed, name='list_routes_detailed'),
    re_path(r'^routes/(?P<route_list>\d+(,\d+)*)/$', route_details, name='route_details'),
    re_path(r'^print_routes/(?P<route_list>\d+(,\d+)*)/$', print_routes_simple, name='print_routes_simple'),
    path('issues_labels/', issues_labels, name='issues_labels'),
    path('logistics_issues_statistics/', logistics_issues_statistics, name="logistics_issues_statistics"),
    re_path(r'^issues_per_route/([^/]+)/([^/]+)/([^/]+)/$', issues_per_route, name="issues_per_route"),
    re_path(r'^issues_route_list/([^/]+)/([^/]+)/$', issues_route_list, name="issues_route_list"),

    # Label printing system
    re_path(
        r'^print_labels_for_product/(?P<page>Roll|SheetA4)/(?P<product_id>\d+)(/(?P<list_type>route)/(?P<route_list>\d+(,\d+)*))?/$',
        print_labels_for_product, name='print_labels_for_product'),
    re_path(
        r'^print_labels/(?P<page>Roll|SheetA4)(/(?P<list_type>route)/(?P<route_list>\d+(,\d+)*))?/$',
        print_labels, name='print_labels'),
    path('print_labels_from_csv/', print_labels_from_csv, name='print_labels_from_csv'),
    path('print_labels_for_day/', print_labels_for_day, name='print_labels_for_day'),
    path('print_labels_for_product_date/', print_labels_for_product_date, name='print_labels_for_product_date'),

    re_path(r'^edition_time/(?P<direction>arrival|departure)/$', edition_time, name='edition_time'),
    path('addresses_with_complementary_information/', addresses_with_complementary_information, name='addresses_with_complementary_information'),
]
