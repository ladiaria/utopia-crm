# coding=utf-8
from django.test import TestCase, override_settings

from core.models import Contact
from core.utils import parse_copies, process_invoice_request
from invoicing.models import Invoice

from tests.factory import create_contact, create_product


@override_settings(WEB_UPDATE_USER_ENABLED=False)
class TestOneshotInvoice(TestCase):
    # The base repo ships no product catalogue: these are built by hand with prices that keep assertions readable.

    def setUp(self):
        self.book = create_product(name="Book", price=100, type="O")
        self.poster = create_product(name="Poster", price=30, type="O")

    def test_parse_copies(self):
        for value, expected in ((None, 1), ("", 1), ("3", 3), (2, 2), (" 4 ", 4)):
            with self.subTest(value=value):
                self.assertEqual(parse_copies(value), expected)
        for value in ("0", "-1", "abc", "2.5", 2.5, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_copies(value)

    def test_add_single_invoice_with_a_list_bills_one_copy_each(self):
        contact = create_contact("buyer", "29000808")
        invoice = contact.add_single_invoice_with_products([self.book, self.poster], "C")
        self.assertEqual(invoice.amount, 130)
        self.assertEqual(sorted(invoice.invoiceitem_set.values_list("copies", flat=True)), [1, 1])

    def test_add_single_invoice_with_copies(self):
        contact = create_contact("buyer", "29000808")
        invoice = contact.add_single_invoice_with_products({self.book: 3, self.poster: 1}, "C")
        self.assertEqual(invoice.amount, 330)
        self.assertEqual(invoice.invoiceitem_set.get(product=self.book).copies, 3)

    def test_process_invoice_request_copies_and_tags(self):
        data = process_invoice_request("book", "buyer@example.com", "", "Buyer", "", "C", copies="2")
        invoice = Invoice.objects.get(id=data["invoice_id"])
        self.assertEqual(invoice.amount, 200)
        self.assertEqual(set(invoice.contact.tags.names()), {"book-added"})

    def test_process_invoice_request_without_tags(self):
        data = process_invoice_request("book", "buyer@example.com", "", "Buyer", "", "C", add_tags=False)
        self.assertEqual(list(Contact.objects.get(id=data["contact_id"]).tags.names()), [])

    def test_invalid_copies_create_nothing(self):
        with self.assertRaises(ValueError):
            process_invoice_request("book", "buyer@example.com", "", "Buyer", "", "C", copies="0")
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(Contact.objects.filter(email="buyer@example.com").exists())
