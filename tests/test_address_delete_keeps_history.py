# coding=utf-8
"""
Deleting an address keeps the issues and scheduled tasks that used it (SET_NULL, it/utopia-crm-ladiaria#40).

They belong to the contact and are kept as history: before this they went away with the address, with no warning
from the contact admin's inline. A pending address change left with no address must not be executed: it used to
strip the products of their address and route before failing, so they stopped being delivered.
"""
from datetime import date
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from core.models import Address, SubscriptionProduct
from logistics.models import Route
from support.models import Issue, ScheduledTask, ScheduledTaskMissingAddress

from tests.factory import create_address, create_contact, create_product, create_subscription


@override_settings(WEB_UPDATE_USER_ENABLED=False)
class TestAddressDeleteKeepsHistory(TestCase):
    def setUp(self):
        self.contact = create_contact(name="Historia", phone="099444111")
        self.old_address = create_address("Colonia 1234", self.contact)
        self.new_address = create_address("Canelones 999", self.contact)
        self.subscription = create_subscription(self.contact)
        self.product = create_product("Paper product", 100)
        self.route = Route.objects.create(number=4001)
        self.sp = SubscriptionProduct.objects.create(
            subscription=self.subscription, product=self.product, address=self.old_address, route=self.route, order=7
        )

    def address_change(self, address):
        task = ScheduledTask.objects.create(
            contact=self.contact, category="AC", execution_date=date.today(), address=address
        )
        task.subscription_products.add(self.sp)
        return task

    def assert_product_untouched(self):
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.address, self.old_address)
        self.assertEqual(self.sp.route, self.route)
        self.assertEqual(self.sp.order, 7)

    def test_deleting_an_address_keeps_the_issue_and_the_task(self):
        issue = Issue.objects.create(contact=self.contact, date=date.today(), address=self.new_address)
        task = self.address_change(self.new_address)
        self.new_address.delete()
        self.assertIsNone(Issue.objects.get(pk=issue.pk).address)
        self.assertIsNone(ScheduledTask.objects.get(pk=task.pk).address)

    def test_an_address_change_without_address_touches_nothing(self):
        task = self.address_change(self.new_address)
        self.new_address.delete()
        task.refresh_from_db()
        with self.assertRaises(ScheduledTaskMissingAddress):
            task.execute()
        self.assert_product_untouched()
        self.assertFalse(ScheduledTask.objects.get(pk=task.pk).completed)

    def test_an_error_halfway_leaves_the_products_as_they_were(self):
        task = self.address_change(self.new_address)
        with mock.patch.object(ScheduledTask, "save", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                task.execute()
        self.assert_product_untouched()

    def test_the_command_warns_and_goes_on_with_the_rest(self):
        orphan = self.address_change(self.new_address)
        self.new_address.delete()
        other_contact = create_contact(name="Otra", phone="099444222")
        other_subscription = create_subscription(other_contact)
        other_sp = SubscriptionProduct.objects.create(subscription=other_subscription, product=self.product)
        other_address = create_address("Mercedes 55", other_contact)
        other = ScheduledTask.objects.create(
            contact=other_contact, category="AC", execution_date=date.today(), address=other_address
        )
        other.subscription_products.add(other_sp)

        with mock.patch("support.management.commands.run_scheduled_tasks.sentry_sdk") as sentry:
            call_command("run_scheduled_tasks", stderr=mock.MagicMock())

        self.assertFalse(ScheduledTask.objects.get(pk=orphan.pk).completed)
        self.assertTrue(ScheduledTask.objects.get(pk=other.pk).completed)
        self.assert_product_untouched()
        sentry.capture_message.assert_called_once()
        self.assertEqual(sentry.capture_message.call_args.kwargs["level"], "warning")
        sentry.capture_exception.assert_not_called()

    @override_settings(SCHEDULED_TASK_NOTIFY_RECIPIENTS=["logistica@example.com"])
    def test_deleting_the_address_of_a_pending_change_sends_one_mail(self):
        task = self.address_change(self.new_address)
        with self.captureOnCommitCallbacks(execute=True):
            self.new_address.delete()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["logistica@example.com"])
        self.assertIn("Canelones 999", mail.outbox[0].body)
        self.assertIn(f"#{task.id}", mail.outbox[0].body)
        self.assertIn("Paper product", mail.outbox[0].body)

    @override_settings(SCHEDULED_TASK_NOTIFY_RECIPIENTS=["logistica@example.com"])
    def test_no_mail_for_a_completed_change(self):
        task = self.address_change(self.new_address)
        ScheduledTask.objects.filter(pk=task.pk).update(completed=True)
        with self.captureOnCommitCallbacks(execute=True):
            self.new_address.delete()
        self.assertEqual(mail.outbox, [])

    @override_settings(SCHEDULED_TASK_NOTIFY_RECIPIENTS=["logistica@example.com"])
    def test_no_mail_when_the_whole_contact_is_deleted(self):
        self.address_change(self.new_address)
        with self.captureOnCommitCallbacks(execute=True):
            self.contact.delete()
        self.assertEqual(mail.outbox, [])
        self.assertFalse(Address.objects.filter(pk=self.new_address.pk).exists())
