# coding=utf-8

from django.core.management import BaseCommand

from core.models import DynamicContactFilter


class Command(BaseCommand):
    help = "Synchronizes all active DynamicContactFilter objects with associated mailtrain."

    def handle(self, *args, **options):
        for dcf in DynamicContactFilter.objects.filter(active=True, autosync=True):
            dcf.sync_with_mailtrain_list()
