from datetime import date

from django.db import connection
from django.test import SimpleTestCase, TestCase

from core.filters import ContactFilter, apply_main_filter
from core.models import Contact
from core.utils import phone_search_forms
from invoicing.filters import InvoiceFilter
from invoicing.models import Invoice
from support.filters import ScheduledTaskFilter
from support.models import ScheduledTask
from tests.factories import ContactFactory, InvoiceFactory


class PhoneSearchFormsTestCase(SimpleTestCase):
    def test_forms_of_what_a_person_types(self):
        cases = {
            "099123456": ["099123456", "99123456"],
            "99123456": ["99123456"],
            "+59899123456": ["59899123456"],
            "00598 99 123 456": ["0059899123456", "59899123456", "00598 99 123 456"],
            "099 123 456": ["099123456", "99123456", "099 123 456"],
            "099-123-456": ["099123456", "99123456", "099-123-456"],
            "  099123456  ": ["099123456", "99123456"],
        }
        for value, forms in cases.items():
            with self.subTest(value=value):
                self.assertEqual(phone_search_forms(value), forms)

    def test_few_digits_are_not_searched_without_the_zeros(self):
        self.assertEqual(phone_search_forms("0123"), ["0123"])
        self.assertEqual(phone_search_forms("0123456"), ["0123456"])
        self.assertEqual(phone_search_forms("01234567"), ["01234567", "1234567"])

    def test_zeros_alone_never_leave_an_empty_form(self):
        self.assertEqual(phone_search_forms("0000000"), ["0000000"])

    def test_without_digits_there_is_nothing_to_look_for(self):
        for value in ("", "   ", "+", "-", "N/A", "sin telefono"):
            with self.subTest(value=value):
                self.assertEqual(phone_search_forms(value), [])


class PhoneSearchTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.contact = ContactFactory(
            name="Ana", last_name="Pérez", phone="+59899123456", mobile="", work_phone="", email="ana@example.com"
        )
        cls.mobile_contact = ContactFactory(
            name="Beto", last_name="Rey", phone="", mobile="+59891222333", work_phone="", email="beto@example.com"
        )
        cls.other = ContactFactory(
            name="Otra", last_name="Sosa", phone="+59829007654", mobile="", work_phone="", email="otra@example.com"
        )

    # How a person may write the number of self.contact
    FOUND_VALUES = (
        "099123456",
        "99123456",
        "+59899123456",
        "099 123 456",
        "099-123-456",
        "(099) 123456",
        "00598 99 123 456",
    )


class ContactsBoxTestCase(PhoneSearchTestBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # The box needs it, but no migration creates it: INSTALL.md says to create it by hand
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    def search(self, value):
        return ContactFilter({"filter_multiple": value}, queryset=Contact.objects.all()).qs

    def test_finds_the_number_however_it_is_written(self):
        for value in self.FOUND_VALUES:
            with self.subTest(value=value):
                self.assertEqual(list(self.search(value)), [self.contact])

    def test_finds_the_mobile_and_the_work_phone(self):
        worker = ContactFactory(phone="", mobile="", work_phone="+59823334444", email="w@example.com")

        self.assertEqual(list(self.search("091222333")), [self.mobile_contact])
        self.assertEqual(list(self.search("023334444")), [worker])

    def test_partial_number_with_few_digits_still_works(self):
        self.assertEqual(list(self.search("9912")), [self.contact])

    def test_short_number_with_zero_is_not_searched_without_it(self):
        # 123 is in +59899123456, but 0123 is not: it may be part of a document
        self.assertEqual(list(self.search("0123")), [])

    def test_document_with_a_zero_keeps_being_found(self):
        contact = ContactFactory(phone="", mobile="", id_document="40123457", email="doc@example.com")

        self.assertEqual(list(self.search("0123")), [contact])

    def test_document_written_with_symbols_keeps_being_found(self):
        contact = ContactFactory(phone="", mobile="", id_document="1.234.567-8", email="doc2@example.com")

        self.assertEqual(list(self.search("1.234.567-8")), [contact])

    def test_text_with_a_digit_is_not_searched_as_a_number(self):
        # With the letters taken out it would look for 2 in every phone
        contact = ContactFactory(phone="", mobile="", email="ana2@example.com")

        self.assertEqual(list(self.search("ana2")), [contact])

    def test_name_with_two_words_keeps_being_a_name(self):
        self.assertEqual(list(self.search("Ana Pérez")), [self.contact])

    def test_symbols_alone_do_not_match_every_phone(self):
        self.assertEqual(list(self.search("+")), [])

    def test_number_stored_with_spaces_is_found_as_written(self):
        # Raw SQL: the field would normalize it, and these are old rows
        with connection.cursor() as cursor:
            cursor.execute("UPDATE core_contact SET phone = %s WHERE id = %s", ["062 2 0308", self.other.pk])

        self.assertEqual(list(self.search("062 2 0308")), [self.other])

    def test_search_contacts_htmx_uses_the_same_rule(self):
        self.assertEqual(list(apply_main_filter(Contact.objects.all(), "099 123 456")), [self.contact])


class ContactDataBoxTestCase(PhoneSearchTestBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.task = ScheduledTask.objects.create(contact=cls.contact, category="PS", execution_date=date(2026, 1, 1))
        cls.other_task = ScheduledTask.objects.create(contact=cls.other, category="PS", execution_date=date(2026, 1, 1))

    def search(self, value):
        return ScheduledTaskFilter({"contact_filter": value}, queryset=ScheduledTask.objects.all()).qs

    def test_finds_the_number_however_it_is_written(self):
        for value in self.FOUND_VALUES:
            with self.subTest(value=value):
                self.assertEqual(list(self.search(value)), [self.task])

    def test_other_contact_data_keeps_being_found(self):
        self.assertEqual(list(self.search("otra@example.com")), [self.other_task])

    def test_text_with_a_digit_does_not_match_every_phone(self):
        self.assertEqual(list(self.search("xx2")), [])


class InvoicePhoneBoxTestCase(PhoneSearchTestBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.invoice = InvoiceFactory(contact=cls.contact)
        cls.mobile_invoice = InvoiceFactory(contact=cls.mobile_contact)
        cls.other_invoice = InvoiceFactory(contact=cls.other)

    def search(self, value):
        return InvoiceFilter({"contact_phone": value}, queryset=Invoice.objects.all()).qs

    def test_finds_the_number_however_it_is_written(self):
        for value in self.FOUND_VALUES:
            with self.subTest(value=value):
                self.assertEqual(list(self.search(value)), [self.invoice])

    def test_finds_the_mobile(self):
        self.assertEqual(list(self.search("091222333")), [self.mobile_invoice])

    def test_without_digits_finds_nothing(self):
        for value in ("+", "N/A", "-"):
            with self.subTest(value=value):
                self.assertEqual(list(self.search(value)), [])
