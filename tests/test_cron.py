# coding=utf-8
from datetime import date, timedelta

from django.test import TestCase
from django.core.management import call_command

from core.models import Subscription
from tests.factory import (
    create_contact, create_subscription, create_product, create_address
)


class TestCron(TestCase):

    def setUp(self):
        contact = create_contact(name="la diaria", phone="29000808")
        subscription = create_subscription(contact)
        subscription.active = False
        subscription.start_date = date.today()
        subscription.status = "OK"
        subscription.save()
        address = create_address('Fake Street 123', contact)
        product1 = create_product(name="newspaper", price=350)
        subscription.add_product(product1, address)

    def test1_subscription_with_start_date_today_or_yesterday_should_be_activated(self):
        # We check it exists and it's inactive
        subscription = Subscription.objects.first()
        self.assertTrue(isinstance(subscription, Subscription))
        self.assertFalse(subscription.active)
        call_command("cron")
        # Then we load the subscription from the database again
        subscription = Subscription.objects.first()
        self.assertTrue(subscription.active)
        # We'll disable the subscription again
        subscription.active = False
        # The activation date will be yesterday
        subscription.start_date = date.today() - timedelta(1)
        subscription.save()
        call_command("cron")
        subscription = Subscription.objects.first()
        self.assertTrue(subscription.active)

    def test2_subscription_with_start_date_far_in_the_past_or_in_the_future_should_not_be_activated(self):
        subscription = Subscription.objects.first()
        self.assertTrue(isinstance(subscription, Subscription))
        self.assertFalse(subscription.active)
        subscription.start_date = date.today() - timedelta(3)
        subscription.save()
        call_command("cron")
        # Then we load the subscription from the database again
        subscription = Subscription.objects.first()
        self.assertFalse(subscription.active)
        subscription.start_date = date.today() + timedelta(1)
        subscription.save()
        call_command("cron")
        # Then we load the subscription from the database again
        subscription = Subscription.objects.first()
        self.assertFalse(subscription.active)

    def test3_subscription_with_end_date_should_not_be_activated(self):
        subscription = Subscription.objects.first()
        self.assertTrue(isinstance(subscription, Subscription))
        self.assertFalse(subscription.active)
        subscription.end_date = date.today()
        subscription.save()
        call_command("cron")
        # Then we load the subscription from the database again
        subscription = Subscription.objects.first()
        self.assertFalse(subscription.active)

    def test4_subscription_with_end_date_yesterday_should_be_disabled_today(self):
        subscription = Subscription.objects.first()
        self.assertTrue(isinstance(subscription, Subscription))
        self.assertFalse(subscription.active)
        subscription.active = True
        subscription.save()
        self.assertTrue(subscription.active)
        subscription.start_date = date.today() - timedelta(30)
        subscription.end_date = date.today() - timedelta(1)
        subscription.save()
        call_command("cron")
        # Then we load the subscription from the database again
        subscription = Subscription.objects.first()
        self.assertFalse(subscription.active)
