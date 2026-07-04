# coding=utf-8
from datetime import date

from django.utils.translation import gettext_lazy as _
from django.core.management import BaseCommand
from django.conf import settings

from core.models import Contact
from support.models import Issue, IssueStatus


def today():
    return date.today()


DEFAULT_NOTE = _("Generated automatically on {today}\n".format(today=today()))


class Command(BaseCommand):
    help = """Genera incidencias para realizar seguimientos de pagos, en clientes que deben facturas."""

    def add_arguments(self, parser):
        parser.add_argument('--verbosity', type=int, default=1, help='Verbosity level (0, 1, 2)')

    def handle(self, *args, **options):
        verbosity = options.get('verbosity', 1)
        contacts = (
            Contact.objects.filter(
                invoice__paid=False,
                invoice__debited=False,
                invoice__canceled=False,
                invoice__uncollectible=False,
                invoice__expiration_date__lt=today(),
            )
            .prefetch_related('invoice_set')
            .distinct()
        )
        if verbosity > 0:
            self.stdout.write(f"Found {contacts.count()} contacts with overdue invoices, starting process...")
        for contact in contacts.iterator():
            try:
                if contact.has_no_open_issues('I'):  # No open issues with category I
                    overdue_invoices = contact.get_expired_invoices()
                    overdue_invoices_str = str([x.id for x in overdue_invoices]).strip('[]')
                    notes = DEFAULT_NOTE + _(
                        "This contact has the following overdue invoices: {overdues}".format(
                            overdues=overdue_invoices_str
                        )
                    )
                    new_issue = Issue.objects.create(
                        category='I',
                        subscription=overdue_invoices[0].subscription if overdue_invoices else None,
                        date=today(),
                        subcategory='I06',  # Collection issue
                        notes=notes,
                        contact=contact,  # This is required
                        status=IssueStatus.objects.get(slug=settings.NEW_INVOICING_ISSUE_STATUS_SLUG),
                    )
                    if verbosity > 1:
                        self.stdout.write(f"Generated new collection issue {new_issue.id} for contact {contact.id}")
            except Exception as e:
                if verbosity > 0:
                    self.stdout.write(f"Error contacto {contact.id}: {e}")

        if verbosity > 0:
            self.stdout.write(_("Ended process"))
