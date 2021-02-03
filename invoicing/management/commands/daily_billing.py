# coding=utf-8

from datetime import date

from django.core.management import BaseCommand
from django.db.models import Q

from core.models import Subscription
from invoicing.views import bill_subscription


class Command(BaseCommand):
    help = """Bills all customers that have not been billed as for today."""

    def handle(self, *args, **options):
        errors = ''
        count = 0
        billing_date = date.today()
        print("Started billing every subscription with billing_date equal or less than {}".format(billing_date))
        subscriptions_to_bill = Subscription.objects.filter(
            Q(end_date=None) | Q(end_date__gt=billing_date), active=True, type='N', next_billing__lte=billing_date)
        for subscription in subscriptions_to_bill:
            try:
                c = subscription.contact
                print('Billing contact {}\'s subscription {}'.format(c.id, subscription.id))
                invoice = bill_subscription(subscription.id, billing_date, 10)
                print('Generated invoice {} for ${}. Contact: {}'.format(invoice.id, invoice.amount, c.id))
                # invoice.save()
            except Exception as e:
                print('An error has been found.')
                errors += 'Contact {}, Subscription {}: {}\n'.format(c.id, subscription.id, e.message)
        print('Ended billing process. {} invoices have been created.'.format(count))
        print('List of errors: \n{}'.format(errors))

        # TODO: Mail someone with the print
