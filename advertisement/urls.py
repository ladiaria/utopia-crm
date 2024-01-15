from django.urls import path

from advertisement import views

urlpatterns = [
    path("advertisers/", views.advertiser_list, name="advertiser_list"),
    path("advertisers/<int:advertiser_id>/", views.advertiser_detail, name="advertiser_detail"),
    path("my_advertisers/", views.my_advertisers, name="my_advertisers"),
]
