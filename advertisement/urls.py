from django.urls import path

from advertisement import views

urlpatterns = [
    path("agencies/", views.AgencyFilterView.as_view(), name="agency_list"),
    path("agencies/<int:pk>/", views.AgencyDetailView.as_view(), name="agency_detail"),
    path("agencies/add/", views.AgencyAddView.as_view(), name="add_agency"),
    path("agencies/<int:pk>/edit/", views.AgencyEditView.as_view(), name="edit_agency"),
    path(
        "advertisers/<int:advertiser_id>/activity/add/",
        views.add_advertisement_activity,
        name="add_advertisement_activity",
    ),
    path("my_advertisers/", views.my_advertisers, name="my_advertisers"),
    path("advertisers/", views.AdvertiserFilterView.as_view(), name="advertiser_list"),
    path("advertisers/<int:pk>/", views.AdvertiserDetailView.as_view(), name="advertiser_detail"),
    path("advertisers/add/", views.AdvertiserAddView.as_view(), name="add_advertiser"),
    path("advertisers/<int:pk>/edit/", views.AdvertiserEditView.as_view(), name="edit_advertiser"),
]
