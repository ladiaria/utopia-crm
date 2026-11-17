# coding=utf-8
"""
The seller console validates the contact's phone or mobile when it is the only number and the seller spoke with the
person: a sale, a scheduled call, or a call that ends with contact, unless the reason says who answered was not the
person. The console has no buttons to validate or delete a number (it/utopia-crm-ladiaria#3).
"""
from datetime import datetime

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from core.choices import CAMPAIGN_STATUS, PhoneValidationSource
from core.models import Campaign, Contact, ContactCampaignStatus
from support.models import Seller, SellerConsoleAction
from support.views import SubscriptionCreateView

from tests.factory import create_contact


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

    def test_validate_the_only_phone(self):
        # phone and mobile: nothing says which one answered
        self.assertIsNone(self.contact.validate_the_only_phone(PhoneValidationSource.CALL_CENTER))
        Contact.objects.filter(pk=self.contact.pk).update(phone="")
        contact = Contact.objects.get(pk=self.contact.pk)
        self.assertEqual(contact.validate_the_only_phone(PhoneValidationSource.CALL_CENTER, user=self.user), "mobile")
        self.assertIsNotNone(Contact.objects.get(pk=self.contact.pk).mobile_validated_at)
        # the institutional phone counts as another number
        Contact.objects.filter(pk=self.contact.pk).update(mobile_validated_at=None, work_phone="0800 1234")
        contact = Contact.objects.get(pk=self.contact.pk)
        self.assertIsNone(contact.validate_the_only_phone(PhoneValidationSource.CALL_CENTER))
        self.assertIsNone(Contact.objects.get(pk=self.contact.pk).mobile_validated_at)

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
            slug="schedule",
            name="Agendar",
            action_type=SellerConsoleAction.ACTION_TYPES.SCHEDULED,
            campaign_status=CAMPAIGN_STATUS.CONTACTED,
            campaign_resolution="SC",
        )
        SellerConsoleAction.objects.create(
            slug="not-found",
            name="No encontrado",
            action_type=SellerConsoleAction.ACTION_TYPES.NOT_FOUND,
            campaign_status=CAMPAIGN_STATUS.CALLED_COULD_NOT_CONTACT,
            campaign_resolution="NF",
        )

    def post_result(self, result, reason="", **extra):
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
                **extra,
            },
        )
        return Contact.objects.get(pk=self.contact.pk)

    def test_spoke_with_the_contact_validates_the_only_number(self):
        contact = self.post_result("not-interested", reason="7")
        self.assertEqual(contact.phone_validation_source, PhoneValidationSource.CALL_CENTER)
        self.assertEqual(contact.history.latest().history_user, self.user)

    def test_a_scheduled_call_validates_the_only_number(self):
        contact = self.post_result("schedule", call_date="2026-11-30", call_time="10:00")
        self.assertEqual(contact.phone_validation_source, PhoneValidationSource.CALL_CENTER)

    def test_not_found_validates_nothing(self):
        self.assertIsNone(self.post_result("not-found").phone_validated_at)

    def test_a_reason_that_says_it_was_not_the_person_validates_nothing(self):
        self.assertIsNone(self.post_result("not-interested", reason="12").phone_validated_at)
        self.assertIsNone(self.post_result("not-interested", reason="14").phone_validated_at)

    def test_with_two_numbers_nothing_is_validated(self):
        Contact.objects.filter(pk=self.contact.pk).update(mobile="+59899123452")
        contact = self.post_result("not-interested", reason="7")
        self.assertIsNone(contact.phone_validated_at)
        self.assertIsNone(contact.mobile_validated_at)

    def test_a_work_phone_counts_as_another_number(self):
        Contact.objects.filter(pk=self.contact.pk).update(work_phone="0800 1234")
        self.assertIsNone(self.post_result("not-interested", reason="7").phone_validated_at)

    def test_the_console_has_no_phone_buttons(self):
        response = self.client.get(reverse("seller_console", args=["new", self.campaign.id]))
        content = response.content.decode()
        self.assertIn("29000152", content.replace(" ", ""))
        self.assertNotIn("seller_console_phone", content)
        self.assertNotIn("hx-post", content)

    def sell(self, contact):
        """Registers a direct sale from the console of the contact, as the subscription form does when it is saved."""
        view = SubscriptionCreateView()
        view.request = RequestFactory().post("/")
        view.request.user = self.user
        view.is_new, view.is_activity = str(self.ccs.pk), None
        view.ccs, view.url, view.offset = self.ccs, "/", 1
        view.edit_subscription = True  # no sales record: it needs a whole subscription, and it is not what is tested
        form = type("Form", (), {"cleaned_data": {"register_activity": "Venta"}})()
        view.get_redirect_url_and_sales_record(form, None, contact, self.seller.pk)
        return Contact.objects.get(pk=self.contact.pk)

    def test_a_sale_validates_the_only_number(self):
        contact = self.sell(self.contact)
        self.assertEqual(contact.phone_validation_source, PhoneValidationSource.CALL_CENTER)
        self.assertEqual(contact.history.latest().history_user, self.user)

    def test_a_sale_with_two_numbers_validates_nothing(self):
        Contact.objects.filter(pk=self.contact.pk).update(mobile="+59899123453")
        contact = self.sell(self.contact)
        self.assertIsNone(contact.phone_validated_at)
        self.assertIsNone(contact.mobile_validated_at)
