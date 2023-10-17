# coding=utf-8
from datetime import date, datetime

from django.utils.translation import gettext_lazy as _
from django.core.management import BaseCommand
from django.conf import settings

from support.models import Issue


DEFAULT_NOTE = _("Generated automatically on {}\n".format(date.today()))


class Command(BaseCommand):
    help = """ Cierra incidencias de facturación de tipo gestión de cobranzas, automáticamente. """

    def handle(self, *args, **options):
        # TODO: Generate a queryset to look for debtors, or a method to check for it while iterating through all
        # The first part would be faster probably
        issues = Issue.objects.filter(category="I").exclude(
            status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST
        )

        issue_status_autoclose = getattr(settings, 'ISSUE_STATUS_AUTO_CLOSE_SLUGS', [])
        if issue_status_autoclose:
            issues = issues.filter(status__slug__in=issue_status_autoclose)

        issue_subcat_autoclose = getattr(settings, 'ISSUE_SUBCATEGORY_AUTO_CLOSE_SLUGS', [])
        if issue_subcat_autoclose:
            issues = issues.filter(status__slug__in=issue_subcat_autoclose)

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
                print("Error issue {}, contact {}: {}".format(issue.id, contact.id, e))
        print(_("Ended process"))
