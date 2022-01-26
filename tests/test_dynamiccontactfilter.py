# coding=utf-8
from django.test import TestCase

from tests.factory import (
    create_contact, create_product, create_address, create_subscription, create_dynamiccontactfilter, create_route
)

from core.models import Contact, Product, DynamicContactFilter
from core.choices import DYNAMIC_CONTACT_FILTER_MODES


class TestCoreDynamicContactFilter(TestCase):

    """
    Pre-defined modes are:
    1, 'At least one of the products' - Contact may have any of the products
    2, 'All products' - All products MUST match exactly.
    3, 'Newsletters' - Contact may have any of the newsletters.
    """

    def setUp(self):
        c1 = create_contact('contact 1', '123456', 'contact1@email.com')
        a1 = create_address('Fake Street 123', c1)
        c2 = create_contact('contact 2', '234567', 'contact2@email.com')
        a2 = create_address('Fake Street 234', c2)
        c3 = create_contact('contact 3', '345567', 'contact3@email.com')
        a3 = create_address('Fake Street 345', c3)
        c4 = create_contact('contact 4', '456789', 'contact4@email.com')
        a4 = create_address('Fake Street 456', c4)
        product1 = create_product('newspaper', 500)
        product2 = create_product('digital subscription', 250)
        product3 = create_product('magazine', 300)
        newsletter = create_product('amazing newsletter', 0)
        newsletter.type = 'N'
        newsletter.save()
        create_route(56, "Digital")

        # Then we need to create subscriptions for these people
        s1 = create_subscription(c1)
        s2 = create_subscription(c2)
        s3 = create_subscription(c3)
        s4 = create_subscription(c4)

        # Finally we need to add products to the subscriptions
        s1.add_product(product1, a1)
        s1.add_product(product2, a1)

        s2.add_product(product2, a2)

        s3.add_product(product1, a3)

        s4.add_product(product1, a4)
        s4.add_product(product2, a4)
        s4.add_product(product3, a4)

        # We will also subscribe 2 people to our amazing newsletter
        c1.add_newsletter(newsletter.id)
        c2.add_newsletter(newsletter.id)

    def test1_unicode(self):
        dcf = create_dynamiccontactfilter('Test description')
        self.assertTrue(isinstance(dcf, DynamicContactFilter))
        self.assertEqual(dcf.description, dcf.__unicode__())

    def test2_create_filter_with_one_product_exactly(self):
        # For this test, all products must match so there should be only one match in this pre populated db
        dcf = create_dynamiccontactfilter('Test description', 2)
        dcf.allow_promotions = True
        dcf.allow_polls = True
        dcf.save()
        product1 = Product.objects.get(name='newspaper')
        dcf.products.add(product1)

        # First we check if the dcf has one product
        self.assertEqual(dcf.products.all().count(), 1)

        # Then we check how many emails this one has, it should be one
        self.assertEqual(dcf.get_email_count(), 1)

        c3 = Contact.objects.get(name='contact 3')
        # Since the only applicable contact is contact 3, we will see if their email is in the list
        self.assertIn(c3.email, dcf.get_emails())

        # Then we will see if the contact doesn't want to allow promotions anymore, if it appears on the dcf.
        c3.allow_promotions = False
        c3.save()

        # Contact 3 shouldn't be here anymore
        self.assertEqual(dcf.get_email_count(), 0)

        # This dcf should have one product only
        self.assertEqual(dcf.get_products().count(), 1)

        # Product 1 should show up in get_products
        self.assertIn(product1, dcf.get_products())

        # We're also going to check if the returned mode is correct
        modes = dict(DYNAMIC_CONTACT_FILTER_MODES)
        self.assertEqual(modes.get(dcf.mode), dcf.get_mode())

    def test3_create_filter_with_one_product_inclusively(self):
        # In this test we are going to test mode 1, which should include 3 of our contacts.
        dcf = create_dynamiccontactfilter('Test description', 1)
        dcf.allow_promotions = True
        dcf.allow_polls = True
        dcf.save()

        product2 = Product.objects.get(name='digital subscription')
        dcf.products.add(product2)

        # First we check if the dcf has one product
        self.assertEqual(dcf.products.all().count(), 1)

        # Then we check how many emails this one has, it should be three (contacts 1, 2 and 4)
        self.assertEqual(dcf.get_email_count(), 3)

        # We're going to load the three contacts just to check if their emails are there
        c1 = Contact.objects.get(name='contact 1')
        c2 = Contact.objects.get(name='contact 2')
        c4 = Contact.objects.get(name='contact 4')

        # And then we're going to see if the emails are in this dcf's list
        self.assertIn(c1.email, dcf.get_emails())
        self.assertIn(c2.email, dcf.get_emails())
        self.assertIn(c4.email, dcf.get_emails())

        # Finally we'll remove the allow promotions from one of these contacts, result should be 2
        c1.allow_promotions = False
        c1.save()
        self.assertEqual(dcf.get_email_count(), 2)

        # This dcf should have one product only
        self.assertEqual(dcf.get_products().count(), 1)

        # Product 2 should show up in get_products
        self.assertIn(product2, dcf.get_products())

        # We're also going to check if the returned mode is correct
        modes = dict(DYNAMIC_CONTACT_FILTER_MODES)
        self.assertEqual(modes.get(dcf.mode), dcf.get_mode())

    def test4_filter_with_two_products(self):
        # This one will feature mode 1 again, and will have both products
        dcf = create_dynamiccontactfilter('Test description', 1)
        dcf.allow_promotions = True
        dcf.allow_polls = True
        dcf.save()

        product1 = Product.objects.get(name='newspaper')
        product2 = Product.objects.get(name='digital subscription')

        dcf.products.add(product1, product2)

        # First we check if the dcf has two products
        self.assertEqual(dcf.products.all().count(), 2)

        # Then we are going to check how many emails this one has, it should have four since all the contacts
        # have at least any of these products
        self.assertEqual(dcf.get_email_count(), 4)

    def test5_newsletter_mode(self):
        dcf = create_dynamiccontactfilter('Test description', 3)
        dcf.allow_promotions = True
        dcf.allor_polls = True
        dcf.save()

        newsletter = Product.objects.get(name='amazing newsletter')

        dcf.newsletters.add(newsletter)

        # We're going to check if the returned mode is correct
        modes = dict(DYNAMIC_CONTACT_FILTER_MODES)
        self.assertEqual(modes.get(dcf.mode), dcf.get_mode())

        # Now we're going to see if our newsletter is in the get_products method
        self.assertIn(newsletter, dcf.get_products())

        # Now we only have 2 people subscribed to this newsletter, let's see if we can find them here
        self.assertEqual(dcf.get_email_count(), 2)
