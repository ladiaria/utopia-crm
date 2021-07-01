# coding=utf-8
from datetime import date

from django.test import TestCase

from invoicing.views import bill_subscription

from tests.factory import create_contact, create_subscription


class TestInvoicing(TestCase):

    def test_1subscription_can_be_billed(self):
        contact = create_contact('cliente1', 21312)
        subscription = create_subscription(contact)
        self.assertTrue(subscription.active)
        self.assertFalse(contact.is_debtor())
        invoice = bill_subscription(subscription.id, date.today(), 10)
