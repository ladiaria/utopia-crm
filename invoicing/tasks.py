# Create your tasks here
from __future__ import absolute_import, unicode_literals
import invoicing
from datetime import datetime
from .models import Billing

from celery import shared_task


@shared_task
def celery_bill_one_contact(contact_id, creation_date, dpp):
    # We get the creation date as a string, so we need to convert it to date
    creation_date = datetime.strptime(creation_date, "%Y-%m-%d").date()
    # this task calls bill_contact_subscriptions on background
    invoicing.views.bill_contact_subscriptions(contact_id, creation_date, dpp)


@shared_task
def celery_run_billing(billing_id):
    errors = ''
    billing_id = int(billing_id)
    billing = Billing.objects.get(pk=billing_id)
    assert billing.status == 'R', "Billing is already started"
    # We're telling the program that the billing has started so it locks them
    billing.status = 'S'
    billing.save()
    contacts = billing.contacts_to_bill()
    processed_contacts = billing.processed_contacts
    for c in contacts:
        try:
            invoice = invoicing.views.bill_contact_subscriptions(
                c.id, billing.billing_date, billing.dpp)
            invoice.billing = billing
            invoice.save()
        except Exception as e:
            errors = errors + 'ID: %s\t%s\n' % (c.id, e.message)
        # This is used just to accurately show a progressbar, might not be
        # very friendly with the database? It's also in the end of the loop
        # so it goes up for every contact and not just on successful ones.
        processed_contacts = processed_contacts + 1
        billing.processed_contacts = processed_contacts
        billing.save()
    billing.status = 'C'  # Add a completed status when it finshes
    if errors:
        billing.errors = errors
    billing.end = datetime.now()
    billing.save()
    return 'Completed {}'.format('with errors' if errors else 'SUCCESSFULLY!')


@shared_task
def celery_sum(a, b):
    return a + b
