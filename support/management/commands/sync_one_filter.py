# coding=utf-8
from django.utils.translation import gettext_lazy as _
from django.core.management import BaseCommand

from core.models import DynamicContactFilter


class Command(BaseCommand):
    help = """Syncs one Dynamic Contact Filter with mailtrain."""

    def add_arguments(self, parser):
        parser.add_argument('filter_id', type=int)

    def handle(self, *args, **options):
        try:
            dcf = DynamicContactFilter.objects.get(pk=options['filter_id'])
        except Exception:
            print(_("Cannot select filter"))

        print(_("Started synchronization process"))
        dcf.sync_with_mailtrain_list()
        print(_("Finished synchronization process"))
