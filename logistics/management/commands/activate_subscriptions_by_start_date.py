# coding=utf-8
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from core.models import Subscription


class Command(BaseCommand):
    help = 'Activates subscriptions on their start date, also activates them one day before their start date.'

    def handle(self, *args, **options):
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
