# coding=utf-8
from datetime import date

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from support.forms import IssueStartForm
from support.models import Issue, IssueStatus, IssueSubcategory

from .factory import create_contact


@override_settings(ISSUE_BLOCK_LOGISTICS_IF_NOT_DELIVERED_OPEN=True)
class NewIssueNotDeliveredBlockTest(TestCase):
    """
    A logistics issue can't be created while the contact has an open "not delivered" service issue.

    The statuses and subcategories are built by hand: the base repo ships no issue catalogue fixture, and their
    slugs come from the settings so they match whatever local_settings defines. Slugs are auto-generated from
    the name.
    """

    @classmethod
    def setUpTestData(cls):
        cls.contact = create_contact("Test", "099111222", "test@example.com")
        cls.status_new = IssueStatus.objects.create(name=settings.ISSUE_STATUS_NEW)
        cls.status_solved = IssueStatus.objects.create(name=settings.ISSUE_STATUS_SOLVED)
        cls.not_delivered = IssueSubcategory.objects.create(name=settings.ISSUE_SUBCATEGORY_NOT_DELIVERED, category="S")
        cls.did_not_arrive = IssueSubcategory.objects.create(name="no-llego-test", category="L")
        cls.user = User.objects.create_user(username="agente", password="secret", is_staff=True)

    def _not_delivered_issue(self, status):
        return Issue.objects.create(
            contact=self.contact, date=date.today(), category="S", sub_category=self.not_delivered, status=status
        )

    def _form(self, category="L", sub_category=None):
        data = {
            "contact": self.contact.id,
            "category": category,
            "date": date.today().isoformat(),
            "sub_category": (sub_category or self.did_not_arrive).id,
            "activity_type": "N",
            "copies": 1,
            "notes": "No le llegó el diario",
        }
        return IssueStartForm(data=data, initial={"contact": self.contact})

    def test_open_not_delivered_blocks_logistics(self):
        blocking = self._not_delivered_issue(self.status_new)
        form = self._form()
        self.assertFalse(form.is_valid())
        self.assertIn(f"#{blocking.id}", form.non_field_errors()[0])

    def test_closed_not_delivered_does_not_block(self):
        self._not_delivered_issue(self.status_solved)
        self.assertTrue(self._form().is_valid(), self._form().errors)

    def test_issue_without_status_counts_as_open(self):
        self._not_delivered_issue(None)
        self.assertFalse(self._form().is_valid())

    def test_other_categories_are_not_blocked(self):
        self._not_delivered_issue(self.status_new)
        service = IssueSubcategory.objects.create(name="quejas-test", category="S")
        self.assertTrue(self._form(category="S", sub_category=service).is_valid())

    @override_settings(ISSUE_BLOCK_LOGISTICS_IF_NOT_DELIVERED_OPEN=False)
    def test_setting_off_does_not_block(self):
        self._not_delivered_issue(self.status_new)
        self.assertTrue(self._form().is_valid())

    def test_hidden_contact_field_does_not_bypass(self):
        # The view saves the issue for the contact in its URL (the form's initial), so tampering with the hidden
        # contact field must not skip the check
        self._not_delivered_issue(self.status_new)
        other = create_contact("Otro", "099333444", "otro@example.com")
        form = self._form()
        form.data = {**form.data, "contact": other.id}
        self.assertFalse(form.is_valid())

    def test_view_warns_and_disables_submit(self):
        blocking = self._not_delivered_issue(self.status_new)
        self.client.force_login(self.user)
        response = self.client.get(reverse("new_issue", args=[self.contact.id, "L"]))
        self.assertEqual(response.context["blocking_issue"], blocking)
        self.assertContains(response, reverse("view_issue", args=[blocking.id]))
        self.assertRegex(response.content.decode(), r'name="submit"[^>]*disabled')

    def test_view_post_keeps_the_form_and_creates_nothing(self):
        self._not_delivered_issue(self.status_new)
        self.client.force_login(self.user)
        response = self.client.post(reverse("new_issue", args=[self.contact.id, "L"]), self._form().data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Issue.objects.filter(category="L").exists())
        self.assertContains(response, "No le llegó el diario")

    def test_view_without_blocking_issue_enables_submit(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("new_issue", args=[self.contact.id, "L"]))
        self.assertIsNone(response.context["blocking_issue"])
        self.assertNotRegex(response.content.decode(), r'name="submit"[^>]*disabled')
