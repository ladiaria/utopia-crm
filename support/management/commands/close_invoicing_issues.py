# coding=utf-8
from datetime import date, datetime

from django.utils.translation import gettext as _
from django.core.management import BaseCommand
from django.conf import settings
from django.db.models import Q

from support.models import Issue, IssueStatus


class Command(BaseCommand):
    help = """ Cierra incidencias de facturación de tipo gestión de cobranzas, automáticamente. """

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="List the issues that would be closed, without closing them"
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        issues = Issue.objects.filter(category="I").exclude(
            status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST
        ).select_related("contact")

        issue_status_autoclose = getattr(settings, 'ISSUE_STATUS_AUTO_CLOSE_SLUGS', [])
        if issue_status_autoclose:
            issues = issues.filter(status__slug__in=issue_status_autoclose)

        issue_subcat_autoclose = getattr(settings, 'ISSUE_SUBCATEGORY_AUTO_CLOSE_SLUGS', [])
        if issue_subcat_autoclose:
            issues = issues.filter(sub_category__slug__in=issue_subcat_autoclose)

        # A contact also stops being a debtor when their overdue invoices are marked as uncollectible. Those issues
        # are not solved: they are closed with this status, or left open if it is not set.
        uncollectible_status_slug = getattr(settings, 'ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE', None)
        uncollectible_status = (
            IssueStatus.objects.get(slug=uncollectible_status_slug) if uncollectible_status_slug else None
        )

        print(_("Started process"))
        for issue in issues.iterator():
            contact = issue.contact
            try:
                if contact.is_debtor():
                    continue
                last_settled = self.last_settled_invoice(contact)
                if last_settled is None:
                    continue
                if last_settled.paid or last_settled.debited:
                    print(
                        _("Closing issue {} for contact {}. All their invoices are paid").format(issue.id, contact.id)
                    )
                    if not dry_run:
                        msg = u"Incidencia cerrada automáticamente por pago de facturas el {}".format(datetime.now())
                        issue.mark_solved(msg)
                elif uncollectible_status:
                    print(
                        _("Closing issue {} for contact {} as {}. Their overdue invoices are uncollectible").format(
                            issue.id, contact.id, uncollectible_status
                        )
                    )
                    if not dry_run:
                        self.close_uncollectible(issue, uncollectible_status)
            except Exception as e:
                print("Error issue {}, contact {}: {}".format(issue.id, contact.id, e))
        print(_("Ended process"))

    def last_settled_invoice(self, contact):
        """
        The contact's last invoice that is paid, debited or uncollectible. A pending invoice that has not expired yet
        is a new billing cycle, so it doesn't tell how the debt of the issue ended.
        """
        return (
            contact.invoice_set.filter(canceled=False)
            .filter(Q(paid=True) | Q(debited=True) | Q(uncollectible=True))
            .order_by("-creation_date", "-id")
            .first()
        )

    def close_uncollectible(self, issue, status):
        note = _("Closed automatically on {}: the overdue invoices were marked as uncollectible").format(date.today())
        issue.status = status
        issue.closing_date = date.today()
        issue.answer_2 = f"{issue.answer_2}\n\n{note}" if issue.answer_2 else note
        issue.save()
