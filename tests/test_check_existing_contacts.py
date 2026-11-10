from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.models import ContactCampaignStatus
from support.views.contacts import CheckForExistingContactsView
from tests.factories import CampaignFactory, ContactFactory, SubscriptionFactory


class CheckForExistingContactsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="staff", is_staff=True)
        cls.contact = ContactFactory(phone="+59899123456", mobile="", email="ana@example.com")
        cls.other_contact = ContactFactory(phone="+59829007654", mobile="", email="otra@example.com")

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("check_for_existing_contacts")

    def upload(self, content, button):
        csv_file = SimpleUploadedFile("check.csv", content.encode("utf-8"), content_type="text/csv")
        response = self.client.post(self.url, {"file": csv_file, button: "1"})
        self.assertEqual(response.status_code, 200)
        return response.context

    def check_phones(self, *values):
        return self.upload("\n".join(["phone", *values]) + "\n", "check_phone")

    def matched_contacts(self, context):
        return [result["contact"].id for result in context["results"]]

    def test_value_without_digits_is_not_searched(self):
        context = self.check_phones("N/A", "sin telefono", "-")

        self.assertEqual(context["results"], [])
        self.assertEqual(context["non_matches"], [])
        self.assertEqual(
            context["not_searched_phones"],
            [
                {"value": "N/A", "row_number": 1},
                {"value": "sin telefono", "row_number": 2},
                {"value": "-", "row_number": 3},
            ],
        )

    def test_too_few_digits_are_not_searched(self):
        context = self.check_phones("0", "099", "123456")

        self.assertEqual(context["results"], [])
        self.assertEqual(len(context["not_searched_phones"]), 3)

    def test_symbols_do_not_count_as_digits(self):
        context = self.check_phones("+99-12-34")

        self.assertEqual(context["results"], [])
        self.assertEqual(context["not_searched_phones"], [{"value": "+99-12-34", "row_number": 1}])

    def test_minimum_digits_are_searched(self):
        context = self.check_phones("9123456")

        self.assertEqual(self.matched_contacts(context), [self.contact.id])
        self.assertEqual(context["not_searched_phones"], [])

    def test_formatted_number_is_searched(self):
        context = self.check_phones("+598 99 123 456")

        self.assertEqual(self.matched_contacts(context), [self.contact.id])

    def test_rows_keep_their_number_in_each_list(self):
        context = self.check_phones("+59899123456", "N/A", "+59891000000")

        self.assertEqual(self.matched_contacts(context), [self.contact.id])
        self.assertEqual(context["results"][0]["csv_row"], 1)
        self.assertEqual(context["not_searched_phones"], [{"value": "N/A", "row_number": 2}])
        self.assertEqual(context["non_matches"], [{"value": "+59891000000", "row_number": 3}])

    def test_leading_zero_finds_the_number_stored_with_country_code(self):
        context = self.check_phones("099123456")

        self.assertEqual(self.matched_contacts(context), [self.contact.id])
        self.assertEqual(context["non_matches"], [])
        self.assertTrue(context["results"][0]["phone_matches"])
        self.assertFalse(context["results"][0]["mobile_matches"])

    def test_leading_zero_also_finds_the_mobile(self):
        contact = ContactFactory(phone="", mobile="+59891222333")

        context = self.check_phones("091222333")

        self.assertEqual(self.matched_contacts(context), [contact.id])
        self.assertFalse(context["results"][0]["phone_matches"])
        self.assertTrue(context["results"][0]["mobile_matches"])

    def test_international_prefix_finds_the_number(self):
        context = self.check_phones("00598 99 123 456")

        self.assertEqual(self.matched_contacts(context), [self.contact.id])

    def test_number_stored_with_the_leading_zero_is_still_found(self):
        # Raw SQL: the field would normalize it, and these are old rows that kept the 0
        with connection.cursor() as cursor:
            cursor.execute("UPDATE core_contact SET phone = %s WHERE id = %s", ["0234567890", self.other_contact.pk])

        for value in ("0234567890", "234567890"):
            with self.subTest(value=value):
                self.assertEqual(self.matched_contacts(self.check_phones(value)), [self.other_contact.id])

    def test_leading_zeros_do_not_count_for_the_minimum(self):
        context = self.check_phones("0000000", "0123456")

        self.assertEqual(context["results"], [])
        self.assertEqual(context["non_matches"], [])
        self.assertEqual(len(context["not_searched_phones"]), 2)

    def test_excel_utf8_csv_finds_the_contact(self):
        context = self.upload("﻿email\nANA@example.com\n", "check_email")

        self.assertEqual(self.matched_contacts(context), [self.contact.id])

    def test_email_check_has_no_not_searched_list(self):
        context = self.upload("email\nnadie@example.com\n", "check_email")

        self.assertEqual(context["not_searched_phones"], [])
        self.assertEqual(context["non_matches"], [{"value": "nadie@example.com", "row_number": 1}])

    @override_settings(LANGUAGE_CODE="en")
    def test_csv_saved_by_excel_as_latin1_finds_the_contact(self):
        contact = ContactFactory(phone="", mobile="", email="jose@example.com")
        content = "nombre,email\nJosé,jose@example.com\n".encode("latin-1")
        csv_file = SimpleUploadedFile("check.csv", content, content_type="text/csv")

        response = self.client.post(self.url, {"file": csv_file, "check_email": "1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.matched_contacts(response.context), [contact.id])

    def test_row_with_fewer_columns_than_the_header(self):
        context = self.upload("nombre,email\nAna,ANA@example.com\nSin columna\n", "check_email")

        self.assertEqual(self.matched_contacts(context), [self.contact.id])
        self.assertEqual(context["non_matches"], [{"value": "N/A", "row_number": 2}])

    def test_row_with_fewer_columns_than_the_header_for_phones(self):
        context = self.upload("nombre,phone\nAna,099123456\nSin columna\n", "check_phone")

        self.assertEqual(self.matched_contacts(context), [self.contact.id])
        self.assertEqual(context["not_searched_phones"], [{"value": "", "row_number": 2}])

    def test_email_keeps_row_order_and_ignores_case(self):
        context = self.upload("email\notra@example.com\nnadie@example.com\nANA@example.com\n", "check_email")

        self.assertEqual([r["csv_row"] for r in context["results"]], [1, 3])
        self.assertEqual(self.matched_contacts(context), [self.other_contact.id, self.contact.id])
        self.assertEqual(context["non_matches"], [{"value": "nadie@example.com", "row_number": 2}])

    def test_results_show_active_subscription_and_campaign(self):
        SubscriptionFactory(contact=self.contact, active=True, status="OK")
        SubscriptionFactory(contact=self.other_contact, active=False, status="OK")
        ContactCampaignStatus.objects.create(contact=self.contact, campaign=CampaignFactory(active=True))
        ContactCampaignStatus.objects.create(contact=self.other_contact, campaign=CampaignFactory(active=False))

        for button, content in (
            ("check_email", "email\nana@example.com\notra@example.com\n"),
            ("check_phone", "phone\n099123456\n029007654\n"),
        ):
            with self.subTest(button=button):
                results = {r["contact"].id: r for r in self.upload(content, button)["results"]}
                self.assertTrue(results[self.contact.id]["has_active_subscription"])
                self.assertTrue(results[self.contact.id]["is_in_active_campaign"])
                self.assertFalse(results[self.other_contact.id]["has_active_subscription"])
                self.assertFalse(results[self.other_contact.id]["is_in_active_campaign"])

    def count_queries(self, content, button):
        with CaptureQueriesContext(connection) as queries:
            self.upload(content, button)
        return len(queries)

    def test_emails_do_not_add_a_query_per_row(self):
        for i in range(10):
            ContactFactory(phone="", mobile="", email=f"persona{i}@example.com")
        one = "email\npersona0@example.com\n"
        many = "email\n" + "".join(f"persona{i}@example.com\n" for i in range(10))

        self.assertEqual(self.count_queries(many, "check_email"), self.count_queries(one, "check_email"))

    def test_phones_make_one_query_per_row(self):
        for i in range(10):
            ContactFactory(phone=f"+5989912340{i}", mobile="", email=f"persona{i}@example.com")
        one = "phone\n099123400\n"
        many = "phone\n" + "".join(f"09912340{i}\n" for i in range(10))

        self.assertEqual(self.count_queries(many, "check_phone"), self.count_queries(one, "check_phone") + 9)

    def test_instructions_show_the_minimum(self):
        minimum = CheckForExistingContactsView.min_phone_digits

        self.assertContains(self.client.get(self.url), f"Values with fewer than {minimum} digits, not counting leading zeros")
