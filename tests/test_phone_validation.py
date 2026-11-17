# coding=utf-8
"""
Each of a contact's phone and mobile numbers records when and how it was confirmed to be theirs, and changing the
number clears that (it/utopia-crm-ladiaria#3).
"""
from datetime import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.choices import PhoneValidationSource
from core.models import Contact

from tests.factory import create_contact

VALIDATED_AT = datetime(2026, 11, 17, 10, 30)


class PhoneValidationTests(TestCase):
    def setUp(self):
        contact = create_contact("Phone validation", "29000144")
        Contact.objects.filter(pk=contact.pk).update(
            mobile="+59899123456",
            phone_validated_at=VALIDATED_AT,
            phone_validation_source=PhoneValidationSource.CALL_CENTER,
            mobile_validated_at=VALIDATED_AT,
            mobile_validation_source=PhoneValidationSource.WEB,
        )
        self.contact = Contact.objects.get(pk=contact.pk)

    def reloaded(self):
        return Contact.objects.get(pk=self.contact.pk)

    def test_changing_the_number_clears_its_validation(self):
        self.contact.phone = "29001234"
        self.contact.save()
        contact = self.reloaded()
        self.assertIsNone(contact.phone_validated_at)
        self.assertEqual(contact.phone_validation_source, "")
        # the mobile did not change, and keeps its own
        self.assertEqual(contact.mobile_validated_at, VALIDATED_AT)
        self.assertEqual(contact.mobile_validation_source, PhoneValidationSource.WEB)

    def test_emptying_the_number_clears_its_validation(self):
        self.contact.mobile = ""
        self.contact.save()
        self.assertIsNone(self.reloaded().mobile_validated_at)

    def test_the_same_number_written_otherwise_keeps_it(self):
        self.contact.mobile = "099 123 456"
        self.contact.save()
        self.assertEqual(self.reloaded().mobile_validated_at, VALIDATED_AT)

    def test_saving_other_fields_keeps_it(self):
        self.contact.name = "Phone validation renamed"
        self.contact.save()
        self.assertEqual(self.reloaded().phone_validated_at, VALIDATED_AT)

    def test_a_new_number_validated_in_the_same_save_keeps_the_new_validation(self):
        now = datetime(2026, 11, 18, 9, 0)
        self.contact.phone = "29001234"
        self.contact.phone_validated_at = now
        self.contact.phone_validation_source = PhoneValidationSource.INCOMING_CALL
        self.contact.save()
        contact = self.reloaded()
        self.assertEqual(contact.phone_validated_at, now)
        self.assertEqual(contact.phone_validation_source, PhoneValidationSource.INCOMING_CALL)

    def test_a_second_change_on_the_same_instance_clears_it(self):
        now = datetime(2026, 11, 18, 9, 0)
        self.contact.phone = "29001234"
        self.contact.phone_validated_at = now
        self.contact.save()
        self.contact.phone = "29005678"
        self.contact.save()
        self.assertIsNone(self.reloaded().phone_validated_at)

    def test_update_fields_with_the_number_clears_it_too(self):
        self.contact.phone = "29001234"
        self.contact.save(update_fields=["phone"])
        contact = self.reloaded()
        self.assertEqual(str(contact.phone), "+59829001234")
        self.assertIsNone(contact.phone_validated_at)
        self.assertEqual(contact.phone_validation_source, "")

    def test_update_fields_without_the_number_keeps_it(self):
        self.contact.phone = "29001234"
        self.contact.save(update_fields=["name"])
        self.assertEqual(self.reloaded().phone_validated_at, VALIDATED_AT)

    def test_a_new_contact_keeps_the_validation_it_is_given(self):
        contact = Contact(
            name="Phone validation new",
            phone="29000145",
            phone_validated_at=VALIDATED_AT,
            phone_validation_source=PhoneValidationSource.WEB,
        )
        contact.save()
        self.assertEqual(Contact.objects.get(pk=contact.pk).phone_validated_at, VALIDATED_AT)


class PhoneValidationBadgeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="phone_validation_badge", password="x")
        contact = create_contact("Phone validation badge", "29000146")
        Contact.objects.filter(pk=contact.pk).update(
            phone_validated_at=VALIDATED_AT, phone_validation_source=PhoneValidationSource.CALL_CENTER
        )
        cls.contact = Contact.objects.get(pk=contact.pk)

    def test_the_contact_detail_shows_the_validated_number(self):
        self.client.force_login(self.user)
        content = self.client.get(reverse("contact_detail", args=[self.contact.pk])).content.decode()
        # once in the overview and once in the information tab: only the phone is validated
        self.assertEqual(content.count("badge badge-success ml-1"), 2)
        self.assertIn("17/11/2026", content)

    def test_the_admin_shows_it_read_only(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("admin:core_contact_change", args=[self.contact.pk]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn('name="phone_validated_at"', content)
        self.assertIn('<div class="readonly">Call center</div>', content)
