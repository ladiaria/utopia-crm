# coding=utf-8
from datetime import date
from progress.bar import Bar

from django.core.management.base import BaseCommand

from core.models import Subscription


class Command(BaseCommand):
    help = u'Executes all the stuff that needs to be maintained daily'

    def handle(self, *args, **options):
        # Deactivate all ended subscriptions
        ended_subscriptions = Subscription.objects.filter(active=True, end_date__lte=date.today())
        bar = Bar('Processing', max=ended_subscriptions.count()) if options.get('verbosity') > 1 else None
        for s in ended_subscriptions.iterator():
            s.active = False
            # NOTE: after saving, a signal will be triggered to add deactivation contactproducthistory entries
            s.save()
            if bar:
                bar.next()
        if bar:
            bar.finish()

        # TODO: something with the people that owes us money
