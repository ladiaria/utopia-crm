from django.urls import path

from advertisement import views

urlpatterns = [
    path("advertisers/", views.advertiser_list),
    path("my_advertisers/", views.my_advertisers),
]