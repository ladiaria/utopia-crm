from datetime import date, timedelta

from django.core.management import call_command
from django.test import TestCase

from tests.factories.core_factories import ContactFactory, SubscriptionFactory, AddressFactory, ProductFactory
from tests.factories.logistics_factories import RouteFactory


class TestAutomaticActivationDisabling(TestCase):

    def setUp(self):
        self.product = ProductFactory()
        self.route = RouteFactory()

    def test1_future_subscription_should_not_be_activated_if_start_date_is_two_days_in_the_future(self):
        subscription = SubscriptionFactory(
            contact=ContactFactory(name='Contact 1', phone='12345678'),
            start_date=date.today() + timedelta(2),
            active=False,
            status="OK",
        )
        address = AddressFactory(contact=subscription.contact)
        subscription.add_product(product=self.product, address=address, route=self.route)

        call_command("activate_subscriptions_by_start_date")

        subscription.refresh_from_db()
        self.assertFalse(subscription.active)

    def test2_future_subscription_should_be_activated_if_start_date_is_tomorrow(self):
        subscription = SubscriptionFactory(
            contact=ContactFactory(name='Contact 2', phone='12345678'),
            start_date=date.today() + timedelta(1),
            active=False,
            status="OK",
        )
        address = AddressFactory(contact=subscription.contact)
        subscription.add_product(product=self.product, address=address, route=self.route)

        call_command("activate_subscriptions_by_start_date")

        subscription.refresh_from_db()
        self.assertTrue(subscription.active)

    def test3_future_subscription_should_be_activated_if_start_date_is_today(self):
        subscription = SubscriptionFactory(
            contact=ContactFactory(name='Contact 3', phone='12345678'),
            start_date=date.today(),
            active=False,
            status="OK",
        )
        address = AddressFactory(contact=subscription.contact)
        subscription.add_product(product=self.product, address=address, route=self.route)

        call_command("activate_subscriptions_by_start_date")

        subscription.refresh_from_db()
        self.assertTrue(subscription.active)

    def test4_subscription_should_be_ended_if_end_date_is_today(self):
        subscription = SubscriptionFactory(
            contact=ContactFactory(name='Contact 4', phone='12345678'),
            end_date=date.today(),
            active=True,
            status="OK",
        )
        address = AddressFactory(contact=subscription.contact)
        subscription.add_product(product=self.product, address=address, route=self.route)

        call_command("disable_subscriptions_by_end_date")

        subscription.refresh_from_db()
        self.assertFalse(subscription.active)

    def test5_subscription_should_not_be_ended_if_end_date_is_greater_than_today(self):
        subscription = SubscriptionFactory(
            contact=ContactFactory(name='Contact 5', phone='12345678'),
            end_date=date.today() + timedelta(1),
            active=True,
            status="OK",
        )
        address = AddressFactory(contact=subscription.contact)
        subscription.add_product(product=self.product, address=address, route=self.route)

        call_command("disable_subscriptions_by_end_date")

        subscription.refresh_from_db()
        self.assertTrue(subscription.active)
