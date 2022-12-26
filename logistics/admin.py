# coding=utf-8


from django.contrib import admin

from .models import *


@admin.register(Edition)
class EditionAdmin(admin.ModelAdmin):
    pass


@admin.register(EditionRoute)
class EditionRouteAdmin(admin.ModelAdmin):
    pass


@admin.register(EditionProduct)
class EditionProductAdmin(admin.ModelAdmin):
    pass


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('number', 'name', 'state', 'active', 'print_labels')


@admin.register(PickupPlace)
class PickupPlaceAdmin(admin.ModelAdmin):
    list_display = ('resort', 'description')
    ordering = ('resort__name', 'description')


@admin.register(PickupPoint)
class PickupPointAdmin(admin.ModelAdmin):
    list_display = ('name', 'address')


class VacationAdmin(admin.ModelAdmin):
    pass


@admin.register(GeorefAddress)
class GeorefAddressAdmin(admin.ModelAdmin):
    pass


@admin.register(RouteChange)
class RouteChangeAdmin(admin.ModelAdmin):
    raw_id_fields = ['contact']


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('date', 'route', 'copies')


@admin.register(Resort)
class ResortAdmin(admin.ModelAdmin):
    list_display = ('name', 'state', 'status', 'route', 'order')
    ordering = ('state', 'name')


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    pass


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    pass


