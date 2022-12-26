# coding=utf-8
from __future__ import unicode_literals

from .models import *
from django.contrib import admin


@admin.register(Support)
class SupportAdmin(admin.ModelAdmin):
    search_fields = ('name', )
    list_display = ('name', 'description')


@admin.register(ProductParticipation)
class ProductParticipationAdmin(admin.ModelAdmin):
    search_fields = ('contact__name', )
    list_display = ('contact', 'product')
    list_filter = ['product']
    raw_id_fields = ['contact', ]


@admin.register(Supporter)
class SupporterAdmin(admin.ModelAdmin):
    search_fields = ('contact__name', )
    list_display = ('contact', 'support')
    list_filter = ['support']
    raw_id_fields = ['contact', ]


