# coding=utf-8
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from core.models import Subscription


class Command(BaseCommand):
    help = 'Executes all the stuff that needs to be maintained daily'

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

        # Activate subscriptions that have not started yet
        not_yet_started = Subscription.objects.filter(
            active=False,
            start_date__gte=date.today() - timedelta(1),
            start_date__lte=date.today(),
            status="OK",
            end_date__isnull=True,
        )
        for s in not_yet_started.iterator():
            s.active = True
            s.save()
