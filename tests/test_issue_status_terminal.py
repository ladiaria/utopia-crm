# coding=utf-8
from datetime import date, timedelta
from importlib import import_module

from django.apps import apps
from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission, User
from django.test import TestCase, override_settings
from django.urls import reverse

from support.models import Issue, IssueStatus, IssueSubcategory

from .factory import create_contact

migration_0044 = import_module("support.migrations.0044_issuestatus_is_terminal")


@override_settings(
    ISSUE_STATUS_NEW="nueva-test",
    ISSUE_STATUS_SOLVED="resuelta-test",
    ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE=None,
)
class IssueStatusTerminalTest(TestCase):
    """
    Whether a status is terminal is IssueStatus.is_terminal (it/utopia-crm-ladiaria#87), changed from the admin by
    whoever has its own permission, and the slugs of statuses and subcategories no longer change when they are
    renamed (it/utopia-crm-ladiaria#81).

    Statuses are built by hand: the base repo ships no issue catalogue fixture. Slugs are auto-generated from the name.
    """

    @classmethod
    def setUpTestData(cls):
        cls.contact = create_contact("Test", "099111222", "test@example.com")
        cls.status_new = IssueStatus.objects.create(name="nueva-test")
        cls.status_solved = IssueStatus.objects.create(name="resuelta-test", is_terminal=True)
        cls.status_waiting = IssueStatus.objects.create(name="en-espera-test")
        cls.subcategory = IssueSubcategory.objects.create(name="sub-test", category="S")

        cls.manager = User.objects.create_user(username="martin", password="secret", is_staff=True)
        cls.manager.user_permissions.add(
            Permission.objects.get(codename="change_issuestatus"),
            Permission.objects.get(codename="change_issuestatus_terminal"),
        )
        cls.editor = User.objects.create_user(username="editor", password="secret", is_staff=True)
        cls.editor.user_permissions.add(Permission.objects.get(codename="change_issuestatus"))

    def _issue(self, status, **kwargs):
        return Issue.objects.create(
            contact=self.contact,
            date=date.today(),
            category="S",
            sub_category=self.subcategory,
            status=status,
            **kwargs,
        )

    def _post(self, user, status, **data):
        self.client.force_login(user)
        payload = {"name": status.name, "category": status.category or ""}
        payload.update(data)
        return self.client.post(reverse("admin:support_issuestatus_change", args=[status.pk]), payload)

    # #81: the slug is fixed

    def test_renaming_keeps_the_slug(self):
        self.status_waiting.name = "En espera, con tilde"
        self.status_waiting.save()
        self.subcategory.name = "Subcategoría renombrada"
        self.subcategory.save()

        self.status_waiting.refresh_from_db()
        self.subcategory.refresh_from_db()
        self.assertEqual(self.status_waiting.slug, "en-espera-test")
        self.assertEqual(self.subcategory.slug, "sub-test")

    # The migration seeds is_terminal from the old list

    @override_settings(ISSUE_STATUS_FINISHED_LIST=["en-espera-test"])
    def test_migration_marks_the_statuses_of_the_old_list(self):
        migration_0044.mark_terminal_statuses(apps, None)

        self.status_waiting.refresh_from_db()
        self.status_new.refresh_from_db()
        self.assertTrue(self.status_waiting.is_terminal)
        self.assertFalse(self.status_new.is_terminal)

    @override_settings(ISSUE_STATUS_FINISHED_LIST=None)
    def test_migration_with_an_empty_list_marks_nothing(self):
        migration_0044.mark_terminal_statuses(apps, None)

        self.assertEqual(list(IssueStatus.objects.filter(is_terminal=True)), [self.status_solved])

    def test_migration_without_the_setting_uses_its_old_default(self):
        solved = IssueStatus.objects.create(name="solved")
        not_solved = IssueStatus.objects.create(name="not solved")

        with self.settings():
            del settings.ISSUE_STATUS_FINISHED_LIST
            migration_0044.mark_terminal_statuses(apps, None)

        solved.refresh_from_db()
        not_solved.refresh_from_db()
        self.status_waiting.refresh_from_db()
        self.assertTrue(solved.is_terminal)
        self.assertTrue(not_solved.is_terminal)
        self.assertFalse(self.status_waiting.is_terminal)

    # Open issues still include the ones without a status

    def test_issues_without_status_count_as_open(self):
        no_status = self._issue(None)
        closed = self._issue(self.status_solved)

        open_issues = Issue.objects.exclude(status__is_terminal=True)

        self.assertIn(no_status, open_issues)
        self.assertNotIn(closed, open_issues)

    # Admin: permission

    def test_without_the_permission_is_terminal_is_read_only(self):
        response = self._post(self.editor, self.status_waiting, is_terminal="on")

        self.assertEqual(response.status_code, 302)
        self.status_waiting.refresh_from_db()
        self.assertFalse(self.status_waiting.is_terminal)

    def test_with_the_permission_it_can_be_marked(self):
        response = self._post(self.manager, self.status_waiting, is_terminal="on")

        self.assertEqual(response.status_code, 302)
        self.status_waiting.refresh_from_db()
        self.assertTrue(self.status_waiting.is_terminal)

    def test_is_terminal_is_not_editable_from_the_list(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("admin:support_issuestatus_changelist"))

        self.assertNotIn("is_terminal", response.context["cl"].list_editable)

    # Admin: statuses that settings rely on

    def test_the_solved_status_cannot_be_unmarked(self):
        response = self._post(self.manager, self.status_solved)

        self.assertEqual(response.status_code, 200)
        self.assertIn("is_terminal", response.context["adminform"].form.errors)
        self.status_solved.refresh_from_db()
        self.assertTrue(self.status_solved.is_terminal)

    def test_the_new_status_cannot_be_marked(self):
        response = self._post(self.manager, self.status_new, is_terminal="on")

        self.assertEqual(response.status_code, 200)
        self.assertIn("is_terminal", response.context["adminform"].form.errors)
        self.status_new.refresh_from_db()
        self.assertFalse(self.status_new.is_terminal)

    def test_renaming_the_solved_status_is_not_blocked(self):
        """The checks run only when is_terminal changes."""
        response = self._post(self.manager, self.status_solved, name="Resuelta", is_terminal="on")

        self.assertEqual(response.status_code, 302)

    # Admin: changing a status that has issues

    def test_marking_with_issues_asks_for_confirmation(self):
        self._issue(self.status_waiting)

        response = self._post(self.manager, self.status_waiting, is_terminal="on")

        self.assertEqual(response.status_code, 200)
        self.assertIn("confirm_terminal_change", response.context["adminform"].form.errors)
        self.status_waiting.refresh_from_db()
        self.assertFalse(self.status_waiting.is_terminal)

    def test_marking_closes_its_issues_today(self):
        open_issue = self._issue(self.status_waiting)
        already_closed = self._issue(self.status_waiting)
        # update(), because save() does not let an open issue have a closing date.
        Issue.objects.filter(pk=already_closed.pk).update(closing_date=date.today() - timedelta(days=5))

        response = self._post(self.manager, self.status_waiting, is_terminal="on", confirm_terminal_change="on")

        self.assertEqual(response.status_code, 302)
        open_issue.refresh_from_db()
        already_closed.refresh_from_db()
        self.assertEqual(open_issue.closing_date, date.today())
        self.assertEqual(already_closed.closing_date, date.today() - timedelta(days=5))
        record = open_issue.history.first()
        self.assertEqual(record.history_user, self.manager)
        self.assertIn("en-espera-test", record.history_change_reason)
        log = LogEntry.objects.filter(object_id=str(self.status_waiting.pk)).latest("action_time")
        self.assertIn("1", log.get_change_message())

    def test_a_status_with_issues_cannot_be_unmarked(self):
        status = IssueStatus.objects.create(name="cerrada-test", is_terminal=True)
        closed_on = date.today() - timedelta(days=5)
        issue = self._issue(status, closing_date=closed_on)

        response = self._post(self.manager, status, confirm_terminal_change="on")

        self.assertEqual(response.status_code, 200)
        self.assertIn("is_terminal", response.context["adminform"].form.errors)
        status.refresh_from_db()
        issue.refresh_from_db()
        self.assertTrue(status.is_terminal)
        self.assertEqual(issue.closing_date, closed_on)

    def test_a_status_without_issues_can_be_unmarked(self):
        status = IssueStatus.objects.create(name="cerrada-test", is_terminal=True)

        response = self._post(self.manager, status)

        self.assertEqual(response.status_code, 302)
        status.refresh_from_db()
        self.assertFalse(status.is_terminal)

    def test_marking_without_issues_needs_no_confirmation(self):
        response = self._post(self.manager, self.status_waiting, is_terminal="on")

        self.assertEqual(response.status_code, 302)

    # Admin: names (and so slugs) are unique

    def _add(self, model_name, name):
        self.client.force_login(User.objects.create_superuser("root", "root@example.com", "secret"))
        return self.client.post(reverse(f"admin:support_{model_name}_add"), {"name": name, "category": ""})

    def test_a_status_with_a_name_in_use_cannot_be_created(self):
        response = self._add("issuestatus", "en-espera-test")

        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["adminform"].form.errors)
        self.assertEqual(IssueStatus.objects.filter(slug="en-espera-test").count(), 1)

    def test_a_name_that_only_differs_in_case_and_accents_is_rejected(self):
        response = self._add("issuesubcategory", "Sub Tést")

        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["adminform"].form.errors)

    def test_a_new_name_is_accepted(self):
        response = self._add("issuesubcategory", "Otra subcategoría")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(IssueSubcategory.objects.filter(slug="otra-subcategoria").exists())

    def test_renaming_to_a_name_in_use_is_rejected(self):
        response = self._post(self.manager, self.status_waiting, name="Nueva-Test")

        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["adminform"].form.errors)

    def test_saving_without_changing_the_name_is_not_checked(self):
        response = self._post(self.manager, self.status_waiting, category="S")

        self.assertEqual(response.status_code, 302)
