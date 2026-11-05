# coding=utf-8
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from support.models import Issue, IssueStatus, IssueSubcategory

from .factory import create_contact


@override_settings(ISSUE_STATUS_SOLVED="resuelta-test")
class IssueClosingDateTest(TestCase):
    """
    The closing date goes with the status: a terminal status has one and any other status has none, whichever way the
    issue is saved (it/utopia-crm-ladiaria#99).

    Statuses are built by hand: the base repo ships no issue catalogue fixture. Slugs are auto-generated from the name.
    """

    @classmethod
    def setUpTestData(cls):
        cls.contact = create_contact("Test", "099111222", "test@example.com")
        cls.status_open = IssueStatus.objects.create(name="abierta-test")
        cls.status_solved = IssueStatus.objects.create(name="resuelta-test", is_terminal=True)
        cls.status_cancelled = IssueStatus.objects.create(name="cancelada-test", is_terminal=True)
        cls.subcategory = IssueSubcategory.objects.create(name="sub-test", category="S")

    def _issue(self, status, **kwargs):
        return Issue.objects.create(
            contact=self.contact,
            date=date.today(),
            category="S",
            sub_category=self.subcategory,
            status=status,
            **kwargs,
        )

    def _set_closing_date(self, issue, closing_date):
        Issue.objects.filter(pk=issue.pk).update(closing_date=closing_date)
        issue.refresh_from_db()

    def test_created_in_a_terminal_status_gets_today(self):
        self.assertEqual(self._issue(self.status_solved).closing_date, date.today())

    def test_created_open_has_no_closing_date(self):
        self.assertIsNone(self._issue(self.status_open).closing_date)

    def test_explicit_closing_date_of_a_terminal_status_is_kept(self):
        closed_on = date.today() - timedelta(days=30)
        self.assertEqual(self._issue(self.status_solved, closing_date=closed_on).closing_date, closed_on)

    def test_moving_to_a_terminal_status_sets_today(self):
        issue = self._issue(self.status_open)
        issue.status = self.status_solved
        issue.save()
        issue.refresh_from_db()
        self.assertEqual(issue.closing_date, date.today())

    def test_moving_between_terminal_statuses_keeps_the_date(self):
        closed_on = date.today() - timedelta(days=10)
        issue = self._issue(self.status_solved, closing_date=closed_on)
        issue.status = self.status_cancelled
        issue.save()
        issue.refresh_from_db()
        self.assertEqual(issue.closing_date, closed_on)

    def test_reopening_removes_the_date(self):
        issue = self._issue(self.status_solved)
        issue.status = self.status_open
        issue.save()
        issue.refresh_from_db()
        self.assertIsNone(issue.closing_date)

    def test_closing_again_gets_a_new_date(self):
        issue = self._issue(self.status_solved, closing_date=date.today() - timedelta(days=10))
        issue.status = self.status_open
        issue.save()
        issue.status = self.status_solved
        issue.save()
        issue.refresh_from_db()
        self.assertEqual(issue.closing_date, date.today())

    def test_update_fields_with_status_also_writes_the_date(self):
        issue = self._issue(self.status_open)
        issue.status = self.status_solved
        issue.save(update_fields=["status"])
        issue.refresh_from_db()
        self.assertEqual(issue.closing_date, date.today())

        issue.status = self.status_open
        issue.save(update_fields=["status"])
        issue.refresh_from_db()
        self.assertIsNone(issue.closing_date)

    def test_update_fields_without_status_writes_only_those_fields(self):
        issue = self._issue(self.status_solved)
        self._set_closing_date(issue, None)
        issue.notes = "nota"
        issue.save(update_fields=["notes"])
        issue.refresh_from_db()
        self.assertEqual(issue.notes, "nota")
        self.assertIsNone(issue.closing_date)

    def test_mark_solved_keeps_the_date_of_a_closed_issue(self):
        closed_on = date.today() - timedelta(days=10)
        issue = self._issue(self.status_cancelled, closing_date=closed_on)
        issue.mark_solved("listo")
        issue.refresh_from_db()
        self.assertEqual(issue.status, self.status_solved)
        self.assertEqual(issue.closing_date, closed_on)

    def test_mark_solved_closes_an_open_issue_today(self):
        issue = self._issue(self.status_open)
        issue.mark_solved("listo")
        issue.refresh_from_db()
        self.assertEqual(issue.closing_date, date.today())

    def _post_detail(self, issue, status):
        user = User.objects.create_user(username="agente", password="secret", is_staff=True)
        self.client.force_login(user)
        data = {
            "category": issue.category,
            "sub_category": issue.sub_category_id,
            "status": status.pk,
            "date": issue.date.isoformat(),
            "contact": issue.contact_id,
            "copies": 0,
        }
        return self.client.post(f"/support/view_issue/{issue.pk}/", data)

    def test_reopening_from_the_issue_page_removes_the_date(self):
        """Issue 560981 in production: solved, and moved to another status a minute later, with the date left behind."""
        issue = self._issue(self.status_solved)
        response = self._post_detail(issue, self.status_open)
        self.assertEqual(response.status_code, 302)
        issue.refresh_from_db()
        self.assertEqual(issue.status, self.status_open)
        self.assertIsNone(issue.closing_date)
        self.assertEqual(issue.next_action_date, date.today() + timedelta(days=1))
