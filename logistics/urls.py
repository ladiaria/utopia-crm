# coding=utf-8

from logistics.views import (
    assign_routes, order_route, change_route, list_routes, route_details, issues_labels, print_labels_for_product,
    print_labels_from_csv, edition_time, print_labels)

from django.conf.urls import url

urlpatterns = [
    url(r'^assign_routes/$', assign_routes, name='assign_routes'),

    url(r'^order_route/$', order_route, name='order_route_default'),
    url(r'^change_route/$', change_route, name='change_route_default'),
    url(r'^order_route/(\d+)/$', order_route, name='order_route'),
    url(r'^change_route/(\d+)/$', change_route, name='change_route'),
    url(r'^list_routes/$', list_routes, name='list_routes'),
    url(r'^route/(\d+)/$', route_details, name='route_details'),
    url(r'^issues_labels/$', issues_labels, name='issues_labels'),

    # Label printing system
    url(r'^print_labels_product/$', print_labels_for_product, name='print_labels_for_product'),
    url(
        r'^print_labels/(?P<page>Roll|SheetA4)(/(?P<list_type>route)/(?P<route_list>\d+(,\d+)*))?/$',
        print_labels, name='print_labels'),
    url(r'^print_labels_from_csv/$', print_labels_from_csv, name='print_labels_from_csv'),

    url(r'^edition_time/(?P<direction>arrival|departure)/$', edition_time, name='edition_time'),
]
