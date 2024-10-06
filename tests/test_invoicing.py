# coding=utf-8
from datetime import date

from django.test import TestCase

from core.models import Product
from logistics.models import Route
from invoicing.models import Invoice
from invoicing.views import bill_subscription

from tests.factory import create_contact, create_subscription, create_product, create_address, create_route


class TestInvoicing(TestCase):

    def setUp(self):
        create_route(number=1, name="Route 1")
        create_product(name='Newspaper', price=500, type="S", billing_priority=1)

    def test_1subscription_can_be_billed(self):
        contact = create_contact('cliente1', "29000808")
        subscription = create_subscription(contact)
        address = create_address('Treinta y Tres 1479', contact, address_type='physical')

        product = Product.objects.get(slug="newspaper")
        route_1 = Route.objects.get(number=1)

        subscription.add_product(
            product=product,
            address=address,
            route=route_1,  # if the setting to require a route is activated, this is mandatory
        )

        self.assertTrue(subscription.active)
        self.assertFalse(contact.is_debtor())
        invoice = bill_subscription(subscription.id, date.today(), 10)
        self.assertTrue(isinstance(invoice, Invoice))
        self.assertEqual(invoice.amount, product.price)
