# coding=utf-8
from datetime import date

from django.utils.translation import ugettext_lazy as _
from django.core.management import BaseCommand

from core.models import Subscription, Contact
from support.models import Issue


DEFAULT_NOTE = _("Generated automatically on {}\n".format(date.today()))


class Command(BaseCommand):
    help = """Generates issue with category Invoicing"""

    # This is left blank if it's necessary to add some arguments
    # def add_arguments(self, parser):
    #    # parser.add_argument('payment_type', type=str)

    def handle(self, *args, **options):
        # TODO: Generate a queryset to look for debtors, or a method to check for it while iterating through all
        # The first part would be faster probably
        contacts = Contact.objects.filter(subscriptions__active=True).iterator()
        for contact in contacts:
            if contact.has_no_open_issues() and contact.is_debtor():
                print("Generating issue for {}".format(contact))
                expired_invoices = contact.get_expired_invoices()
                expired_invoices_str = str([x.id for x in expired_invoices]).strip('[]')
                notes = DEFAULT_NOTE + "This contact has these expired invoices: {}".format(expired_invoices_str)
                if contact.has_active_subscription():
                    subcategory = 'I06'  # Active collection issue
                else:
                    subcategory = 'I07'  # Inactive collection issue
                subscriptions_with_expired_invoices = contact.get_subscriptions_with_expired_invoices()
                if not subscriptions_with_expired_invoices:
                    # TODO: Remove this, this shouldn't ever be necessary
                    subscriptions_with_expired_invoices = contact.subscriptions.filter(active=True)
                new_issue = Issue.objects.create(
                    category='I', subcategory=subcategory,
                    subscription=subscriptions_with_expired_invoices[0] if subscriptions_with_expired_invoices else None,
                    date=date.today(),
                    notes=notes,
                    contact=contact,  # This is required
                )
                print("Generated new issue {} for contact {}".format(new_issue.id, contact.id))
