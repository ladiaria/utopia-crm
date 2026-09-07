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

    def test_a_free_subscription_reads_as_na_and_pays_no_commission(self):
        # Free subscriptions are recorded as FULL sales, so without the free check they would report
        # the subscription's payment method and compute a commission on a sale worth nothing.
        subscription = create_subscription(self.contact, subscription_type="F", payment_type="S")
        sales_record = SalesRecord.objects.create(subscription=subscription, price=0)

        self.assertTrue(sales_record.is_free_subscription())
        self.assertEqual(sales_record.get_payment_type(), "N/A")
        self.assertEqual(sales_record.calculate_total_commission(), 0)

        # Forcing the calculation the way the validation view does must not create a commission.
        sales_record.set_commissions(force=True)
        sales_record.refresh_from_db()
        self.assertEqual(sales_record.total_commission_value, 0)

    def test_the_validation_form_will_not_commission_a_free_subscription(self):
        # Locked, not merely hidden: a hand-made POST asking for the commission must not get one.
        seller = Seller.objects.create(name="Internal seller", internal=True)
        subscription = create_subscription(self.contact, subscription_type="F", payment_type="S")
        sales_record = SalesRecord.objects.create(subscription=subscription, price=0, seller=seller)

        response = self.client.post(
            reverse("validate_sale", args=[sales_record.pk]),
            {"seller": seller.pk, "can_be_commissioned": "on", "override_commission_value": 5000},
        )
        self.assertEqual(response.status_code, 302)

        sales_record.refresh_from_db()
        subscription.refresh_from_db()
        self.assertTrue(subscription.validated)  # the sale is validated all the same
        self.assertFalse(sales_record.can_be_commissioned)
        self.assertEqual(sales_record.total_commission_value, 0)

    def test_a_paid_subscription_keeps_reporting_its_payment_method(self):
        subscription = create_subscription(self.contact, subscription_type="N", payment_type="S")
        sales_record = SalesRecord.objects.create(subscription=subscription, price=100)

        self.assertFalse(sales_record.is_free_subscription())
        self.assertNotEqual(sales_record.get_payment_type(), "N/A")
