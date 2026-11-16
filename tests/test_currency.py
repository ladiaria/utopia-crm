# coding=utf-8
"""
The currency of subscriptions and invoices (it/utopia-crm-ladiaria#120): the invoice copies the subscription's, and a
subscription in a currency other than the local one is never billed at a converted price.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext

from core.models import Product, Subscription
from core.templatetags.core_tags import with_currency
from invoicing.models import CreditNote, Invoice, InvoiceItem
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


class ShownCurrencyTests(TestCase):
    """The currency is informative: shown in the screens, never edited there."""

    def test_in_default_currency(self):
        subscription = create_subscription(create_contact("Shown currency", "29000124"))
        self.assertTrue(subscription.in_default_currency)
        subscription.currency = "USD"
        self.assertFalse(subscription.in_default_currency)

    def test_the_invoice_detail_shows_the_currency_and_the_exchange_rate(self):
        user = User.objects.create_superuser(username="currency_detail", password="x")
        self.client.force_login(user)
        invoice = Invoice.objects.create(
            contact=create_contact("Invoice detail currency", "29000125"),
            creation_date=date(2026, 11, 10),
            expiration_date=date(2026, 11, 20),
            service_from=date(2026, 11, 10),
            service_to=date(2026, 12, 10),
            amount=Decimal("6.50"),
            currency="USD",
            exchange_rate=Decimal("40.214000"),
        )
        response = self.client.get(reverse("invoice_detail", args=[invoice.pk]))
        self.assertContains(response, "<p>USD</p>", html=True)
        self.assertContains(response, "40.214000")

    def test_the_invoice_detail_shows_the_billing_country_only_when_it_has_one(self):
        user = User.objects.create_superuser(username="billing_country_detail", password="x")
        self.client.force_login(user)
        abroad, local = (
            Invoice.objects.create(
                contact=create_contact(name, document),
                creation_date=date(2026, 11, 10),
                expiration_date=date(2026, 11, 20),
                service_from=date(2026, 11, 10),
                service_to=date(2026, 12, 10),
                amount=Decimal("7.00"),
                billing_country=country,
            )
            for name, document, country in (
                ("Billing country abroad", "29000127", "Estados Unidos"),
                ("Billing country local", "29000128", None),
            )
        )
        label = gettext("Billing Country")
        response = self.client.get(reverse("invoice_detail", args=[abroad.pk]))
        self.assertContains(response, label)
        self.assertContains(response, "<p>Estados Unidos</p>", html=True)
        # The local invoices don't fill it in: no empty field for them
        self.assertNotContains(self.client.get(reverse("invoice_detail", args=[local.pk])), label)

    def test_the_contact_screen_shows_no_price_for_another_currency(self):
        user = User.objects.create_superuser(username="currency_contact", password="x")
        self.client.force_login(user)
        contact = create_contact("Contact USD subscription", "29000126")
        subscription = create_subscription(contact)
        Subscription.objects.filter(pk=subscription.pk).update(currency="USD", balance=Decimal("2.50"))
        response = self.client.get(reverse("contact_detail", args=[contact.pk]))
        # Neither a local price nor a line saying there is none: the currency goes on the line below (#143)
        self.assertNotContains(response, "fa-dollar-sign text-success")
        self.assertContains(response, "USD 2.50")


class WithCurrencyFilterTests(TestCase):
    """Amounts in another currency say so; the ones in the local currency stay as they were (#143)."""

    def test_the_local_currency_is_left_as_is(self):
        self.assertEqual(with_currency(Decimal("500.00"), "UYU"), Decimal("500.00"))

    def test_another_currency_goes_in_front(self):
        self.assertEqual(with_currency(Decimal("6.00"), "USD"), "USD 6.00")
        with translation.override("es"):
            self.assertEqual(with_currency(Decimal("6.00"), "USD"), "USD 6,00")

    def test_no_amount_is_left_as_is(self):
        self.assertIsNone(with_currency(None, "USD"))
        self.assertEqual(with_currency("", "USD"), "")

    def test_invoice_in_default_currency(self):
        self.assertTrue(Invoice(currency="UYU").in_default_currency)
        self.assertFalse(Invoice(currency="USD").in_default_currency)


class AmountsWithCurrencyScreenTests(TestCase):
    """The screens that show invoice amounts put the currency in front of the ones that are not local (#143)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="amounts_currency", password="x")
        cls.contact = create_contact("Amounts with currency", "29000129")
        cls.invoice = Invoice.objects.create(
            contact=cls.contact,
            creation_date=date(2026, 11, 10),
            expiration_date=date(2026, 11, 20),
            service_from=date(2026, 11, 10),
            service_to=date(2026, 12, 10),
            payment_date=date(2026, 11, 10),
            amount=Decimal("6.00"),
            currency="USD",
            paid=True,
        )
        InvoiceItem.objects.create(
            invoice=cls.invoice, amount=Decimal("7.00"), price=Decimal("7.00"), description="Producto", type="I"
        )
        InvoiceItem.objects.create(invoice=cls.invoice, amount=Decimal("1.00"), description="Descuento", type="D")

    def setUp(self):
        self.client.force_login(self.user)

    def test_the_latest_payment_does_not_read_as_pesos(self):
        response = self.client.get(reverse("contact_detail", args=[self.contact.pk]))
        self.assertContains(response, '<span class="text-success">USD 6.00</span>', html=True)
        self.assertNotContains(response, "$6.00")

    def test_the_invoices_tab(self):
        response = self.client.get(reverse("contact_invoices_htmx", args=[self.contact.pk]), HTTP_HX_REQUEST="true")
        self.assertContains(response, "<td>USD 6.00</td>", html=True)

    def test_the_invoice_detail(self):
        response = self.client.get(reverse("invoice_detail", args=[self.invoice.pk]))
        # Item amount and price, discount, and the totals
        self.assertContains(response, "<td>USD 7.00</td>", count=2, html=True)
        self.assertContains(response, "<td>USD 1.00</td>", html=True)
        self.assertContains(response, '<strong class="ms-2">USD 6.00</strong>', html=True)

    def test_the_local_currency_does_not_change(self):
        Invoice.objects.filter(pk=self.invoice.pk).update(currency="UYU")
        response = self.client.get(reverse("contact_detail", args=[self.contact.pk]))
        self.assertContains(response, '<span class="text-success">$6.00</span>', html=True)
        response = self.client.get(reverse("contact_invoices_htmx", args=[self.contact.pk]), HTTP_HX_REQUEST="true")
        self.assertContains(response, "<td>6.00</td>", html=True)
