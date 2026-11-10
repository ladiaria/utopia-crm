# coding=utf-8
"""
Money totals never mix currencies (it/utopia-crm-ladiaria#123): they add up the local currency only, and what is in
another currency is shown apart, in its own.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from invoicing.models import Invoice
from util.currency import split_by_currency

from tests.factory import create_contact, create_product

HACE_UN_MES = date.today() - timedelta(days=30)


def create_invoice(contact, amount, currency="UYU", overdue=True, creation_date=HACE_UN_MES, **kwargs):
    return Invoice.objects.create(
        contact=contact,
        creation_date=creation_date,
        expiration_date=HACE_UN_MES + timedelta(days=10) if overdue else date.today() + timedelta(days=10),
        service_from=HACE_UN_MES,
        service_to=date.today(),
        amount=Decimal(amount),
        currency=currency,
        **kwargs,
    )


class SplitByCurrencyTests(TestCase):
    def test_splits_the_local_currency_from_the_rest(self):
        contact = create_contact("Split by currency", "29000128")
        create_invoice(contact, "500.00")
        create_invoice(contact, "6.50", currency="USD")
        create_invoice(contact, "13.00", currency="USD")
        local, others = split_by_currency(Invoice.objects.filter(contact=contact))
        self.assertEqual(list(local.values_list("amount", flat=True)), [Decimal("500.00")])
        self.assertEqual(others, [{"currency": "USD", "count": 2, "total": Decimal("19.50")}])

    def test_a_joined_queryset_does_not_add_a_row_up_twice(self):
        contact = create_contact("Joined split", "29000133")
        invoice = create_invoice(contact, "13.00", currency="USD")
        product = create_product("Joined product", 100)
        invoice.invoiceitem_set.create(product=product, amount=Decimal("6.50"), copies=1)
        invoice.invoiceitem_set.create(product=product, amount=Decimal("6.50"), copies=1)
        joined = Invoice.objects.filter(contact=contact, invoiceitem__product=product).distinct()
        self.assertEqual(split_by_currency(joined)[1], [{"currency": "USD", "count": 1, "total": Decimal("13.00")}])

    def test_with_the_local_currency_only_there_is_nothing_apart(self):
        contact = create_contact("Only local", "29000129")
        create_invoice(contact, "500.00")
        self.assertEqual(split_by_currency(Invoice.objects.filter(contact=contact))[1], [])


class ContactDebtTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.contact = create_contact("Debt in two currencies", "29000130")
        create_invoice(cls.contact, "500.00")
        create_invoice(cls.contact, "13.00", currency="USD")
        create_invoice(cls.contact, "700.00", overdue=False)  # not overdue: no debt
        cls.user = User.objects.create_superuser(username="debt_currency", password="x")

    def setUp(self):
        self.client.force_login(self.user)

    def test_the_debt_is_in_the_local_currency_and_the_rest_apart(self):
        self.assertEqual(self.contact.get_debt(), Decimal("500.00"))
        self.assertEqual(
            self.contact.get_debt_in_other_currencies(), [{"currency": "USD", "count": 1, "total": Decimal("13.00")}]
        )

    def test_the_contact_screen_shows_each_debt_in_its_currency(self):
        response = self.client.get(reverse("contact_detail", args=[self.contact.pk]))
        self.assertContains(response, "$500.00")
        self.assertContains(response, "Debt (USD):")
        self.assertContains(response, "USD 13")


class InvoiceFilterTotalsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        contact = create_contact("Filter totals", "29000131")
        create_invoice(contact, "500.00", creation_date=date.today())
        create_invoice(contact, "300.00", paid=True, creation_date=date.today())
        create_invoice(contact, "13.00", currency="USD", creation_date=date.today())
        create_invoice(contact, "6.50", currency="USD", paid=True, creation_date=date.today())
        cls.user = User.objects.create_superuser(username="filter_currency", password="x")

    def test_totals_count_the_local_currency_only_and_show_the_rest_apart(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("invoice_filter") + "?creation_date=today")
        self.assertEqual(response.context["invoices_count"], 2)
        self.assertEqual(response.context["invoices_sum"], Decimal("800.00"))
        self.assertEqual(response.context["paid_sum"], Decimal("300.00"))
        self.assertEqual(response.context["overdue_sum"], Decimal("500.00"))
        self.assertEqual(
            response.context["other_currencies"], [{"currency": "USD", "count": 2, "total": Decimal("19.50")}]
        )
        self.assertContains(response, "Not included in these totals")


class DebtorContactsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.debtor = create_contact("Debtor with history", "29000132")
        create_invoice(cls.debtor, "500.00")  # owed
        create_invoice(cls.debtor, "900.00", paid=True)  # paid long ago: not debt
        create_invoice(cls.debtor, "13.00", currency="USD")  # owed, in another currency
        cls.user = User.objects.create_superuser(username="debtors_currency", password="x")

    def test_the_debt_is_what_is_owed_in_the_local_currency(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("debtor_contacts"))
        debtor = next(c for c in response.context["page"].object_list if c.pk == self.debtor.pk)
        # It used to add up every invoice of the contact, paid ones included
        self.assertEqual(debtor.debt, Decimal("500.00"))
        self.assertEqual(response.context["sum"], Decimal("500.00"))
        self.assertEqual(
            response.context["other_currencies"], [{"currency": "USD", "count": 1, "total": Decimal("13.00")}]
        )
