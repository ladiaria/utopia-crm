# coding=utf-8
from datetime import date

from django.core.management.base import BaseCommand

from core.models import Subscription


class Command(BaseCommand):
    help = u'Ends subscriptions that have reached their end date'

    def handle(self, *args, **options):
        # Deactivate all ended subscriptions
        ended_subscriptions = Subscription.objects.filter(
            active=True,
            end_date__lt=date.today()
        )
        for s in ended_subscriptions.iterator():
            s.active = False
            # NOTE: after saving, a signal will be triggered to add deactivation contactproducthistory entries
            s.save()
