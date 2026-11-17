# coding=utf-8
"""
The seller console validates a phone or mobile number, or deletes it as wrong, with a button per number; and a result
that means the seller spoke with the contact validates the number when it is the only one (it/utopia-crm-ladiaria#3).
"""
from datetime import datetime

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.choices import CAMPAIGN_STATUS, PhoneValidationSource
from core.models import Campaign, Contact, ContactCampaignStatus
from support.models import Seller, SellerConsoleAction

from tests.factory import create_contact

HTMX = {"HTTP_HX_REQUEST": "true"}


class ContactPhoneMethodsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="phone_methods")
        contact = create_contact("Phone methods", "29000150")
        Contact.objects.filter(pk=contact.pk).update(mobile="+59899123450", phone_extension="12")
        self.contact = Contact.objects.get(pk=contact.pk)

    def test_mark_phone_validated(self):
        self.contact.mark_phone_validated("mobile", PhoneValidationSource.CALL_CENTER, user=self.user)
        contact = Contact.objects.get(pk=self.contact.pk)
        self.assertIsNotNone(contact.mobile_validated_at)
        self.assertEqual(contact.mobile_validation_source, PhoneValidationSource.CALL_CENTER)
        record = contact.history.latest()
        self.assertEqual(record.history_user, self.user)
        self.assertIn("Call center", record.history_change_reason)

    def test_mark_phone_validated_needs_a_number(self):
        Contact.objects.filter(pk=self.contact.pk).update(mobile="")
        with self.assertRaises(ValueError):
            Contact.objects.get(pk=self.contact.pk).mark_phone_validated("mobile", PhoneValidationSource.WEB)
        with self.assertRaises(ValueError):
            self.contact.mark_phone_validated("work_phone", PhoneValidationSource.WEB)

    def test_remove_phone_takes_its_extension_and_validation(self):
        Contact.objects.filter(pk=self.contact.pk).update(phone_validated_at=datetime(2026, 11, 17))
        contact = Contact.objects.get(pk=self.contact.pk)
        contact.remove_phone("phone", user=self.user, reason="Wrong number")
        contact = Contact.objects.get(pk=self.contact.pk)
        self.assertEqual(str(contact.phone), "")
        self.assertEqual(contact.phone_extension, "")
        self.assertIsNone(contact.phone_validated_at)
        self.assertEqual(str(contact.mobile), "+59899123450")
        # the history keeps the deleted number, its author and the reason
        record = contact.history.latest()
        self.assertEqual(record.history_change_reason, "Wrong number")
        self.assertEqual(record.history_user, self.user)
        self.assertEqual(str(record.prev_record.phone), "+59829000150")


class SellerConsolePhoneButtonsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="phone_buttons", password="x")

    def setUp(self):
        contact = create_contact("Phone buttons", "29000151")
        Contact.objects.filter(pk=contact.pk).update(mobile="+59899123451")
        self.contact = Contact.objects.get(pk=contact.pk)
        self.client.force_login(self.user)

    def post(self, field, action, number, **headers):
        url = reverse("seller_console_phone", args=[self.contact.pk, field, action])
        return self.client.post(url, {"number": number}, **(headers or HTMX))

    def test_validate(self):
        response = self.post("phone", "validate", "+59829000151")
        self.assertEqual(response.status_code, 200)
        contact = Contact.objects.get(pk=self.contact.pk)
        self.assertEqual(contact.phone_validation_source, PhoneValidationSource.CALL_CENTER)
        self.assertEqual(contact.history.latest().history_user, self.user)
        content = response.content.decode()
        self.assertIn("badge badge-success", content)
        # validated: only the delete button is left
        self.assertNotIn("/phone/validate/", content)
        self.assertIn("/phone/remove/", content)

    def test_remove(self):
        response = self.post("mobile", "remove", "+59899123451")
        self.assertEqual(response.status_code, 200)
        contact = Contact.objects.get(pk=self.contact.pk)
        self.assertEqual(str(contact.mobile), "")
        self.assertEqual(str(contact.phone), "+59829000151")
        content = response.content.decode()
        self.assertIn("<del>", content)
        self.assertIn("Deleted as a wrong number", content)
        self.assertNotIn("/mobile/remove/", content)

    def test_a_number_that_changed_meanwhile_is_not_touched(self):
        response = self.post("phone", "remove", "+59829009999")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(Contact.objects.get(pk=self.contact.pk).phone), "+59829000151")
        self.assertNotIn("<del>", response.content.decode())

    def test_only_htmx_posts_on_phone_and_mobile(self):
        self.assertEqual(self.post("phone", "remove", "+59829000151", HTTP_X_OTHER="1").status_code, 404)
        self.assertEqual(self.post("work_phone", "remove", "").status_code, 404)
        self.assertEqual(self.post("phone", "erase", "+59829000151").status_code, 404)
        url = reverse("seller_console_phone", args=[self.contact.pk, "phone", "remove"])
        self.assertEqual(self.client.get(url, **HTMX).status_code, 405)
        self.assertEqual(str(Contact.objects.get(pk=self.contact.pk).phone), "+59829000151")

    def test_a_foreign_number_reads_whole_in_the_confirmation(self):
        Contact.objects.filter(pk=self.contact.pk).update(mobile="+34612345678")
        response = self.post("mobile", "validate", "+34612345678")
        self.assertIn('hx-confirm="Delete +34 612 34 56 78 from the contact', response.content.decode())

    def test_staff_only(self):
        self.client.force_login(User.objects.create_user(username="phone_buttons_not_staff"))
        self.post("phone", "remove", "+59829000151")
        self.assertEqual(str(Contact.objects.get(pk=self.contact.pk).phone), "+59829000151")


@override_settings(SELLER_CONSOLE_PHONE_NOT_VALIDATED_REASONS=(12, 14))
class SellerConsoleValidatesTheOnlyPhoneTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="phone_console", password="x")
        self.seller = Seller.objects.create(name="Vendedor", user=self.user, internal=True)
        self.client.force_login(self.user)
        self.campaign = Campaign.objects.create(name="Campaña teléfonos", active=True, priority=3)
        self.contact = create_contact("Phone console", "29000152")
        self.ccs = ContactCampaignStatus.objects.create(
            contact=self.contact, campaign=self.campaign, status=1, seller=self.seller
        )
        SellerConsoleAction.objects.create(
            slug="not-interested",
            name="No interesado",
            action_type=SellerConsoleAction.ACTION_TYPES.DECLINED,
            campaign_status=CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
            campaign_resolution="NI",
        )
        SellerConsoleAction.objects.create(
            slug="not-found",
            name="No encontrado",
            action_type=SellerConsoleAction.ACTION_TYPES.NOT_FOUND,
            campaign_status=CAMPAIGN_STATUS.CALLED_COULD_NOT_CONTACT,
            campaign_resolution="NF",
        )

    def post_result(self, result, reason=""):
        self.client.post(
            reverse("seller_console", args=["new", self.campaign.id]),
            {
                "result": result,
                "category": "new",
                "instance_id": self.ccs.id,
                "seller_id": self.seller.id,
                "offset": 1,
                "notes": "",
                "campaign_resolution_reason": reason,
            },
        )
        return Contact.objects.get(pk=self.contact.pk)

    def test_spoke_with_the_contact_validates_the_only_number(self):
        contact = self.post_result("not-interested", reason="7")
        self.assertEqual(contact.phone_validation_source, PhoneValidationSource.CALL_CENTER)
        self.assertEqual(contact.history.latest().history_user, self.user)

    def test_not_found_validates_nothing(self):
        self.assertIsNone(self.post_result("not-found").phone_validated_at)

    def test_a_wrong_number_reason_validates_nothing(self):
        self.assertIsNone(self.post_result("not-interested", reason="12").phone_validated_at)

    def test_with_two_numbers_the_seller_chooses(self):
        Contact.objects.filter(pk=self.contact.pk).update(mobile="+59899123452")
        contact = self.post_result("not-interested", reason="7")
        self.assertIsNone(contact.phone_validated_at)
        self.assertIsNone(contact.mobile_validated_at)

    def test_a_work_phone_counts_as_another_number(self):
        Contact.objects.filter(pk=self.contact.pk).update(work_phone="0800 1234")
        self.assertIsNone(self.post_result("not-interested", reason="7").phone_validated_at)

    def test_the_console_shows_the_buttons(self):
        response = self.client.get(reverse("seller_console", args=["new", self.campaign.id]))
        content = response.content.decode()
        self.assertIn(reverse("seller_console_phone", args=[self.contact.pk, "phone", "validate"]), content)
        self.assertIn(reverse("seller_console_phone", args=[self.contact.pk, "phone", "remove"]), content)
