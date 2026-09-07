# coding=utf-8
"""
What happens when a sale is validated, and which subscriptions are born with a sales record.

Two separate things worth not mixing up:

- **The hook.** Validating is the moment the sale becomes real for the rest of the world, and
  ``SUBSCRIPTION_VALIDATED_HOOK`` hangs off it (la diaria uses it to grant website access right
  then). The hook can never undo the validation: it is already saved.
- **The free subscription.** Free or not, somebody inside the CRM creates it, so it gets a sales
  record like any other and lands in the queue managers look at.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from core.models import Address, Product, Subscription
from support.models import SalesRecord, Seller

from tests.factory import create_contact, create_subscription


hook_calls = []


def sample_hook(subscription, user):
    hook_calls.append((subscription, user))
    return "done"


class TestSubscriptionValidatedHook(TestCase):

    def setUp(self):
        hook_calls.clear()
        self.contact = create_contact(name="Hook Test", phone="099111333")
        self.subscription = create_subscription(self.contact)

    def test_does_nothing_without_the_setting(self):
        from core.utils import run_subscription_validated_hook

        self.assertIsNone(run_subscription_validated_hook(self.subscription))

    @override_settings(SUBSCRIPTION_VALIDATED_HOOK="tests.test_subscription_validation.sample_hook")
    def test_calls_the_callable_with_subscription_and_user(self):
        from core.utils import run_subscription_validated_hook

        user = User.objects.create_user(username="validator", password="x")
        result = run_subscription_validated_hook(self.subscription, user)
        self.assertEqual(hook_calls, [(self.subscription, user)])
        self.assertEqual(result, "done")

    @override_settings(SUBSCRIPTION_VALIDATED_HOOK="module.that.does.not.exist")
    def test_a_broken_hook_does_not_raise(self):
        from core.utils import run_subscription_validated_hook

        # The validation is already saved: failing to propagate it is logged and swallowed.
        self.assertIsNone(run_subscription_validated_hook(self.subscription))


class TestFreeSubscriptionSalesRecord(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(username="manager", password="x")
        self.client.login(username="manager", password="x")
        self.contact = create_contact(name="Free Sub", phone="099111444")
        self.address = Address.objects.create(contact=self.contact, address_1="Street 1")
        self.product = Product.objects.create(name="Free product", slug="free-product", type="S", offerable=True)

    def test_a_free_subscription_leaves_a_sales_record_priced_at_zero(self):
        response = self.client.post(
            reverse("create_free_subscription", args=[self.contact.id]),
            {
                "name": self.contact.name,
                "last_name": self.contact.last_name or "",
                "phone": self.contact.phone,
                "mobile": "",
                "email": "",
                "notes": "",
                "start_date": "2026-09-01",
                "end_date": "2026-09-08",
                "free_subscription_requested_by": "PR",
                "check-{}".format(self.product.id): "on",
                "address-{}".format(self.product.id): self.address.id,
                "copies-{}".format(self.product.id): 1,
            },
        )
        self.assertEqual(response.status_code, 302)

        subscription = Subscription.objects.get(contact=self.contact, type="F")
        sales_record = SalesRecord.objects.get(subscription=subscription)
        self.assertEqual(sales_record.price, 0)
        self.assertIn(self.product, sales_record.products.all())
        # Without a seller of its own it falls back to the generic one, not None: that is what the
        # rest of the panel expects.
        self.assertEqual(sales_record.seller, Seller.objects.filter(name="Generic Seller").first())
        # And it waits for validation, like any other sale.
        self.assertFalse(subscription.validated)
