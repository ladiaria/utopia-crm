# coding=utf-8
from datetime import date, datetime, time
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from core.models import Subscription, SubscriptionProduct, Product
from tests.factories.core_factories import ContactFactory, AddressFactory, SubscriptionFactory


class TestSubscriptionProductOriginalDatetime(TestCase):
    """
    Tests for the populate_subscriptionproduct_original_date management command
    and the original_datetime field behavior.
    """

    fixtures = ["core_product"]

    def setUp(self):
        """Set up test data"""
        self.contact = ContactFactory()
        self.address = AddressFactory(contact=self.contact)
        self.product1 = Product.objects.filter(type="S").first()
        self.product2 = Product.objects.filter(type="S").last()

    def test_original_datetime_set_on_new_product(self):
        """
        Test that original_datetime is automatically set when a new SubscriptionProduct is created.
        """
        subscription = SubscriptionFactory(contact=self.contact)
        sp = subscription.add_product(self.product1, self.address)

        # The original_datetime should be set automatically due to default=timezone.now
        self.assertIsNotNone(sp.original_datetime)
        self.assertIsInstance(sp.original_datetime, datetime)

    def test_management_command_populates_null_original_datetime(self):
        """
        Test that the management command correctly populates NULL original_datetime fields.
        """
        # Create subscription with product
        subscription = SubscriptionFactory(contact=self.contact, start_date=date(2024, 1, 1))
        sp = subscription.add_product(self.product1, self.address)

        # Manually set original_datetime to None to simulate old data
        SubscriptionProduct.objects.filter(pk=sp.pk).update(original_datetime=None)
        sp.refresh_from_db()
        self.assertIsNone(sp.original_datetime)

        # Run the management command
        out = StringIO()
        call_command('populate_subscriptionproduct_original_date', stdout=out)

        # Check that original_datetime was populated
        sp.refresh_from_db()
        self.assertIsNotNone(sp.original_datetime)

        # Should be midnight on the subscription's start_date (naive datetime)
        expected_datetime = datetime.combine(date(2024, 1, 1), time(0, 0, 0))
        self.assertEqual(sp.original_datetime, expected_datetime)

    def test_product_added_in_original_subscription(self):
        """
        Test that a product in the original subscription gets the original start_date.
        """
        # Create original subscription
        original_sub = SubscriptionFactory(contact=self.contact, start_date=date(2024, 1, 1))
        sp1 = original_sub.add_product(self.product1, self.address)

        # Clear original_datetime to test command
        SubscriptionProduct.objects.filter(pk=sp1.pk).update(original_datetime=None)

        # Create updated subscription (subscription chain)
        updated_sub = Subscription.objects.create(
            contact=self.contact,
            start_date=date(2024, 6, 1),
            payment_type='O',
            updated_from=original_sub,
        )
        # Copy product to new subscription
        sp2 = updated_sub.add_product(self.product1, self.address)
        SubscriptionProduct.objects.filter(pk=sp2.pk).update(original_datetime=None)

        # Run command
        call_command('populate_subscriptionproduct_original_date', stdout=StringIO())

        # Both products should have the original subscription's start_date
        sp1.refresh_from_db()
        sp2.refresh_from_db()

        expected_datetime = datetime.combine(date(2024, 1, 1), time(0, 0, 0))
        self.assertEqual(sp1.original_datetime, expected_datetime)
        self.assertEqual(sp2.original_datetime, expected_datetime)

    def test_product_added_in_second_subscription(self):
        """
        Test that a product added in the 2nd subscription gets that subscription's start_date.
        """
        # Create original subscription with product1
        original_sub = SubscriptionFactory(contact=self.contact, start_date=date(2024, 1, 1))
        sp1 = original_sub.add_product(self.product1, self.address)
        SubscriptionProduct.objects.filter(pk=sp1.pk).update(original_datetime=None)

        # Create 2nd subscription with product1 AND product2 (new product)
        second_sub = Subscription.objects.create(
            contact=self.contact,
            start_date=date(2024, 6, 1),
            payment_type='O',
            updated_from=original_sub,
        )
        sp2 = second_sub.add_product(self.product1, self.address)  # Existing product
        sp3 = second_sub.add_product(self.product2, self.address)  # NEW product
        SubscriptionProduct.objects.filter(pk__in=[sp2.pk, sp3.pk]).update(original_datetime=None)

        # Run command
        call_command('populate_subscriptionproduct_original_date', stdout=StringIO())

        # Refresh all
        sp1.refresh_from_db()
        sp2.refresh_from_db()
        sp3.refresh_from_db()

        # product1 should have original subscription's date (Jan 1)
        expected_jan = datetime.combine(date(2024, 1, 1), time(0, 0, 0))
        self.assertEqual(sp1.original_datetime, expected_jan)
        self.assertEqual(sp2.original_datetime, expected_jan)

        # product2 should have second subscription's date (Jun 1)
        expected_jun = datetime.combine(date(2024, 6, 1), time(0, 0, 0))
        self.assertEqual(sp3.original_datetime, expected_jun)

    def test_product_added_in_third_subscription(self):
        """
        Test that a product added in the 3rd subscription gets that subscription's start_date.
        """
        # Create subscription chain: original -> second -> third
        original_sub = SubscriptionFactory(contact=self.contact, start_date=date(2024, 1, 1))
        original_sub.add_product(self.product1, self.address)

        second_sub = Subscription.objects.create(
            contact=self.contact,
            start_date=date(2024, 6, 1),
            payment_type='O',
            updated_from=original_sub,
        )
        second_sub.add_product(self.product1, self.address)

        third_sub = Subscription.objects.create(
            contact=self.contact,
            start_date=date(2024, 12, 1),
            payment_type='O',
            updated_from=second_sub,
        )
        third_sub.add_product(self.product1, self.address)
        sp_new = third_sub.add_product(self.product2, self.address)  # NEW product in 3rd sub

        # Clear all original_datetime values
        SubscriptionProduct.objects.all().update(original_datetime=None)

        # Run command
        call_command('populate_subscriptionproduct_original_date', stdout=StringIO())

        # product2 should have third subscription's date (Dec 1)
        sp_new.refresh_from_db()
        expected_dec = datetime.combine(date(2024, 12, 1), time(0, 0, 0))
        self.assertEqual(sp_new.original_datetime, expected_dec)

    def test_command_with_contact_id_filter(self):
        """
        Test that the --contact-id option correctly filters products.
        """
        # Create two contacts with subscriptions
        contact1 = ContactFactory()
        contact2 = ContactFactory()

        sub1 = SubscriptionFactory(contact=contact1, start_date=date(2024, 1, 1))
        sub2 = SubscriptionFactory(contact=contact2, start_date=date(2024, 1, 1))

        sp1 = sub1.add_product(self.product1, self.address)
        sp2 = sub2.add_product(self.product1, self.address)

        # Clear original_datetime
        SubscriptionProduct.objects.filter(pk__in=[sp1.pk, sp2.pk]).update(original_datetime=None)

        # Run command only for contact1
        call_command(
            'populate_subscriptionproduct_original_date',
            contact_id=contact1.id,
            stdout=StringIO()
        )

        # Only sp1 should be updated
        sp1.refresh_from_db()
        sp2.refresh_from_db()

        self.assertIsNotNone(sp1.original_datetime)
        self.assertIsNone(sp2.original_datetime)

    def test_command_with_limit(self):
        """
        Test that the --limit option correctly limits processing.
        """
        # Create multiple subscription products
        subscription = SubscriptionFactory(contact=self.contact, start_date=date(2024, 1, 1))
        products = Product.objects.filter(type="S")[:3]

        sps = []
        for product in products:
            sp = subscription.add_product(product, self.address)
            sps.append(sp)

        # Clear original_datetime
        SubscriptionProduct.objects.filter(pk__in=[sp.pk for sp in sps]).update(original_datetime=None)

        # Run command with limit=1
        call_command(
            'populate_subscriptionproduct_original_date',
            limit=1,
            stdout=StringIO()
        )

        # Refresh all
        for sp in sps:
            sp.refresh_from_db()

        # Only one should be updated (we can't guarantee which one due to query ordering)
        updated_count = sum(1 for sp in sps if sp.original_datetime is not None)
        self.assertEqual(updated_count, 1)

    def test_command_dry_run(self):
        """
        Test that --dry-run doesn't actually save changes.
        """
        subscription = SubscriptionFactory(contact=self.contact, start_date=date(2024, 1, 1))
        sp = subscription.add_product(self.product1, self.address)

        # Clear original_datetime
        SubscriptionProduct.objects.filter(pk=sp.pk).update(original_datetime=None)
        sp.refresh_from_db()
        self.assertIsNone(sp.original_datetime)

        # Run command with dry-run
        call_command(
            'populate_subscriptionproduct_original_date',
            dry_run=True,
            stdout=StringIO()
        )

        # Should still be None
        sp.refresh_from_db()
        self.assertIsNone(sp.original_datetime)

    def test_naive_datetime_format(self):
        """
        Test that the command creates naive datetimes (USE_TZ=False).
        """
        subscription = SubscriptionFactory(contact=self.contact, start_date=date(2024, 1, 1))
        sp = subscription.add_product(self.product1, self.address)

        # Clear original_datetime
        SubscriptionProduct.objects.filter(pk=sp.pk).update(original_datetime=None)

        # Run command
        call_command('populate_subscriptionproduct_original_date', stdout=StringIO())

        # Check datetime
        sp.refresh_from_db()
        self.assertIsNotNone(sp.original_datetime)

        # Should be naive datetime (no timezone info, since USE_TZ=False)
        self.assertIsNone(sp.original_datetime.tzinfo)

        # Should match expected naive datetime
        expected_datetime = datetime.combine(date(2024, 1, 1), time(0, 0, 0))
        self.assertEqual(sp.original_datetime, expected_datetime)
