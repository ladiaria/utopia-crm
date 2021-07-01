# coding=utf-8
# TODO: All commented code should be explained or removed

from django.test import TestCase
# from django.utils.translation import ugettext_lazy as _

# from django.forms import ValidationError
# from django.test import TestCase

from core.utils import dnames

from tests.factory import (
    create_contact, create_subscription, create_product, create_address
    # , create_simple_invoice, create_campaign,
)


class TestContact(TestCase):

    def test_1cliente_nuevo_es_activo_y_no_es_moroso(self):
        contact = create_contact('cliente1', 21312)
        subscription = create_subscription(contact)
        self.assertTrue(subscription.active)
        self.assertFalse(contact.is_debtor())

    def test_2cliente_activo_debe_tener_algun_dia_marcado(self):
        contact = create_contact('cliente1', 21312)
        subscription = create_subscription(contact)

        for day in dnames:
            setattr(subscription, day, False)
        # self.assertRaises(AssertionError, subscription.save)
        subscription.active = False
        subscription.save()
        subscription.active = True
        # self.assertRaises(AssertionError, subscription.save)

    def test_3cliente_que_no_tiene_email_debe_tener_email_en_blanco(self):
        contact = create_contact('cliente1', 21312)
        contact.no_email, contact.email = True, 'cliente1@ladiaria.com.uy'
        # self.assertRaises(ValidationError, contact.save)
        contact.email = None
        contact.save()

    # hacer devuelta
    def test_4cliente_activo_debe_tener_ejemplares(self):

        contact = create_contact(u'cliente2asd', 21312)
        contact.save()
        # p = create_plan('plan2', 200)
        # p.type = 'N'
        # p.save()

        # subscription = create_subscription(contact, p)

        # route = create_route(1, 'ruta1')

        # subscription.route_id, subscription.active, subscription.payment_type = 1, True, 'R'
        # subscription.copies = 0
        # self.assertRaises(ValidationError, subscription.save)
        # subscription.copies = 1
        # subscription.save()

    def test_5_metodos_simples(self):
        # SUBSCRIPTION_PAYMENT_METHODS = (
        # ('O', 'Other'),
        # ('D', 'Debit'),
        # ('S', 'Cash payment'),
        contact = create_contact('cliente11', 21312)
        first_act = contact.get_first_active_subscription()
        self.assertFalse(first_act)  # None
        subscription = create_subscription(contact)
        self.assertTrue(subscription.active)
        has_active_sub = contact.has_active_subscription(True)
        self.assertEqual(has_active_sub, 1)
        first_act = contact.get_first_active_subscription()
        self.assertTrue(first_act)  # None

        open_issues = contact.has_no_open_issues()
        self.assertEqual(open_issues, True)

        prod_count = subscription.get_product_count()
        self.assertEqual(prod_count, 0)

        product = create_product('newspaper', 500)
        address = create_address('Araucho 1390', contact, address_type='physical')

        subscription.add_product(product, address)
        status = 'A'
        contact.add_product_history(subscription, product, status)

        # default name
        billing_name = subscription.get_billing_name()
        self.assertEqual(billing_name, 'cliente11')

        # default phone
        billing_phone = subscription.get_billing_phone()
        self.assertEqual(billing_phone, '21312')

        freq0 = subscription.get_frequency_discount()
        self.assertEqual(freq0, 0)

        # check that definitions exists
        subscription.frequency = 3  # white box test
        freq3 = subscription.get_frequency_discount()
        assert freq3

        subscription.frequency = 6  # white box test
        freq6 = subscription.get_frequency_discount()
        assert freq6

        subscription.frequency = 12  # white box test
        freq12 = subscription.get_frequency_discount()
        assert freq12

        first_day = subscription.get_first_day_of_the_week()
        # default value is 6 :: white box test
        self.assertEqual(first_day, 6)

        product2 = create_product('newspaper3', 1500)
        product2.weekday = 1
        subscription.add_product(product2, address)

        self.assertEqual(subscription.product_summary(), {1: '1', 2: '1'})
