# coding=utf-8
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from core.models import Subscription


class Command(BaseCommand):
    help = """Ends subscriptions that have reached their end date.
        It's executed at 20:40 so it's meant to disable things from today or less."""

    def handle(self, *args, **options):
        # Deactivate all ended subscriptions
        verbose3 = options.get('verbosity') > 2

        ended_subscriptions = Subscription.objects.filter(
            active=True,
            end_date__lte=date.today(),
        )
        if verbose3:
            print("Starting process of ending subscriptions that have reached their end date...")
        for s in ended_subscriptions.iterator():
            s.active = False
            if verbose3:
                print("Disabling subscription {} for contact {} - End date {}".format(s.id, s.contact.id, s.end_date))
            # NOTE: after saving, a signal will be triggered to add deactivation contactproducthistory entries
            s.save()
        if verbose3:
            print("Ended process")
