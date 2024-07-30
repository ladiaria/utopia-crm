from django.urls import path

from advertisement import views

urlpatterns = [
    path("agencies/", views.AgencyFilterView.as_view(), name="agency_list"),
    path("agencies/<int:pk>/", views.AgencyDetailView.as_view(), name="agency_detail"),
    path("agencies/add/", views.AgencyCreateView.as_view(), name="add_agency"),
    path("agencies/<int:pk>/edit/", views.AgencyEditView.as_view(), name="edit_agency"),
    path(
        "advertisers/<int:advertiser_id>/activity/add/",
        views.AdvertisementActivityCreateView.as_view(),
        name="add_advertisement_activity",
    ),
    path(
        "advertisers/<int:advertiser_id>/activity/<int:pk>/edit/",
        views.AdvertisementActivityEditView.as_view(),
        name="edit_advertisement_activity",
    ),
    path("my_advertisers/", views.my_advertisers, name="my_advertisers"),
    path("advertisers/", views.AdvertiserFilterView.as_view(), name="advertiser_list"),
    path("advertisers/<int:pk>/", views.AdvertiserDetailView.as_view(), name="advertiser_detail"),
    path("advertisers/add/", views.AdvertiserCreateView.as_view(), name="add_advertiser"),
    path("advertisers/<int:pk>/edit/", views.AdvertiserEditView.as_view(), name="edit_advertiser"),
    path(
        "advertisers/<int:advertiser_id>/add_ad_purchase_order/",
        views.AdPurchaseOrderCreateView.as_view(),
        name="add_ad_purchase_order",
    ),
    path(
        "advertisers/<int:advertiser_id>/ad_purchase_orders/<int:pk>/",
        views.AdPurchaseOrderDetailView.as_view(),
        name="ad_purchase_order_detail",
    ),
    path("ad_purchase_orders/", views.AdPurchaseOrderFilterView.as_view(), name="ad_purchase_order_list"),
    path("advertisers/<int:agency_id>/add_agent/", views.AgentCreateView.as_view(), name="add_agent"),
    path(
        "advertisers/<int:agency_id>/ad_purchase_orders/<int:pk>/set_billed/",
        views.ad_purchase_order_set_billed,
        name="ad_purchase_order_set_billed",
    )
]
