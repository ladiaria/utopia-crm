# coding=utf-8

from datetime import date

from django.core.management import BaseCommand
from django.db.models import Sum

from core.models import SubscriptionProduct
from logistics.models import Delivery


class Command(BaseCommand):
    help = """Creates deliveries based on product per weekday."""

    def handle(self, *args, **options):
        # With --verbosity 0 it prints nothing, so a cron only mails when the command fails
        verbose = options['verbosity'] >= 1
        today = date.today()
        isoweekday = today.isoweekday()
        sp_queryset = SubscriptionProduct.objects.filter(
            product__weekday=isoweekday, subscription__active=True, subscription__start_date__lte=today)

        if verbose:
            self.stdout.write(f"Creating deliveries for the day {today}")
        for route in sp_queryset.values('route_id').distinct():
            route_id = route['route_id']
            if route_id is None:
                continue
            copies = sp_queryset.filter(route_id=route_id).aggregate(sum_copies=Sum('copies'))['sum_copies'] or 0
            nd, created = Delivery.objects.get_or_create(
                date=today,
                route=route['route_id'],
            )
            if nd.copies:
                nd.copies = nd.copies + copies
            else:
                nd.copies = copies
            nd.save()
            if not verbose:
                continue
            if created:
                self.stdout.write(f"New delivery for route {route_id}: {copies} copies")
            else:
                self.stdout.write(f"Added {copies} copies to delivery for route {route_id}")
        if verbose:
            self.stdout.write("Ended process")
