# coding=utf-8

from logistics.views import (
    assign_routes, order_route, change_route, list_routes, route_details, issues_labels, print_labels_for_product,
    print_labels_from_csv, edition_time, print_labels, logistics_issues_statistics, issues_per_route,
    issues_route_list, print_routes_simple, list_routes_detailed, convert_orders_to_tens)

from django.conf.urls import url

urlpatterns = [
    url(r'^assign_routes/$', assign_routes, name='assign_routes'),

    url(r'^order_route/$', order_route, name='order_route_default'),
    url(r'^change_route/$', change_route, name='change_route_default'),
    url(r'^order_route/(\d+)/$', order_route, name='order_route'),
    url(r'^change_route/(\d+)/$', change_route, name='change_route'),
    url(r'^convert_orders_to_tens/(\d+)/$', convert_orders_to_tens, name='convert_orders_to_tens'),
    url(r'^routes/$', list_routes, name='list_routes'),
    url(r'^routes_detailed/$', list_routes_detailed, name='list_routes_detailed'),
    url(r'^routes/(?P<route_list>\d+(,\d+)*)/$', route_details, name='route_details'),
    url(r'^print_routes/(?P<route_list>\d+(,\d+)*)/$', print_routes_simple, name='print_routes_simple'),
    url(r'^issues_labels/$', issues_labels, name='issues_labels'),
    url(r'^logistics_issues_statistics/$', logistics_issues_statistics, name="logistics_issues_statistics"),
    url(r'^issues_per_route/([^/]+)/([^/]+)/([^/]+)/$', issues_per_route, name="issues_per_route"),
    url(r'^issues_route_list/([^/]+)/([^/]+)/$', issues_route_list, name="issues_route_list"),

    # Label printing system
    url(
        r'^print_labels_for_product/(?P<page>Roll|SheetA4)/(?P<product_id>\d+)(/(?P<list_type>route)/(?P<route_list>\d+(,\d+)*))?/$',
        print_labels_for_product, name='print_labels_for_product'),
    url(
        r'^print_labels/(?P<page>Roll|SheetA4)(/(?P<list_type>route)/(?P<route_list>\d+(,\d+)*))?/$',
        print_labels, name='print_labels'),
    url(r'^print_labels_from_csv/$', print_labels_from_csv, name='print_labels_from_csv'),

    url(r'^edition_time/(?P<direction>arrival|departure)/$', edition_time, name='edition_time'),
]
