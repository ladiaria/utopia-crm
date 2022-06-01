# coding=utf-8
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from core.models import Subscription


class Command(BaseCommand):
    help = u'Activates subscriptions on their start date, also activates them one day before their start date.'

    def handle(self, *args, **options):
        verbose3 = options.get('verbosity') > 2

        # Activate subscriptions that have not started yet
        not_yet_started = Subscription.objects.filter(
            active=False,
            start_date__gte=date.today(),
            start_date__lte=date.today() + timedelta(1),
            status="OK",
            end_date__isnull=True,
        )
        if verbose3:
            print("Starting process of starting subscriptions that have reached their start date...")
        for s in not_yet_started.iterator():
            s.active = True
            if verbose3:
                print(
                    "Activating subscription {} for contact {} - Start date {}".format(
                        s.id, s.contact.id, s.start_date)
                )
            s.save()
        if verbose3:
            print("Ended process")
