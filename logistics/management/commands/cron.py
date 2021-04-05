# coding=utf-8
from django.core.management.base import BaseCommand
from core.models import Subscription
from datetime import date


class Command(BaseCommand):
    help = 'Executes all the stuff that needs to be maintained daily'

    def handle(self, *args, **options):

        # Deactivate all ended subscriptions
        for s in Subscription.objects.filter(active=True, end_date__lte=date.today()):
            s.active = False
            # TODO: Contact product history deactivation
            s.save()

        for s in Subscription.objects.filter(active=True, type__in='NG'):
            # Do something with the people that owes us money.
            pass
