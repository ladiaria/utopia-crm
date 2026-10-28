# coding=utf-8
from datetime import date, timedelta

from django.core.management import call_command
from django.test import TestCase, override_settings

from invoicing.models import Invoice
from support.models import Issue, IssueStatus, IssueSubcategory

from .factory import create_contact


@override_settings(
    ISSUE_STATUS_AUTO_CLOSE_SLUGS=["new-test"],
    ISSUE_SUBCATEGORY_AUTO_CLOSE_SLUGS=["debt-test"],
    ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE="not-solved-test",
    ISSUE_STATUS_SOLVED="solved-test",
    ISSUE_STATUS_FINISHED_LIST=["solved-test", "not-solved-test"],
)
class CloseInvoicingIssuesTest(TestCase):
    """
    close_invoicing_issues closes the open invoicing issues of contacts that are no longer debtors: as solved if they
    paid, with ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE if their debt was marked as uncollectible.

    The statuses and subcategories are built by hand: the base repo ships no issue catalogue fixture. Slugs are
    auto-generated from the name.
    """

    @classmethod
    def setUpTestData(cls):
        cls.status_new = IssueStatus.objects.create(name="new-test")
        cls.status_other = IssueStatus.objects.create(name="other-test")
        IssueStatus.objects.create(name="solved-test")
        IssueStatus.objects.create(name="not-solved-test")
        cls.debt = IssueSubcategory.objects.create(name="debt-test", category="I")
        cls.other = IssueSubcategory.objects.create(name="other-sub-test", category="I")

    def setUp(self):
        self.contact = create_contact("Contacto", "099111222", "c@example.com")

    def _issue(self, sub_category=None, status=None):
        return Issue.objects.create(
            contact=self.contact,
            date=date.today(),
            category="I",
            sub_category=sub_category or self.debt,
            status=status or self.status_new,
        )

    def _invoice(self, days_to_expire=-10, **flags):
        creation_date = date.today() + timedelta(days_to_expire - 10)
        return Invoice.objects.create(
            contact=self.contact,
            creation_date=creation_date,
            expiration_date=date.today() + timedelta(days_to_expire),
            service_from=creation_date,
            service_to=creation_date + timedelta(30),
            amount=100,
            **flags,
        )

    def _run(self):
        call_command("close_invoicing_issues")

    def test_paid_is_solved(self):
        issue = self._issue()
        self._invoice(paid=True)

        self._run()

        issue.refresh_from_db()
        self.assertEqual(issue.status.slug, "solved-test")
        self.assertIn("pago de facturas", issue.answer_2)

    def test_uncollectible_is_closed_with_its_status(self):
        issue = self._issue()
        self._invoice(paid=True, days_to_expire=-400)
        self._invoice(uncollectible=True)

        self._run()

        issue.refresh_from_db()
        self.assertEqual(issue.status.slug, "not-solved-test")
        self.assertEqual(issue.closing_date, date.today())

    @override_settings(ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE=None)
    def test_uncollectible_stays_open_without_the_setting(self):
        issue = self._issue()
        self._invoice(uncollectible=True)

        self._run()

        issue.refresh_from_db()
        self.assertEqual(issue.status, self.status_new)

    def test_paid_after_uncollectible_is_solved(self):
        """What counts is the last settled invoice: old uncollectible debt, paid since."""
        issue = self._issue()
        self._invoice(uncollectible=True, days_to_expire=-400)
        self._invoice(paid=True)

        self._run()

        issue.refresh_from_db()
        self.assertEqual(issue.status.slug, "solved-test")

    def test_pending_not_expired_does_not_count(self):
        """A pending invoice not expired yet is a new cycle: the issue closes by the last settled one."""
        issue = self._issue()
        self._invoice(paid=True)
        self._invoice(days_to_expire=10)

        self._run()

        issue.refresh_from_db()
        self.assertEqual(issue.status.slug, "solved-test")

    def test_debtor_stays_open(self):
        issue = self._issue()
        self._invoice(paid=True, days_to_expire=-40)
        self._invoice()

        self._run()

        issue.refresh_from_db()
        self.assertEqual(issue.status, self.status_new)

    def test_other_subcategory_or_status_stays_open(self):
        """The subcategories are filtered by subcategory, not by status (it/utopia-crm-ladiaria#63)."""
        other_subcategory = self._issue(sub_category=self.other)
        other_status = self._issue(status=self.status_other)
        self._invoice(paid=True)

        self._run()

        for issue in (other_subcategory, other_status):
            issue.refresh_from_db()
        self.assertEqual(other_subcategory.status, self.status_new)
        self.assertEqual(other_status.status, self.status_other)

    def test_dry_run_closes_nothing(self):
        paid = self._issue()
        self._invoice(paid=True)

        call_command("close_invoicing_issues", dry_run=True)

        paid.refresh_from_db()
        self.assertEqual(paid.status, self.status_new)
