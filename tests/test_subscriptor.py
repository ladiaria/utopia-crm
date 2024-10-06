# coding=utf-8

from django.conf import settings
from django.test import TestCase

from django.forms import ValidationError

from tests.factory import create_contact, create_subscription, create_product, create_address


class TestContact(TestCase):

    def test1_contact_is_active_and_is_not_debtor(self):
        contact = create_contact('cliente1', "21312")
        subscription = create_subscription(contact)
        self.assertTrue(subscription.active)
        self.assertFalse(contact.is_debtor())

    def test2_cliente_que_no_tiene_email_debe_tener_email_en_blanco(self):
        contact = create_contact('cliente1', "21312")
        contact.no_email, contact.email = True, 'cliente1@ladiaria.com.uy'
        self.assertRaises(ValidationError, contact.save)
        contact.email = None
        contact.save()

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
