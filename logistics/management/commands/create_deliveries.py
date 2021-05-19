# coding=utf-8

from datetime import date

from django.core.management import BaseCommand
from django.db.models import Sum

from core.models import SubscriptionProduct
from logistics.models import Delivery


class Command(BaseCommand):
    help = """Creates deliveries based on product per weekday."""

    def handle(self, *args, **options):
        today = date.today()
        isoweekday = today.isoweekday()
        sp_queryset = SubscriptionProduct.objects.filter(
            product__weekday=isoweekday, subscription__active=True, subscription__start_date__lte=today)

        print("Creating deliveries for the day {}")
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
            if created:
                print("New delivery for route {} ({}): {}".format(route_id, copies))
            else:
                print("Added {} copies to delivery for route {}".format(copies, route_id))
        print("Ended process")
