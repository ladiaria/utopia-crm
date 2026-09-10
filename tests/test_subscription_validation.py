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
from datetime import datetime

from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.test import TestCase
from django.utils import translation
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


class TestValidationIsTraceable(TestCase):
    """
    Who validated a sale and when, and who the customer is, must be readable from the panel.

    Both screens answer the same question from different distances: the list says it in a tooltip
    over the OK, the detail says it in full next to the customer's name.
    """

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="manager", password="x", first_name="Ana", last_name="Gestora"
        )
        self.client.login(username="manager", password="x")
        self.contact = create_contact(name="Trace Test", phone="099111555", email="trace@example.com")
        self.subscription = create_subscription(self.contact)
        self.seller = Seller.objects.create(name="A seller")
        self.sales_record = SalesRecord.objects.create(subscription=self.subscription, price=100, seller=self.seller)

    def test_the_detail_shows_who_the_customer_is(self):
        response = self.client.get(reverse("validate_sale", args=[self.sales_record.pk]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.contact.get_full_name(), content)
        self.assertIn("trace@example.com", content)
        self.assertIn(str(self.contact.id), content)

    def test_a_validated_sale_says_who_validated_it_and_when(self):
        self.subscription.validate(user=self.user)

        detail = self.client.get(reverse("validate_sale", args=[self.sales_record.pk]))
        self.assertEqual(detail.status_code, 200)
        detail_content = detail.content.decode()
        self.assertIn("Ana Gestora", detail_content)
        self.subscription.refresh_from_db()
        expected_moment = self.subscription.validated_date.strftime("%d/%m/%Y %H:%M")
        self.assertIn(expected_moment, detail_content)

        listing = self.client.get(reverse("sales_record_filter"))
        self.assertEqual(listing.status_code, 200)
        listing_content = listing.content.decode()
        self.assertIn("Ana Gestora", listing_content)
        self.assertIn(expected_moment, listing_content)

    def test_the_transaction_time_shows_minutes_and_not_the_month(self):
        # `H:m` is the month, not the minutes: it made every hour in the list end in the current
        # month's number. A minute that is nobody's month number tells the two apart.
        SalesRecord.objects.filter(pk=self.sales_record.pk).update(date_time=datetime(2026, 9, 3, 14, 37))

        listing = self.client.get(reverse("sales_record_filter"))
        self.assertEqual(listing.status_code, 200)
        content = listing.content.decode()
        self.assertIn("03/09/2026 14:37", content)
        self.assertNotIn("03/09/2026 14:09", content)


class TestValidationCredit(TestCase):
    """
    The one line that says who validated a subscription, rendered by every screen that shows it.

    The two fields arrived later than the flag, so a subscription validated before them carries
    neither: every combination still has to read as a finished sentence.
    """

    def setUp(self):
        self.contact = create_contact(name="Credit Test", phone="099111666")
        self.subscription = create_subscription(self.contact)
        self.user = User.objects.create_user(
            username="validator", password="x", first_name="Ana", last_name="Gestora"
        )

    def render(self):
        # Pinned to the language the panel actually runs in: the point of these is the wording a
        # manager reads, not the msgid behind it.
        with translation.override("es"):
            return render_to_string(
                "components/_validation_credit.html", {"subscription": self.subscription}
            ).strip()

    def test_names_the_person_and_the_moment(self):
        self.subscription.validated_by = self.user
        self.subscription.validated_date = datetime(2026, 9, 3, 14, 37)
        self.assertEqual(self.render(), "Validada por Ana Gestora el 03/09/2026 14:37")

    def test_a_user_with_no_full_name_falls_back_to_the_username(self):
        nameless = User.objects.create_user(username="nameless", password="x")
        self.subscription.validated_by = nameless
        self.subscription.validated_date = datetime(2026, 9, 3, 14, 37)
        self.assertIn("nameless", self.render())

    def test_no_user_means_the_system_did_it(self):
        self.subscription.validated_date = datetime(2026, 9, 3, 14, 37)
        self.assertEqual(self.render(), "Validada por el sistema el 03/09/2026 14:37")

    def test_an_old_validation_with_neither_field_still_reads_as_a_sentence(self):
        self.assertEqual(self.render(), "Validada, sin registro de quién ni cuándo")
