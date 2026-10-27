# coding=utf-8
from datetime import date

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.urls import reverse

from support.models import Issue, IssueResolution, IssueStatus, IssueSubcategory

from .factory import create_contact


@override_settings(ISSUE_RESOLUTION_SOLVED_SUBCATEGORIES=["baja-test"])
class IssueResolutionAutoSolvedTest(TestCase):
    """
    Editing an issue with a resolution of a subcategory in ISSUE_RESOLUTION_SOLVED_SUBCATEGORIES closes it as solved,
    and the message says it was done automatically.

    Statuses and subcategories are built by hand: the base repo ships no issue catalogue fixture, and their slugs come
    from the settings so they match whatever local_settings defines. Slugs are auto-generated from the name.
    """

    @classmethod
    def setUpTestData(cls):
        cls.contact = create_contact("Test", "099111222", "test@example.com")
        cls.status_new = IssueStatus.objects.create(name=settings.ISSUE_STATUS_NEW)
        cls.status_solved = IssueStatus.objects.create(name=settings.ISSUE_STATUS_SOLVED)
        cls.subcategory = IssueSubcategory.objects.create(name="baja-test", category="S")
        cls.other_subcategory = IssueSubcategory.objects.create(name="otra-test", category="S")
        cls.resolution = IssueResolution.objects.create(name="Baja", subcategory=cls.subcategory)
        cls.other_resolution = IssueResolution.objects.create(name="Otra", subcategory=cls.other_subcategory)
        cls.user = User.objects.create_user(username="agente", password="secret", is_staff=True)

    def setUp(self):
        self.client.login(username="agente", password="secret")

    def _update(self, sub_category, resolution):
        issue = Issue.objects.create(
            contact=self.contact, date=date.today(), category="S", sub_category=sub_category, status=self.status_new
        )
        data = {
            "contact": self.contact.id,
            "sub_category": sub_category.id,
            "status": self.status_new.id,
            "resolution": resolution.id,
            "submit": "",
        }
        response = self.client.post(reverse("view_issue", args=[issue.id]), data)
        issue.refresh_from_db()
        return issue, [str(m) for m in get_messages(response.wsgi_request)]

    def test_resolution_of_listed_subcategory_solves(self):
        issue, messages = self._update(self.subcategory, self.resolution)
        self.assertEqual(issue.status, self.status_solved)
        self.assertEqual(issue.closing_date, date.today())
        self.assertTrue(any(f"#{issue.id}" in m and self.status_solved.name in m for m in messages[1:]), messages)

    def test_resolution_of_other_subcategory_keeps_status(self):
        issue, messages = self._update(self.other_subcategory, self.other_resolution)
        self.assertEqual(issue.status, self.status_new)
        self.assertEqual(len(messages), 1, messages)
