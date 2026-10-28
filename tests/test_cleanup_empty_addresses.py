# coding=utf-8
"""
cleanup_empty_addresses no longer skips the empty addresses with issues or done tasks (it/utopia-crm-ladiaria#67):
with SET_NULL (#40) they stay, without the address. A pending address change still holds its address back.
"""
from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from core.models import Address
from support.models import Issue, ScheduledTask

from tests.factory import create_contact


@override_settings(WEB_UPDATE_USER_ENABLED=False)
class TestCleanupEmptyAddresses(TestCase):
    def setUp(self):
        self.contact = create_contact(name="Vacia", phone="099444222")

    def empty_address(self):
        # city defaults to DEFAULT_CITY
        return Address.objects.create(contact=self.contact, city=None)

    def address_change(self, address, completed):
        return ScheduledTask.objects.create(
            contact=self.contact, category="AC", execution_date=date.today(), address=address, completed=completed
        )

    def test_deletes_the_ones_with_history_and_keeps_the_history(self):
        with_issue, with_done_task = self.empty_address(), self.empty_address()
        issue = Issue.objects.create(contact=self.contact, date=date.today(), address=with_issue)
        task = self.address_change(with_done_task, completed=True)

        out = StringIO()
        call_command("cleanup_empty_addresses", fix=True, stdout=out)

        self.assertFalse(Address.objects.filter(contact=self.contact).exists())
        self.assertIsNone(Issue.objects.get(pk=issue.pk).address)
        self.assertIsNone(ScheduledTask.objects.get(pk=task.pk).address)
        self.assertIn("Issues que quedan sin direccion: 1", out.getvalue())

    def test_skips_a_pending_address_change(self):
        pending = self.empty_address()
        task = self.address_change(pending, completed=False)

        out = StringIO()
        call_command("cleanup_empty_addresses", fix=True, stdout=out)

        self.assertTrue(Address.objects.filter(pk=pending.pk).exists())
        self.assertEqual(ScheduledTask.objects.get(pk=task.pk).address, pending)
        self.assertIn("Omitidas por un cambio de direccion pendiente: 1", out.getvalue())

    def test_dry_run_deletes_nothing(self):
        address = self.empty_address()
        Issue.objects.create(contact=self.contact, date=date.today(), address=address)

        call_command("cleanup_empty_addresses", stdout=StringIO())

        self.assertTrue(Address.objects.filter(pk=address.pk).exists())
