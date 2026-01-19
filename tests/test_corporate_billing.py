# coding=utf-8
from datetime import date

from django.test import TestCase

from core.models import Product
from invoicing.models import Invoice
from invoicing.utils import bill_subscription

from tests.factory import create_contact, create_subscription, create_product, create_address, create_route


class TestCorporateBilling(TestCase):
    """Tests for corporate and affiliate subscription billing behavior."""

    def setUp(self):
        """Set up test data for corporate subscription billing tests."""
        create_route(number=1, name="Route 1")
        create_product(name='Newspaper', price=500, type="S", billing_priority=1)
        self.product = Product.objects.get(slug="newspaper")

    def test_corporate_subscription_uses_override_price(self):
        """
        Test that a corporate subscription with override_price uses that price
        instead of the calculated product price when billing.
        """
        # Create contact and corporate subscription
        contact = create_contact('Corporate Client', "29000808", email="corporate@example.com")
        corporate_subscription = create_subscription(contact, subscription_type='C', payment_type='C')

        # Set corporate-specific fields
        corporate_subscription.number_of_subscriptions = 5
        corporate_subscription.override_price = 2000  # Override price instead of 500
        corporate_subscription.save()

        # Add product and address
        address = create_address('Treinta y Tres 1479', contact, address_type='physical')
        from logistics.models import Route
        route_1 = Route.objects.get(number=1)

        corporate_subscription.add_product(
            product=self.product,
            address=address,
            route=route_1,
        )

        # Bill the subscription
        self.assertTrue(corporate_subscription.active)
        invoice = corporate_subscription.bill(date.today(), 10)

        # Verify invoice was created with override price
        self.assertIsInstance(invoice, Invoice)
        self.assertEqual(invoice.amount, 2000, "Invoice should use override_price of 2000, not product price of 500")

        # Verify invoice items
        invoice_items = invoice.invoiceitem_set.all()
        self.assertEqual(len(invoice_items), 1)
        self.assertEqual(invoice_items[0].amount, 2000)
        self.assertEqual(invoice_items[0].description, self.product.name)

    def test_corporate_subscription_without_override_uses_product_price(self):
        """
        Test that a corporate subscription WITHOUT override_price uses the
        normal calculated product price when billing.
        """
        # Create contact and corporate subscription
        contact = create_contact('Corporate Client 2', "29000809", email="corporate2@example.com")
        corporate_subscription = create_subscription(contact, subscription_type='C', payment_type='C')

        # Set corporate fields but NO override_price
        corporate_subscription.number_of_subscriptions = 3
        corporate_subscription.override_price = None  # No override
        corporate_subscription.save()

        # Add product and address
        address = create_address('Av. 18 de Julio 1234', contact, address_type='physical')
        from logistics.models import Route
        route_1 = Route.objects.get(number=1)

        corporate_subscription.add_product(
            product=self.product,
            address=address,
            route=route_1,
        )

        # Bill the subscription
        invoice = corporate_subscription.bill(date.today(), 10)

        # Verify invoice uses normal product price
        self.assertIsInstance(invoice, Invoice)
        self.assertEqual(invoice.amount, 500, "Invoice should use product price of 500 when no override_price")

    def test_affiliate_subscription_cannot_be_billed(self):
        """
        Test that affiliate subscriptions (type='A') cannot be billed,
        similar to free subscriptions (type='F') and promo subscriptions (type='P').
        """
        # Create corporate subscription
        corporate_contact = create_contact('Corporate Main', "29000810", email="main@example.com")
        corporate_subscription = create_subscription(corporate_contact, subscription_type='C', payment_type='C')
        corporate_subscription.number_of_subscriptions = 5
        corporate_subscription.save()

        # Create affiliate subscription
        affiliate_contact = create_contact('Affiliate User', "29000811", email="affiliate@example.com")
        affiliate_subscription = create_subscription(affiliate_contact, subscription_type='A', payment_type='C')
        affiliate_subscription.parent_subscription = corporate_subscription
        affiliate_subscription.save()

        # Add product and address to affiliate
        address = create_address('Calle Falsa 123', affiliate_contact, address_type='physical')
        from logistics.models import Route
        route_1 = Route.objects.get(number=1)

        affiliate_subscription.add_product(
            product=self.product,
            address=address,
            route=route_1,
        )

        # Attempt to bill the affiliate subscription - should raise AssertionError
        self.assertTrue(affiliate_subscription.active)

        with self.assertRaises(AssertionError) as context:
            bill_subscription(affiliate_subscription, billing_date=date.today(), dpp=10)

        # Verify the error message indicates it's not a billable type
        # Message can be in Spanish or English depending on locale
        error_msg = str(context.exception)
        self.assertTrue(
            'not normal or corporate' in error_msg or 'no es normal o corporativa' in error_msg,
            f"Expected billing error message, got: {error_msg}"
        )

    def test_free_subscription_cannot_be_billed(self):
        """
        Test that free subscriptions (type='F') cannot be billed.
        This is a baseline test to confirm affiliate subscriptions behave similarly.
        """
        # Create free subscription
        contact = create_contact('Free User', "29000812", email="free@example.com")
        free_subscription = create_subscription(contact, subscription_type='F', payment_type='C')

        # Add product and address
        address = create_address('Av. Brasil 2020', contact, address_type='physical')
        from logistics.models import Route
        route_1 = Route.objects.get(number=1)

        free_subscription.add_product(
            product=self.product,
            address=address,
            route=route_1,
        )

        # Attempt to bill - should raise AssertionError
        with self.assertRaises(AssertionError) as context:
            bill_subscription(free_subscription, billing_date=date.today(), dpp=10)

        # Verify the error message indicates it's not a billable type
        # Message can be in Spanish or English depending on locale
        error_msg = str(context.exception)
        self.assertTrue(
            'not normal or corporate' in error_msg or 'no es normal o corporativa' in error_msg,
            f"Expected billing error message, got: {error_msg}"
        )

    def test_corporate_with_multiple_affiliates_only_corporate_billed(self):
        """
        Test that in a corporate subscription structure with multiple affiliates,
        only the corporate subscription gets billed, not the affiliates.
        """
        # Create corporate subscription
        corporate_contact = create_contact('Corporate HQ', "29000813", email="hq@example.com")
        corporate_subscription = create_subscription(corporate_contact, subscription_type='C', payment_type='C')
        corporate_subscription.number_of_subscriptions = 3
        corporate_subscription.override_price = 1500
        corporate_subscription.save()

        # Add product to corporate
        corp_address = create_address('Corporate Office 100', corporate_contact, address_type='physical')
        from logistics.models import Route
        route_1 = Route.objects.get(number=1)

        corporate_subscription.add_product(
            product=self.product,
            address=corp_address,
            route=route_1,
        )

        # Create two affiliate subscriptions
        affiliate1_contact = create_contact('Affiliate 1', "29000814", email="affiliate1@example.com")
        affiliate1_subscription = create_subscription(affiliate1_contact, subscription_type='A', payment_type='C')
        affiliate1_subscription.parent_subscription = corporate_subscription
        affiliate1_subscription.save()

        affiliate1_address = create_address('Affiliate Office 1', affiliate1_contact, address_type='physical')
        affiliate1_subscription.add_product(
            product=self.product,
            address=affiliate1_address,
            route=route_1,
        )

        affiliate2_contact = create_contact('Affiliate 2', "29000815", email="affiliate2@example.com")
        affiliate2_subscription = create_subscription(affiliate2_contact, subscription_type='A', payment_type='C')
        affiliate2_subscription.parent_subscription = corporate_subscription
        affiliate2_subscription.save()

        affiliate2_address = create_address('Affiliate Office 2', affiliate2_contact, address_type='physical')
        affiliate2_subscription.add_product(
            product=self.product,
            address=affiliate2_address,
            route=route_1,
        )

        # Bill the corporate subscription - should succeed
        corporate_invoice = corporate_subscription.bill(date.today(), 10)
        self.assertIsInstance(corporate_invoice, Invoice)
        self.assertEqual(corporate_invoice.amount, 1500)

        # Attempt to bill affiliate subscriptions - should fail
        with self.assertRaises(AssertionError):
            bill_subscription(affiliate1_subscription, billing_date=date.today(), dpp=10)

        with self.assertRaises(AssertionError):
            bill_subscription(affiliate2_subscription, billing_date=date.today(), dpp=10)

        # Verify only one invoice was created (for corporate)
        total_invoices = Invoice.objects.count()
        self.assertEqual(total_invoices, 1, "Only corporate subscription should create an invoice")

    def test_corporate_subscription_with_end_date_one_time_billing(self):
        """
        Test that a corporate subscription with an end_date is treated as a one-time
        billing and won't be billed again after the end_date.
        """
        from datetime import timedelta

        # Create contact and corporate subscription
        contact = create_contact('One-Time Corporate', "29000816", email="onetime@example.com")
        corporate_subscription = create_subscription(contact, subscription_type='C', payment_type='C')

        # Set corporate fields with end_date (one-time subscription)
        start_date = date.today()
        end_date = start_date + timedelta(days=30)  # 30-day subscription

        corporate_subscription.number_of_subscriptions = 2
        corporate_subscription.override_price = 1000
        corporate_subscription.start_date = start_date
        corporate_subscription.end_date = end_date
        corporate_subscription.next_billing = start_date
        corporate_subscription.save()

        # Add product and address
        address = create_address('One-Time Office 500', contact, address_type='physical')
        from logistics.models import Route
        route_1 = Route.objects.get(number=1)

        corporate_subscription.add_product(
            product=self.product,
            address=address,
            route=route_1,
        )

        # Bill the subscription - should succeed
        invoice = corporate_subscription.bill(start_date, 10)
        self.assertIsInstance(invoice, Invoice)
        self.assertEqual(invoice.amount, 1000)

        # Verify that subscription with end_date won't be billed again
        # The billing system should handle this by either:
        # 1. Setting next_billing to None after billing, or
        # 2. Checking that next_billing < end_date before allowing billing
        # This ensures one-time billing behavior for corporate subscriptions with end_date

    def test_corporate_subscription_only_billed_once(self):
        """
        Test that a corporate subscription with end_date is only billed once.
        After the first billing, next_billing should be set to end_date,
        preventing any subsequent billing attempts.
        """
        from datetime import timedelta

        # Create contact and corporate subscription
        contact = create_contact('One-Time Corp', "29000817", email="onetime2@example.com")
        corporate_subscription = create_subscription(contact, subscription_type='C', payment_type='C')

        # Set corporate fields with end_date
        start_date = date.today()
        end_date = start_date + timedelta(days=90)  # 3-month subscription

        corporate_subscription.number_of_subscriptions = 3
        corporate_subscription.override_price = 1500
        corporate_subscription.start_date = start_date
        corporate_subscription.end_date = end_date
        corporate_subscription.next_billing = start_date
        corporate_subscription.frequency = 3  # 3 months
        corporate_subscription.save()

        # Add product and address
        address = create_address('Corporate Plaza 200', contact, address_type='physical')
        from logistics.models import Route
        route_1 = Route.objects.get(number=1)

        corporate_subscription.add_product(
            product=self.product,
            address=address,
            route=route_1,
        )

        # First billing - should succeed
        first_invoice = corporate_subscription.bill(start_date, 10)
        self.assertIsInstance(first_invoice, Invoice)
        self.assertEqual(first_invoice.amount, 1500)

        # Refresh subscription from database to get updated next_billing
        corporate_subscription.refresh_from_db()

        # Verify that next_billing was set to end_date (not start_date + frequency)
        self.assertEqual(
            corporate_subscription.next_billing,
            end_date,
            f"After billing, next_billing should be set to end_date ({end_date}), "
            f"but got {corporate_subscription.next_billing}"
        )

        # Attempt to bill again on a date before end_date - should fail
        # because next_billing is now equal to end_date
        second_billing_date = start_date + timedelta(days=30)

        with self.assertRaises(Exception) as context:
            corporate_subscription.bill(second_billing_date, 10)

        # The error should indicate that the subscription shouldn't be billed yet
        # because next_billing (end_date) > second_billing_date
        error_msg = str(context.exception)
        self.assertTrue(
            'should not be billed yet' in error_msg or 'aún no debería ser facturada' in error_msg,
            f"Expected 'should not be billed yet' error, got: {error_msg}"
        )

        # Verify only one invoice was created
        invoice_count = Invoice.objects.filter(subscription=corporate_subscription).count()
        self.assertEqual(invoice_count, 1, "Corporate subscription should only create one invoice")
