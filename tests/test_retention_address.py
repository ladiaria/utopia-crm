"""
The new paper products of the retention form are created with the address chosen for them on the same form.

The view is called directly: a customization package may override the ``add_retention_discount`` URL.
Products are built by hand because this repository ships no product fixtures.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase, override_settings

from core.models import Product, Subscription, SubscriptionProduct
from support.views.subscriptions import add_retention_discount
from tests.factories.core_factories import AddressFactory, ContactFactory, SubscriptionFactory


@override_settings(WEB_UPDATE_USER_ENABLED=False)
class TestRetentionNewProductAddress(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("retention-agent", password="x", is_staff=True)
        cls.contact = ContactFactory()
        cls.address = AddressFactory(contact=cls.contact)
        cls.current = Product.objects.create(name="Current paper", type="S", price=100, offerable=True)
        cls.paper = Product.objects.create(name="New paper", type="S", price=200, offerable=True)
        cls.online = Product.objects.create(name="Online edition", type="S", price=150, offerable=True, digital=True)

    def setUp(self):
        self.subscription = SubscriptionFactory(
            contact=self.contact, start_date=date(2025, 1, 1), end_date=None, active=True, payment_type="O"
        )
        self.subscription.add_product(self.current, self.address)

    def _post(self, data):
        data = {
            "start_date": (date.today() + timedelta(days=1)).strftime("%Y-%m-%d"),
            "unsubscription_channel": 4,
            **data,
        }
        request = RequestFactory().post("/", data)
        request.user = self.user
        SessionMiddleware(lambda r: None).process_request(request)
        request._messages = FallbackStorage(request)
        return add_retention_discount(request, self.subscription.id)

    def test_paper_product_without_address_creates_nothing(self):
        response = self._post({f"activateproduct-{self.paper.id}": "on"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Subscription.objects.filter(updated_from=self.subscription).exists())

    def test_paper_product_gets_the_chosen_address(self):
        response = self._post({f"activateproduct-{self.paper.id}": "on", f"address-{self.paper.id}": self.address.id})
        self.assertEqual(response.status_code, 302)
        new_subscription = Subscription.objects.get(updated_from=self.subscription)
        sp = SubscriptionProduct.objects.get(subscription=new_subscription, product=self.paper)
        self.assertEqual(sp.address, self.address)

    def test_digital_product_needs_no_address(self):
        response = self._post({f"activateproduct-{self.online.id}": "on"})
        self.assertEqual(response.status_code, 302)
        new_subscription = Subscription.objects.get(updated_from=self.subscription)
        self.assertIsNone(SubscriptionProduct.objects.get(subscription=new_subscription, product=self.online).address)
