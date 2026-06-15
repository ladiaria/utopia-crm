# coding=utf-8
from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from support.models import Issue, IssueStatus, IssueSubcategory

from .factory import create_contact


class BulkReassignIssueStatusTest(TestCase):
    def setUp(self):
        self.contact = create_contact("Test", "099111222", "test@example.com")

        # "resuelto" is terminal (in ISSUE_STATUS_FINISHED_LIST via local_settings),
        # "pendiente" is not. Slugs are auto-generated from the name.
        self.status_pending = IssueStatus.objects.create(name="pendiente")
        self.status_open = IssueStatus.objects.create(name="abierto")
        self.status_solved = IssueStatus.objects.create(name="resuelto")

        self.subcategory = IssueSubcategory.objects.create(name="reclamo")

        self.issues = [
            Issue.objects.create(
                contact=self.contact,
                date=date.today(),
                status=self.status_open,
                sub_category=self.subcategory,
            )
            for _ in range(3)
        ]

        self.admin = User.objects.create_user(username="admin", password="secret")
        admins_group, _created = Group.objects.get_or_create(name="Admins")
        self.admin.groups.add(admins_group)

        self.plain = User.objects.create_user(username="plain", password="secret")

        self.url = reverse("bulk_reassign_issue_status")

    def _login(self, user):
        c = Client()
        c.force_login(user)
        return c

    def test_permission_denied_for_plain_user(self):
        c = self._login(self.plain)
        response = c.post(
            self.url,
            {"mode": "ids", "issue_ids": [self.issues[0].id], "new_status": self.status_pending.id},
        )
        self.assertEqual(response.status_code, 403)

    def test_step1_shows_confirmation_without_changing(self):
        c = self._login(self.admin)
        ids = [i.id for i in self.issues]
        response = c.post(self.url, {"mode": "ids", "issue_ids": ids, "new_status": self.status_pending.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["count"], 3)
        # Nothing changed yet.
        for issue in self.issues:
            issue.refresh_from_db()
            self.assertEqual(issue.status, self.status_open)

    def test_step1_includes_date_range(self):
        # Spread the issue dates so oldest != newest.
        oldest = date.today() - timedelta(days=10)
        newest = date.today()
        self.issues[0].date = oldest
        self.issues[0].save(update_fields=["date"])
        self.issues[2].date = newest
        self.issues[2].save(update_fields=["date"])

        c = self._login(self.admin)
        ids = [i.id for i in self.issues]
        response = c.post(self.url, {"mode": "ids", "issue_ids": ids, "new_status": self.status_pending.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["oldest_date"], oldest)
        self.assertEqual(response.context["newest_date"], newest)

    def test_ids_mode_applies_change_with_confirmed(self):
        c = self._login(self.admin)
        ids = [i.id for i in self.issues[:2]]
        response = c.post(
            self.url,
            {"mode": "ids", "issue_ids": ids, "new_status": self.status_pending.id, "confirmed": "1"},
        )
        self.assertEqual(response.status_code, 302)
        # The two targeted issues changed; the third did not.
        self.issues[0].refresh_from_db()
        self.issues[1].refresh_from_db()
        self.issues[2].refresh_from_db()
        self.assertEqual(self.issues[0].status, self.status_pending)
        self.assertEqual(self.issues[1].status, self.status_pending)
        self.assertEqual(self.issues[2].status, self.status_open)

    def test_non_terminal_status_sets_next_action_date(self):
        c = self._login(self.admin)
        response = c.post(
            self.url,
            {
                "mode": "ids",
                "issue_ids": [self.issues[0].id],
                "new_status": self.status_pending.id,
                "confirmed": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.issues[0].refresh_from_db()
        self.assertEqual(self.issues[0].next_action_date, date.today() + timedelta(days=1))
        self.assertIsNone(self.issues[0].closing_date)

    def test_terminal_status_sets_closing_date(self):
        c = self._login(self.admin)
        response = c.post(
            self.url,
            {
                "mode": "ids",
                "issue_ids": [self.issues[0].id],
                "new_status": self.status_solved.id,
                "confirmed": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.issues[0].refresh_from_db()
        self.assertEqual(self.issues[0].closing_date, date.today())

    def test_filter_mode_resolves_queryset_serverside(self):
        c = self._login(self.admin)
        # A narrow-enough filter: status + subcategory. All three issues match.
        filter_qs = "status={}&sub_category={}".format(self.status_open.id, self.subcategory.id)
        response = c.post(
            self.url,
            {
                "mode": "filter",
                "filter_querystring": filter_qs,
                "new_status": self.status_pending.id,
                "confirmed": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        changed = Issue.objects.filter(status=self.status_pending).count()
        self.assertEqual(changed, 3)

    def test_filter_mode_rejected_when_filter_not_narrow(self):
        c = self._login(self.admin)
        # Only a status, no subcategory: whole-filter mode must be refused and
        # nothing should change.
        filter_qs = "status={}".format(self.status_open.id)
        response = c.post(
            self.url,
            {
                "mode": "filter",
                "filter_querystring": filter_qs,
                "new_status": self.status_pending.id,
                "confirmed": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Issue.objects.filter(status=self.status_pending).count(), 0)
        self.assertEqual(Issue.objects.filter(status=self.status_open).count(), 3)

    def test_list_shows_bulk_ui_for_admin_only(self):
        list_url = reverse("list_issues")

        # The <form> wrapper only renders inside the can_bulk_reassign block
        # (the JS that references the ids is always present, so we assert on the
        # form element, not on the script selectors).
        c_admin = self._login(self.admin)
        r_admin = c_admin.get(list_url)
        self.assertEqual(r_admin.status_code, 200)
        self.assertContains(r_admin, 'id="bulk-reassign-form"')
        self.assertContains(r_admin, 'class="bulk-issue-check"')

        c_plain = self._login(self.plain)
        r_plain = c_plain.get(list_url)
        self.assertEqual(r_plain.status_code, 200)
        self.assertNotContains(r_plain, 'id="bulk-reassign-form"')
        self.assertNotContains(r_plain, 'class="bulk-issue-check"')

    def test_invalid_status_is_rejected(self):
        c = self._login(self.admin)
        response = c.post(
            self.url,
            {"mode": "ids", "issue_ids": [self.issues[0].id], "new_status": 999999, "confirmed": "1"},
        )
        self.assertEqual(response.status_code, 302)
        self.issues[0].refresh_from_db()
        self.assertEqual(self.issues[0].status, self.status_open)
