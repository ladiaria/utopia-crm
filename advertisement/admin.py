from django.contrib import admin

from .models import Advertiser, AdvertisementActivity, AdvertisementSeller, AdPurchaseOrder, AdType, Ad, Agency, Agent


@admin.register(Advertiser)
class AdvertiserAdmin(admin.ModelAdmin):
    raw_id_fields = ("main_contact", "other_contacts", "main_seller")


@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    raw_id_fields = ("main_contact", "other_contacts", "main_seller")


@admin.register(AdvertisementActivity)
class AdvertisementActivityAdmin(admin.ModelAdmin):
    raw_id_fields = ("advertiser", "seller", "purchase_order")


class AdInline(admin.StackedInline):
    model = Ad
    extra = 1


@admin.register(AdPurchaseOrder)
class AdPurchaseOrderAdmin(admin.ModelAdmin):
    inlines = [AdInline]
    raw_id_fields = ("advertiser", "bill_to", "seller")


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    raw_id_fields = ("agency", "contact")


admin.site.register(Ad)
admin.site.register(AdType)
admin.site.register(AdvertisementSeller)
