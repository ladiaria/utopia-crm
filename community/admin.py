# coding=utf-8
from __future__ import unicode_literals

from .models import *
from django.contrib import admin


class SupportAdmin(admin.ModelAdmin):
    search_fields = ('name', )
    list_display = ('name', 'description')


class ProductParticipationAdmin(admin.ModelAdmin):
    search_fields = ('contact__name', )
    list_display = ('contact', 'product')
    list_filter = ['product']
    raw_id_fields = ['contact', ]


class SupporterAdmin(admin.ModelAdmin):
    search_fields = ('contact__name', )
    list_display = ('contact', 'support')
    list_filter = ['support']
    raw_id_fields = ['contact', ]


admin.site.register(Support, SupportAdmin)
admin.site.register(ProductParticipation, ProductParticipationAdmin)
admin.site.register(Supporter, SupporterAdmin)
