# coding=utf-8
from datetime import date, datetime

from django.utils.translation import ugettext_lazy as _
from django.core.management import BaseCommand
from django.conf import settings

from support.models import Issue


DEFAULT_NOTE = _("Generated automatically on {}\n".format(date.today()))


class Command(BaseCommand):
    help = """Cierra incidencias de facturación de tipo gestión de cobranzas, automáticamente."""

    # This is left blank if it's necessary to add some arguments
    # def add_arguments(self, parser):
    #    # parser.add_argument('payment_type', type=str)

    def handle(self, *args, **options):
        # TODO: Generate a queryset to look for debtors, or a method to check for it while iterating through all
        # The first part would be faster probably
        issues = Issue.objects.filter(category="I", subcategory="I06").exclude(
            status__slug__in=settings.FINISHED_ISSUE_STATUS_SLUG_LIST
        )
        if getattr(settings, 'ISSUE_STATUS_AUTO_CLOSE_SLUGS', None):
            issues = issues.filter(status__slug__in=settings.ISSUE_STATUS_AUTO_CLSOSE_SLUGS)
        print(_("Started process"))
        for issue in issues.iterator():
            try:
                contact = issue.contact
                if contact.is_debtor() is False:  # No open issues with category I
                    print(
                        _(
                            "Closing issue {} for contact {}. All their invoices are paid".format(
                                issue.id, contact.id
                            )
                        )
                    )
                    msg = u"Incidencia cerrada automáticamente por pago de facturas el {}".format(datetime.now())
                    issue.mark_solved(msg)
            except Exception as e:
                print("Error issue {}, contact {}: {}".format(issue.id, contact.id, e.message))
        print(_("Ended process"))
