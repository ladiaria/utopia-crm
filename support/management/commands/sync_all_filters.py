# coding=utf-8
from django.utils.translation import ugettext_lazy as _
from django.core.management import BaseCommand

from core.models import DynamicContactFilter


class Command(BaseCommand):
    help = """Syncs all Dynamic Contact Filters with mailtrain. It needs to have the 'autosync' attribute on."""

    # This is left blank if it's necessary to add some arguments
    # def add_arguments(self, parser):
    #    # parser.add_argument('payment_type', type=str)

    def handle(self, *args, **options):
        dc_filters = DynamicContactFilter.objects.filter(autosync=True)
        print(_("Started synchronization process"))
        for dcf in dc_filters:
            print(_("Started synchronizing filter {}".format(dcf.id)))
            try:
                dcf.sync_with_mailtrain_list()
            except Exception as e:
                print(_("There was an error synchronizing filter {}: {}".format(dcf.id, e.message)))
            else:
                print(_("Finished synchronizing filter {}".format(dcf.id)))
        print(_("Finished synchronization process"))
