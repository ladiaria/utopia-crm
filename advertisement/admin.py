from django.contrib import admin

from .models import Advertiser, AdvertisementActivity, AdvertisementSeller, AdPurchaseOrder, AdType, Ad


@admin.register(Advertiser)
class AdvertiserAdmin(admin.ModelAdmin):
    raw_id_fields = ("main_contact", "other_contacts", "billing_address", "main_seller")


@admin.register(AdvertisementActivity)
class AdvertisementActivityAdmin(admin.ModelAdmin):
    raw_id_fields = ("advertiser", "seller", "purchase_order")


admin.site.register(AdType)
admin.site.register(Ad)
admin.site.register(AdPurchaseOrder)
admin.site.register(AdvertisementSeller)
