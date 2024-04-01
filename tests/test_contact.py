# coding=utf-8
from datetime import timedelta
import json

from django.conf import settings
from django.test import TestCase
from django.utils.translation import gettext_lazy as _

from tests.factory import (
    create_contact, create_simple_invoice, create_product, create_campaign, create_address, create_subtype
)

from util import space_join
from core.models import Contact, Product, Campaign, ContactCampaignStatus, update_customer
from invoicing.models import Invoice


class TestCoreContact(TestCase):

    def setUp(self):
        pass

    def test1_create_contact(self):
        """
        Gets the contact and checks that its name is the one we set in setUp
        """
        create_contact(name='Contact 1', phone='12345678')
        contact = Contact.objects.all().last()
        self.assertTrue(isinstance(contact, Contact))  # Check if it is a contact
        self.assertEqual(contact.name, 'Contact 1')  # Check if its name is Contact 1
        # a way to make this test fail by settings (may be useful to know if you get noticed when tests are failing)
        self.assertFalse(getattr(settings, "TESTS_FIRST_TEST_SHOULD_FAIL", False))

    def test2_rename_contact_name(self):
        """
        Simple operation to see if that contact allows to change names.
        """
        contact = create_contact(name='Contact 2', phone='12345567')
        contact.name = 'Renamed Contact'
        contact.save()

        # Check if the object is a contact
        self.assertTrue(isinstance(contact, Contact))

        # Check if the contact's name has actually changed
        self.assertEqual(contact.name, 'Renamed Contact')

    def test3_contact_str_method(self):
        """
        Check the unicode method. This test uses a contact that will only be used in this one.
        """
        contact = create_contact(name='Contact 3', phone='12345567')
        self.assertTrue(isinstance(contact, Contact))
        self.assertEqual(contact.name, contact.__str__())

    def test4_contact_debtor_methods(self):
        """
        Checks if the is_debtor method works
        """
        contact = create_contact(name='Contact 4', phone='12312321')
        product = create_product('newspaper', 500)
        invoice = create_simple_invoice(contact, 'R', product)
        invoice.creation_date = invoice.creation_date - timedelta(30)
        invoice.expiration_date = invoice.expiration_date - timedelta(30)  # This will be a forced expired invoice
        invoice.save()

        # Just to check if every objects is correctly created
        self.assertTrue(isinstance(contact, Contact))
        self.assertTrue(isinstance(product, Product))
        self.assertTrue(isinstance(invoice, Invoice))

        # First we check if the contact is debtor
        self.assertTrue(contact.is_debtor())

        # That function depends on this one.
        self.assertEqual(contact.expired_invoices_count(), 1)

        # Get expired invoices should return a queryset with the one that we created before
        expired_invoices = contact.get_expired_invoices()
        self.assertIn(invoice, expired_invoices)

        # The debt should be exactly the amount of the invoice (for now it is the amount of the product's price)
        self.assertEqual(contact.get_debt(), product.price)

    def test5_contact_campaign_methods(self):
        """
        Creates a contact and checks if it has been added to the campaign.
        """
        contact = create_contact(name='Contact 5', phone='12412455')
        campaign = create_campaign(name='Campaign')

        # Check if they were created correctly
        self.assertTrue(isinstance(contact, Contact))
        self.assertTrue(isinstance(campaign, Campaign))

        response = contact.add_to_campaign(campaign.id)

        # This command returns a text, we have to see if the text has been correctly returned
        self.assertEqual(
            response, _("Contact %(name)s (ID: %(id)s) added to campaign") % {'name': contact.name, 'id': contact.id}
        )

        # We have to check if a ContactCampaignStatus with campaign.id and contact.id exists
        self.assertTrue(ContactCampaignStatus.objects.filter(contact=contact, campaign=campaign).exists())

        # Then we have to see that it's only one. This would fail otherwise. Then we have to see that the status is
        # the default one
        ccs = ContactCampaignStatus.objects.get(contact=contact, campaign=campaign)
        self.assertEqual(ccs.status, 1)  # Default is always 1, which means not contacted yet

        # We need to try to add the contact again, that should raise a normal exception
        with self.assertRaises(Exception):
            contact.add_to_campaign(campaign.id)

    def test6_others(self):
        subtype = create_subtype(name='Subtype 1')
        count = subtype.get_contact_count()
        self.assertEqual(count, 0)

        product = create_product('news', 500)
        # test for default
        self.assertEqual(product.get_type(), _("Subscription"))
        product.type = 'N'
        self.assertEqual(product.get_type(), _("Newsletter"))
        self.assertEqual(product.get_weekday(), 'N/A')

        basic_print = str(product)
        self.assertEqual(basic_print, 'news, newsletter')

        # very simple, no expired
        contact = create_contact(name='Contact 6', phone='12412455')
        subs_expired = contact.get_subscriptions_with_expired_invoices()
        assert not subs_expired

        gender = contact.get_gender()
        self.assertEqual(gender, 'N/A')

        newsletters = contact.get_newsletters()
        assert not newsletters

        # TODO: complete this test (if it makes sense to test product history here) (final lines were commented)
        # status = 'A'
        # contact.add_product_history(product, status)

    def test7_others_classes(self):
        contact = create_contact(name='Contact 9', phone='12412455')
        address = create_address('Araucho 1390', contact, address_type='physical')
        self.assertEqual(
            str(address),
            space_join(
                'Araucho 1390',
                space_join(getattr(settings, 'DEFAULT_CITY', None), getattr(settings, 'DEFAULT_STATE', None)),
            )
        )

        address_type = address.get_type()
        self.assertEqual(address_type, _('Physical'))

    def test8_basic_print(self):
        from core.models import Institution
        institution = Institution.objects.create(name='inst')
        basic_print = str(institution)
        self.assertEqual(basic_print, 'inst')

    def test9_update_contact(self):
        """
        - Email change will not raise any error.
        - Adding or removing a newsletter whose pub_id is not defined in settings will not raise any error.
        """
        email = "contact@fakemail.com.uy"
        contact = create_contact("Digital", 29000808, email)
        # secure id check to prevent failures on "running" CMS databases
        if contact.id > 999:  # TODO: a new local setting and only make this check if the setting is set
            self.fail("contact_id secure limit reached, please drop your test db and try again")
        contact.email = "newemail@fakemail.com.uy"
        contact.save()
        # change again, if not, next run of this test will fail (TODO: confirm this assumption)
        contact.email = email
        contact.save()
        non_existing_key = max(settings.WEB_UPDATE_NEWSLETTER_MAP.keys() or [0]) + 1
        try:
            update_customer(contact, None, 'newsletters', json.dumps([non_existing_key]))
        except Exception:
            self.fail('update_customer call raised Exception')
        try:
            update_customer(contact, None, 'newsletters_remove', json.dumps([non_existing_key]))
        except Exception:
            self.fail('update_customer call raised Exception')
