# coding=utf-8
from datetime import date, timedelta

from django.test import TestCase

from invoicing.filters import InvoiceFilter
from invoicing.models import Invoice

from .factory import create_contact


class InvoiceFilterUncollectiblePaidTest(TestCase):
    """The uncollectible invoices that were collected anyway (it/utopia-crm-ladiaria#101)."""

    @classmethod
    def setUpTestData(cls):
        cls.contact = create_contact("Test", "099111222", "test@example.com")
        cls.paid = cls._invoice(uncollectible=True, paid=True)
        cls.debited = cls._invoice(uncollectible=True, debited=True)
        cls._invoice(uncollectible=True)
        cls._invoice(uncollectible=True, paid=True, canceled=True)
        cls._invoice(paid=True)
        cls._invoice(debited=True)
        cls._invoice()

    @classmethod
    def _invoice(cls, **flags):
        return Invoice.objects.create(
            contact=cls.contact,
            creation_date=date.today(),
            expiration_date=date.today() + timedelta(days=10),
            service_from=date.today(),
            service_to=date.today() + timedelta(days=30),
            amount=100,
            **flags,
        )

    def _filter(self, status):
        return InvoiceFilter({"status": status}, queryset=Invoice.objects.all()).qs

    def test_only_uncollectible_paid_or_debited_and_not_canceled(self):
        self.assertCountEqual(self._filter("uncollectible_paid_or_debited"), [self.paid, self.debited])

    def test_the_uncollectible_option_still_brings_all_of_them(self):
        self.assertEqual(self._filter("uncollectible").count(), 4)
