# coding=utf-8

from django.conf import settings
from django.test import TestCase
from tests.factory import create_contact, create_subscription, create_product, create_address


class TestContact(TestCase):

    def test1_contact_is_active_and_is_not_debtor(self):
        contact = create_contact('cliente1', "21312")
        subscription = create_subscription(contact)
        self.assertTrue(subscription.active)
        self.assertFalse(contact.is_debtor())

    def test2_no_email_is_automatically_managed(self):
        """
        Test that no_email field is automatically set based on email value.
        As of the current implementation (see models.py line 554), no_email is
        automatically set to True when email is None, and False otherwise.
        This replaces the old manual validation that raised ValidationError.
        """
        contact = create_contact('cliente1', "21312")

        # Set email to a value - no_email should automatically become False
        contact.email = 'cliente1@ladiaria.com.uy'
        contact.save()  # TODO: check why we now we have to delete the user in CMS (not required some time ago)
        contact.refresh_from_db()
        self.assertFalse(contact.no_email, "no_email should be False when email is set")

        # Set email to None - no_email should automatically become True
        contact.email = None
        contact.save()
        contact.refresh_from_db()
        self.assertTrue(contact.no_email, "no_email should be True when email is None")

    def test3_cliente_activo_debe_tener_ejemplares(self):
        # TODO: write this test
        pass

    def test4_metodos_simples(self):
        contact = create_contact('cliente11', "21312")
        first_act = contact.get_first_active_subscription()
        self.assertFalse(first_act)
        subscription = create_subscription(contact)
        self.assertTrue(subscription.active)
        has_active_sub = contact.has_active_subscription(True)
        self.assertEqual(has_active_sub, 1)
        first_act = contact.get_first_active_subscription()
        self.assertTrue(first_act)

        open_issues = contact.has_no_open_issues()
        self.assertEqual(open_issues, True)

        prod_count = subscription.get_product_count()
        self.assertEqual(prod_count, 0)

        product1 = create_product('newspaper', 500)
        address = create_address('Araucho 1390', contact, address_type='physical')

        subscription.add_product(product1, address)
        status = 'A'
        contact.add_product_history(subscription, product1, status)

        # creation name keep
        billing_name = subscription.get_billing_name()
        self.assertEqual(billing_name, 'cliente11')

        # creation phone keep
        billing_phone = subscription.get_billing_phone()
        self.assertEqual(billing_phone, '21312')

        freq0 = subscription.get_frequency_discount()
        self.assertEqual(freq0, 0)

        subscription.frequency = 3
        freq3 = subscription.get_frequency_discount()
        self.assertEqual(freq3, getattr(settings, "DISCOUNT_3_MONTHS", 0))

        subscription.frequency = 6
        freq6 = subscription.get_frequency_discount()
        self.assertEqual(freq6, getattr(settings, "DISCOUNT_6_MONTHS", 0))

        subscription.frequency = 12
        freq12 = subscription.get_frequency_discount()
        self.assertEqual(freq12, getattr(settings, "DISCOUNT_12_MONTHS", 0))

        first_day = subscription.get_first_day_of_the_week()
        self.assertEqual(first_day, 6)

        product2 = create_product('newspaper3', 1500)
        product2.weekday = 1
        subscription.add_product(product2, address)

        self.assertEqual(subscription.product_summary(), {product1.id: '1', product2.id: '1'})
