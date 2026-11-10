# coding=utf-8
"""
The currency of subscriptions and invoices (it/utopia-crm-ladiaria#120): the invoice copies the subscription's, and a
subscription in a currency other than the local one is never billed at a converted price.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings

from core.models import Product, Subscription
from invoicing.models import CreditNote, Invoice
from util.currency import get_default_currency, is_default_currency

from tests.factory import create_address, create_contact, create_product, create_route, create_subscription


class DefaultCurrencyTests(TestCase):
    def test_new_subscriptions_and_invoices_are_in_the_local_currency(self):
        contact = create_contact("Currency default", "29000120")
        subscription = create_subscription(contact)
        invoice = Invoice.objects.create(
            contact=contact,
            creation_date=date(2026, 11, 10),
            expiration_date=date(2026, 11, 20),
            service_from=date(2026, 11, 10),
            service_to=date(2026, 12, 10),
            amount=Decimal("500.00"),
        )
        self.assertEqual(subscription.currency, "UYU")
        self.assertEqual(invoice.currency, "UYU")
        self.assertIsNone(invoice.exchange_rate)

    @override_settings(DEFAULT_CURRENCY="ARS")
    def test_the_default_is_read_from_settings_when_the_row_is_created(self):
        # A callable default: the migration does not freeze the value of the settings that generated it
        self.assertEqual(get_default_currency(), "ARS")
        self.assertTrue(is_default_currency("ARS"))
        self.assertFalse(is_default_currency("UYU"))
        self.assertEqual(create_subscription(create_contact("Currency ARS", "29000121")).currency, "ARS")


class BillingCurrencyTests(TestCase):
    def setUp(self):
        self.route = create_route(number=1, name="Route 1")
        self.product = create_product(name="Newspaper", price=500, type="S", billing_priority=1)

    def subscription_with_product(self, name, currency=None):
        contact = create_contact(name, "29000122")
        subscription = create_subscription(contact)
        if currency:
            Subscription.objects.filter(pk=subscription.pk).update(currency=currency)
            subscription.refresh_from_db()
        address = create_address("Treinta y Tres 1479", contact, address_type="physical")
        subscription.add_product(product=Product.objects.get(pk=self.product.pk), address=address, route=self.route)
        return subscription

    def test_the_invoice_copies_the_subscription_currency(self):
        invoice = self.subscription_with_product("Billed in UYU").bill(date.today(), 10)
        self.assertIsInstance(invoice, Invoice)
        self.assertEqual(invoice.currency, "UYU")
        self.assertEqual(invoice.amount, self.product.price)

    def test_a_subscription_in_another_currency_is_not_billed(self):
        subscription = self.subscription_with_product("Billed in USD", currency="USD")
        with self.assertRaisesMessage(AssertionError, "The subscription is in USD"):
            subscription.bill(date.today(), 10)
        self.assertFalse(Invoice.objects.filter(subscription=subscription).exists())

    @override_settings(DEFAULT_CURRENCY="USD")
    def test_the_local_currency_is_the_one_in_settings(self):
        invoice = self.subscription_with_product("Billed in USD as local").bill(date.today(), 10)
        self.assertEqual(invoice.currency, "USD")


class CreditNoteAmountTests(TestCase):
    def test_keeps_the_cents(self):
        contact = create_contact("Credit note cents", "29000123")
        invoice = Invoice.objects.create(
            contact=contact,
            creation_date=date(2026, 11, 10),
            expiration_date=date(2026, 11, 20),
            service_from=date(2026, 11, 10),
            service_to=date(2026, 12, 10),
            amount=Decimal("4.99"),
        )
        note = CreditNote.objects.create(invoice=invoice, amount=Decimal("4.99"))
        note.refresh_from_db()
        self.assertEqual(note.amount, Decimal("4.99"))
