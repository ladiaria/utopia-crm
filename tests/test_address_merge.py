# coding=utf-8
"""
Address.merge_other_address_into_this: everything pointing to the merged address goes to the one that stays.

Every FK to Address has to move. The billing address of a subscription is SET_NULL, and it was left out: merging an
address used for billing left the subscription with no billing address and nobody noticed. The default mark has to
move too, or the contact is left with no default address, and deleting a default address tells the web the contact
has none. All of it runs in one transaction.
"""
from datetime import date
from unittest import mock

from django.test import TestCase, override_settings

from core.models import Address, Subscription, SubscriptionProduct
from support.models import Issue, ScheduledTask

from tests.factory import create_address, create_contact, create_product, create_subscription


class TestAddressMerge(TestCase):
    def setUp(self):
        self.contact = create_contact(name="Merge", phone="099333111")
        self.target = create_address("Havre 1910", self.contact)
        self.source = create_address("havre 1910", self.contact)
        self.subscription = create_subscription(self.contact)
        self.product = create_product("Paper product", 100)

    def test_everything_pointing_to_the_source_moves(self):
        sp = SubscriptionProduct.objects.create(
            subscription=self.subscription, product=self.product, address=self.source
        )
        Subscription.objects.filter(pk=self.subscription.pk).update(billing_address=self.source)
        issue = Issue.objects.create(contact=self.contact, date=date.today(), address=self.source)
        task = ScheduledTask.objects.create(
            contact=self.contact, category="AC", execution_date=date.today(), address=self.source
        )

        self.assertEqual(self.target.merge_other_address_into_this(self.source, notes=""), [])

        self.assertFalse(Address.objects.filter(pk=self.source.pk).exists())
        sp.refresh_from_db()
        self.subscription.refresh_from_db()
        self.assertEqual(sp.address, self.target)
        self.assertEqual(self.subscription.billing_address, self.target)
        self.assertEqual(Issue.objects.get(pk=issue.pk).address, self.target)
        self.assertEqual(ScheduledTask.objects.get(pk=task.pk).address, self.target)

    def test_the_default_mark_moves(self):
        Address.objects.filter(pk=self.source.pk).update(default=True)
        self.source.refresh_from_db()
        self.target.merge_other_address_into_this(self.source, notes="")
        self.target.refresh_from_db()
        self.assertTrue(self.target.default)

    def test_an_explicit_default_wins(self):
        Address.objects.filter(pk=self.source.pk).update(default=True)
        self.source.refresh_from_db()
        self.target.merge_other_address_into_this(self.source, notes="", default=False)
        self.target.refresh_from_db()
        self.assertFalse(self.target.default)

    @override_settings(WEB_UPDATE_USER_ENABLED=True)
    def test_the_web_is_not_told_the_contact_has_no_address(self):
        Address.objects.filter(pk=self.source.pk).update(default=True)
        self.source.refresh_from_db()
        with mock.patch("core.signals.cms_address_api_call") as api_call:
            self.target.merge_other_address_into_this(self.source, notes="")
        # Only calls with the address that stays: a call with no address clears it on the web
        for call in api_call.call_args_list:
            self.assertEqual(call.args, (self.contact, self.target))

    def test_an_error_halfway_leaves_both_addresses_as_they_were(self):
        sp = SubscriptionProduct.objects.create(
            subscription=self.subscription, product=self.product, address=self.source
        )
        with mock.patch.object(Address, "delete", side_effect=RuntimeError("boom")):
            errors = self.target.merge_other_address_into_this(self.source, notes="merged")
        self.assertEqual(errors, ["boom"])
        sp.refresh_from_db()
        self.assertEqual(sp.address, self.source)
        self.assertNotEqual(Address.objects.get(pk=self.target.pk).notes, "merged")

    def test_an_address_is_not_merged_into_itself(self):
        self.assertTrue(self.target.merge_other_address_into_this(self.target))
        self.assertTrue(Address.objects.filter(pk=self.target.pk).exists())
