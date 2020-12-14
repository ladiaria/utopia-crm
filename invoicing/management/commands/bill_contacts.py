# coding=utf-8

from django.core.management import BaseCommand
from django.db.models import Q

from core.models import Subscription
from invoicing.views import bill_subscription, create_billing
from datetime import date


class Command(BaseCommand):
    help = """Bills all subscriptions with one payment type on a string."""

    def add_arguments(self, parser):
        parser.add_argument('payment_type', type=str, help="One payment type to be billed.")

    def handle(self, *args, **options):
        # TODO: Generate a billing here? Yes
        payment_type = options['payment_type'] or None
        # TODO: customize date?
        billing_date = date.today()
        print("Started billing with type(s) {} on {}".format(payment_type, billing_date))
        subscriptions_to_bill = Subscription.objects.filter(
            Q(end_date=None) | Q(end_date__gt=billing_date), active=True, type='N', next_billing__lte=billing_date,
            payment_type=payment_type)
        # We need to create a billing to store all these invoices.
        billing = create_billing(payment_type=payment_type, billing_date=billing_date, dpp=10)
        for subscription in subscriptions_to_bill:
            try:
                c = subscription.contact
                print('Billing contact {}'.format(c.id))
                invoice = bill_subscription(subscription.id, billing_date, 30)
                print('Generated invoice {} for ${}. Contact: {}'.format(invoice.id, invoice.amount, c.id))
                invoice.billing = billing
                invoice.save()
            except Exception as e:
                print('ID: {}\t{}'.format(c.id, e.message))
        print('Ended billing process. Billing id {} has been generated.'.format(billing.id))
