# coding=utf-8


from django.contrib import admin

from core.models import Product

from .models import (
    Edition,
    EditionRoute,
    EditionProduct,
    Route,
    PickupPlace,
    PickupPoint,
    RouteChange,
    Delivery,
    Resort,
    City,
    Message
)


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


class OfferableProductFilter(admin.SimpleListFilter):
    title = 'producto'
    parameter_name = 'product'

    def lookups(self, request, model_admin):
        return [
            (p.pk, str(p))
            for p in Product.objects.filter(offerable=True, type='S').order_by('name')
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(product_id=self.value())
        return queryset


@admin.register(RouteChange)
class RouteChangeAdmin(admin.ModelAdmin):
    list_display = ('dt', 'contact', 'product', 'old_route', 'old_address', 'old_city')
    list_filter = (OfferableProductFilter, 'old_route', ('dt', admin.DateFieldListFilter))
    search_fields = ('contact__id', 'contact__name', 'contact__last_name')
    raw_id_fields = ['contact']
    date_hierarchy = 'dt'


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
