# coding=utf-8
from datetime import date

from django.utils.translation import ugettext_lazy as _
from django.core.management import BaseCommand
from django.conf import settings

from core.models import Invoice
from support.models import Issue, IssueStatus


DEFAULT_NOTE = _("Generated automatically on {}\n".format(date.today()))


class Command(BaseCommand):
    help = """Genera incidencias para realizar seguimientos de pagos, en clientes que deben facturas."""

    # This is left blank if it's necessary to add some arguments
    # def add_arguments(self, parser):
    #    # parser.add_argument('payment_type', type=str)

    def handle(self, *args, **options):
        # TODO: Generate a queryset to look for debtors, or a method to check for it while iterating through all
        # The first part would be faster probably
        invoices = Invoice.objects.filter(
            paid=False, debited=False, canceled=False, uncollectible=False, expiration_date__lte=date.today())
        print(_("Started process"))
        for invoice in invoices.iterator():
            try:
                contact = invoice.contact
                if contact.has_no_open_issues('I'):  # No open issues with category I
                    print(_("Generating issue for contact {}".format(contact.name)))
                    expired_invoices = contact.get_expired_invoices()
                    overdue_invoices_str = str([x.id for x in expired_invoices]).strip('[]')
                    notes = DEFAULT_NOTE + _("This contact has the following overdue invoices: {}".format(
                        overdue_invoices_str))
                    new_issue = Issue.objects.create(
                        category='I',
                        subscription=invoice.subscription if invoice.subscription else None,
                        date=date.today(),
                        subcategory='I06',  # Collection issue
                        notes=notes,
                        contact=contact,  # This is required
                        status=IssueStatus.objects.get(slug=settings.NEW_INVOICING_ISSUE_STATUS_SLUG)
                    )
                    print("Generated new issue {} for contact {}".format(new_issue.id, contact.id))
            except Exception as e:
                print("Error factura {}, contacto {}: {}".format(invoice.id, contact.id, e))

        print(_("Ended process"))
