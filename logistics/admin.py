# coding=utf-8
from __future__ import unicode_literals

from django.contrib import admin

from .models import *


class EditionAdmin(admin.ModelAdmin):
    pass


class EditionRouteAdmin(admin.ModelAdmin):
    pass


class EditionProductAdmin(admin.ModelAdmin):
    pass


class RouteAdmin(admin.ModelAdmin):
    pass


class PickupPlaceAdmin(admin.ModelAdmin):
    pass


class PickupPointAdmin(admin.ModelAdmin):
    pass


class VacationAdmin(admin.ModelAdmin):
    pass


class GeorefAddressAdmin(admin.ModelAdmin):
    pass


class RouteChangeAdmin(admin.ModelAdmin):
    pass


class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('date', 'route', 'copies')


class ResortAdmin(admin.ModelAdmin):
    pass


class CityAdmin(admin.ModelAdmin):
    pass


class MessageAdmin(admin.ModelAdmin):
    pass


admin.site.register(Edition, EditionAdmin)
admin.site.register(EditionRoute, EditionRouteAdmin)
admin.site.register(EditionProduct, EditionProductAdmin)
admin.site.register(Route, RouteAdmin)
admin.site.register(PickupPlace, PickupPlaceAdmin)
admin.site.register(PickupPoint, PickupPointAdmin)
admin.site.register(GeorefAddress, GeorefAddressAdmin)
admin.site.register(RouteChange, RouteChangeAdmin)
admin.site.register(Delivery, DeliveryAdmin)
admin.site.register(Resort, ResortAdmin)
admin.site.register(City, CityAdmin)
admin.site.register(Message, MessageAdmin)
