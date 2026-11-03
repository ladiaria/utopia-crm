# coding=utf-8
from datetime import date

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.formats import date_format

from support.models import Issue, IssueStatus, IssueSubcategory

from .factory import create_contact

BADGE = "fa-lock"


@override_settings(ISSUE_STATUS_FINISHED_LIST=["cerrado-test"])
class IssueTerminalStatusBadgeTest(TestCase):
    """
    The issue detail shows a "closed" badge next to the status when the status is terminal, with the closing date in
    its tooltip when the issue has one.

    Statuses are built by hand: the base repo ships no issue catalogue fixture, and the terminal slug is set by the
    test so it does not depend on local_settings. Slugs are auto-generated from the name.
    """

    @classmethod
    def setUpTestData(cls):
        cls.contact = create_contact("Test", "099111222", "test@example.com")
        cls.status_open = IssueStatus.objects.create(name=settings.ISSUE_STATUS_NEW)
        cls.status_closed = IssueStatus.objects.create(name="cerrado-test")
        cls.subcategory = IssueSubcategory.objects.create(name="sub-test", category="S")
        cls.user = User.objects.create_user(username="agente", password="secret", is_staff=True)

    def setUp(self):
        self.client.login(username="agente", password="secret")

    def _detail(self, status, closing_date=None):
        issue = Issue.objects.create(
            contact=self.contact,
            date=date.today(),
            category="S",
            sub_category=self.subcategory,
            status=status,
            closing_date=closing_date,
        )
        response = self.client.get(reverse("view_issue", args=[issue.id]))
        self.assertEqual(response.status_code, 200)
        return issue, response.content.decode()

    def test_terminal_status_shows_badge_with_closing_date(self):
        closing_date = date(2026, 11, 3)
        issue, content = self._detail(self.status_closed, closing_date)
        self.assertTrue(issue.has_terminal_status())
        self.assertIn(BADGE, content)
        self.assertIn(date_format(closing_date, "SHORT_DATE_FORMAT"), content)

    def test_terminal_status_without_closing_date_shows_badge(self):
        issue, content = self._detail(self.status_closed)
        self.assertTrue(issue.has_terminal_status())
        self.assertIn(BADGE, content)

    def test_open_status_shows_no_badge(self):
        issue, content = self._detail(self.status_open, date(2026, 11, 3))
        self.assertFalse(issue.has_terminal_status())
        self.assertNotIn(BADGE, content)
