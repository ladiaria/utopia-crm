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
        # Pinned to English on purpose. What is under test is which of the four sentences the
        # partial picks, not how it was translated, and asserting on the Spanish would tie these
        # to the contents of the .po and to whatever LANGUAGE_CODE the machine ends up with:
        # `test_settings` asks for en-us, but a `local_test_settings` that re-imports `settings`
        # quietly hands it back to es.
        with translation.override("en"):
            return render_to_string(
                "components/_validation_credit.html", {"subscription": self.subscription}
            ).strip()

    def test_names_the_person_and_the_moment(self):
        self.subscription.validated_by = self.user
        self.subscription.validated_date = datetime(2026, 9, 3, 14, 37)
        self.assertEqual(self.render(), "Validated by Ana Gestora on 03/09/2026 14:37")

    def test_a_user_with_no_full_name_falls_back_to_the_username(self):
        nameless = User.objects.create_user(username="nameless", password="x")
        self.subscription.validated_by = nameless
        self.subscription.validated_date = datetime(2026, 9, 3, 14, 37)
        self.assertIn("nameless", self.render())

    def test_no_user_means_the_system_did_it(self):
        self.subscription.validated_date = datetime(2026, 9, 3, 14, 37)
        self.assertEqual(self.render(), "Validated by the system on 03/09/2026 14:37")

    def test_an_old_validation_with_neither_field_still_reads_as_a_sentence(self):
        self.assertEqual(self.render(), "Validated, with no record of who did it or when")


@override_settings(
    SELLER_COMMISSION_PRODUCTS_SLUGS={"extra-product": 105},
    SELLER_COMMISSION_PRODUCTS_COUNT={1: 0, 2: 100},
    SELLER_COMMISSION_PAYMENT_METHODS={"S": 80},
    SELLER_COMMISSION_SUBSCRIPTION_FREQUENCY={1: 0, 3: 50},
)
class TestCommissionShownAfterValidating(TestCase):
    """
    A commission stops being a forecast the moment the sale is validated.

    Before that, what the panel shows is what *would* be paid: a partial sale forecasts nothing,
    because by default only full sales commission. But whoever validates can decide otherwise, and
    from then on the stored value is the one that reaches the seller's liquidation. Recomputing the
    components at that point answers a question nobody asked, and used to make a validated partial
    sale read "... + 105 (specific products) = 0" while the list said 105.
    """

    def setUp(self):
        self.user = User.objects.create_superuser(username="commission-manager", password="x")
        self.client.login(username="commission-manager", password="x")
        self.contact = create_contact(name="Partial Sale", phone="099111555")
        self.seller = Seller.objects.create(name="Commissioned seller", internal=True)
        self.product = Product.objects.create(
            name="Extra product", slug="extra-product", type="S", offerable=True
        )
        self.subscription = create_subscription(self.contact, payment_type="S")
        self.sales_record = SalesRecord.objects.create(
            subscription=self.subscription,
            seller=self.seller,
            price=327,
            sale_type=SalesRecord.SALE_TYPE.PARTIAL,
        )
        self.sales_record.products.add(self.product)

    def validate(self, **extra):
        data = {"seller": self.seller.pk, "can_be_commissioned": "on"}
        data.update(extra)
        response = self.client.post(reverse("validate_sale", args=[self.sales_record.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.sales_record.refresh_from_db()
        self.subscription.refresh_from_db()

    def test_an_unvalidated_partial_sale_still_forecasts_nothing(self):
        # Unchanged behaviour: until somebody decides, a partial sale is worth no commission.
        self.assertFalse(self.sales_record.is_settled())
        self.assertEqual(self.sales_record.calculate_total_commission(), 0)
        self.assertEqual(self.sales_record.get_commission_value(), 0)
        self.assertIn("= 0", self.sales_record.calculate_commission())

    def test_a_validated_partial_sale_shows_what_was_actually_settled(self):
        self.validate()

        self.assertTrue(self.sales_record.is_settled())
        # 0 (payment type, gated to full sales) + 0 (1 product) + 0 (monthly) + 105 (the product)
        self.assertEqual(self.sales_record.total_commission_value, 105)
        self.assertEqual(self.sales_record.get_commission_value(), 105)
        # This is the regression: the breakdown may no longer add up on its own, but the figure
        # the panel ends on has to be the one the seller gets paid.
        self.assertNotIn("= 0", self.sales_record.calculate_commission())
        self.assertIn("105", self.sales_record.calculate_commission())

    def test_an_overridden_commission_says_so_instead_of_pretending_the_components_add_up(self):
        self.validate(override_commission_value=300)

        self.assertEqual(self.sales_record.total_commission_value, 300)
        self.assertEqual(self.sales_record.get_commission_value(), 300)
        with translation.override("en"):
            shown = str(self.sales_record.calculate_commission())
        # The components still total 105, so they are reported apart from the settled 300 rather
        # than joined to it with an "=" that would be a lie.
        self.assertIn("300", shown)
        self.assertIn("settled", shown)
        self.assertIn("105", shown)

    def test_a_validated_full_sale_is_unaffected(self):
        self.sales_record.sale_type = SalesRecord.SALE_TYPE.FULL
        self.sales_record.save()
        self.validate()

        # 80 (payment type) + 0 (1 product) + 0 (monthly) + 105 (the product)
        self.assertEqual(self.sales_record.total_commission_value, 185)
        self.assertEqual(self.sales_record.get_commission_value(), 185)
        self.assertIn("= 185", str(self.sales_record.calculate_commission()))

    def test_the_detail_shows_the_total_apart_from_its_components(self):
        # The validation screen gives the total its own weight and keeps the components as a
        # footnote, so there is never an "=" claiming a breakdown adds up to an overridden amount.
        self.validate(override_commission_value=300)
        response = self.client.get(reverse("validate_sale", args=[self.sales_record.pk]))
        content = response.content.decode()

        self.assertIn("<strong class=\"h5\">300", content)
        self.assertIn("105", self.sales_record.get_commission_breakdown())
        self.assertNotIn("=", self.sales_record.get_commission_breakdown())

    def test_a_free_subscription_still_explains_itself(self):
        free_subscription = create_subscription(self.contact, subscription_type="F", payment_type="S")
        free_record = SalesRecord.objects.create(subscription=free_subscription, price=0)

        with translation.override("en"):
            self.assertEqual(str(free_record.get_commission_breakdown()), "Free subscription: no commission")

    def test_it_says_when_a_partial_sale_is_not_going_to_commission_yet(self):
        with translation.override("en"):
            note = str(self.sales_record.get_commission_note())
        self.assertIn("partial sale pays no commission", note)

    def test_it_says_when_the_amount_was_typed_in_by_hand(self):
        self.validate(override_commission_value=300)

        self.assertTrue(self.sales_record.commission_overridden)
        with translation.override("en"):
            note = str(self.sales_record.get_commission_note())
        self.assertIn("entered by hand", note)

    def test_it_says_when_the_record_is_not_commissionable_at_all(self):
        # Unchecking the box is a decision, and a 0 with no explanation looks like a bug.
        response = self.client.post(
            reverse("validate_sale", args=[self.sales_record.pk]), {"seller": self.seller.pk}
        )
        self.assertEqual(response.status_code, 302)
        self.sales_record.refresh_from_db()

        self.assertFalse(self.sales_record.can_be_commissioned)
        with translation.override("en"):
            note = str(self.sales_record.get_commission_note())
        self.assertIn("not commissionable", note)

    def test_a_commission_that_came_out_of_the_breakdown_needs_no_note(self):
        self.sales_record.sale_type = SalesRecord.SALE_TYPE.FULL
        self.sales_record.save()
        self.validate()

        self.assertFalse(self.sales_record.commission_overridden)
        self.assertIsNone(self.sales_record.get_commission_note())

    def test_a_commissioned_partial_sale_needs_no_note_when_its_breakdown_adds_up(self):
        # "0 + 0 + 0 + 105" reads as 105 to anyone looking at it, so there is nothing to explain.
        # Comparing against calculate_total_commission() instead of the components flagged every
        # commissioned partial sale, because that method applies the "only full sales" rule and
        # answers 0.
        self.validate()

        self.assertFalse(self.sales_record.commission_overridden)
        self.assertEqual(self.sales_record.total_commission_value, 105)
        self.assertEqual(self.sales_record.sum_commission_components(), 105)
        self.assertIsNone(self.sales_record.get_commission_note())

    def test_it_says_when_the_components_really_stopped_adding_up(self):
        # The note is for the case it was written for: the sale was settled at one price and the
        # catalogue moved afterwards.
        self.validate()
        self.assertIsNone(self.sales_record.get_commission_note())

        with override_settings(SELLER_COMMISSION_PRODUCTS_SLUGS={"extra-product": 130}):
            self.assertEqual(self.sales_record.total_commission_value, 105)
            self.assertEqual(self.sales_record.sum_commission_components(), 130)
            with translation.override("en"):
                note = str(self.sales_record.get_commission_note())
        self.assertIn("no longer add up", note)

    def test_the_forecast_still_applies_the_partial_sale_rule(self):
        # sum_commission_components() must not be mistaken for the forecast: before validating, a
        # partial sale is still worth nothing no matter what its components add up to.
        self.assertEqual(self.sales_record.sum_commission_components(), 105)
        self.assertEqual(self.sales_record.calculate_total_commission(), 0)
        self.assertEqual(self.sales_record.get_commission_value(), 0)

    def test_the_list_reports_the_same_figure_as_the_detail(self):
        # The two screens disagreeing is what started this: they must read the same number both
        # before and after validating.
        self.assertEqual(
            self.sales_record.get_commission_value(), self.sales_record.calculate_total_commission()
        )
        self.validate()
        self.assertEqual(
            self.sales_record.get_commission_value(), self.sales_record.total_commission_value
        )


class TestFreeSubscriptionAddresses(TestCase):
    """
    Which products of a free subscription need an address and which do not.

    A digital product is delivered to the contact's email address, so a contact with no addresses at
    all can still be given one. That is how the regular subscription form already behaves, and the
    free one used to disagree: it refused to save anything without an address, digital or not.
    """

    def setUp(self):
        self.user = User.objects.create_superuser(username="manager_addresses", password="x")
        self.client.login(username="manager_addresses", password="x")
        self.contact = create_contact(name="No Address", phone="099111555", email="no.address@gmail.com")
        # The flag is what decides, not the slug: this one is digital without saying so in its name.
        self.digital = Product.objects.create(
            name="Premium online", slug="premium-online", type="S", offerable=True, digital=True
        )
        self.paper = Product.objects.create(name="Paper product", slug="paper-product", type="S", offerable=True)

    def post(self, products):
        data = {
            "name": self.contact.name,
            "last_name": "",
            "phone": self.contact.phone,
            "mobile": "",
            "email": self.contact.email,
            "notes": "",
            "start_date": "2026-09-01",
            "end_date": "2026-09-08",
            "free_subscription_requested_by": "PR",
        }
        for product, address in products:
            data["check-{}".format(product.id)] = "on"
            data["copies-{}".format(product.id)] = 1
            if address:
                data["address-{}".format(product.id)] = address.id
        return self.client.post(reverse("create_free_subscription", args=[self.contact.id]), data)

    def test_a_digital_product_is_saved_for_a_contact_with_no_addresses(self):
        response = self.post([(self.digital, None)])
        self.assertEqual(response.status_code, 302)

        subscription = Subscription.objects.get(contact=self.contact, type="F")
        subscription_product = subscription.subscriptionproduct_set.get(product=self.digital)
        self.assertIsNone(subscription_product.address)

    def test_a_paper_product_without_an_address_creates_nothing(self):
        response = self.post([(self.paper, None)])

        # The form comes back with the error instead of leaving a subscription nobody can deliver.
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paper product")
        self.assertFalse(Subscription.objects.filter(contact=self.contact).exists())

    def test_a_paper_product_next_to_a_digital_one_still_needs_its_address(self):
        # The digital product must not be a free pass for the rest of the selection.
        response = self.post([(self.digital, None), (self.paper, None)])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Subscription.objects.filter(contact=self.contact).exists())

    def test_both_are_saved_when_the_paper_one_has_an_address(self):
        address = Address.objects.create(contact=self.contact, address_1="Street 1")
        response = self.post([(self.digital, None), (self.paper, address)])
        self.assertEqual(response.status_code, 302)

        subscription = Subscription.objects.get(contact=self.contact, type="F")
        self.assertIsNone(subscription.subscriptionproduct_set.get(product=self.digital).address)
        self.assertEqual(subscription.subscriptionproduct_set.get(product=self.paper).address, address)

    def test_the_form_offers_no_address_selector_for_a_digital_product(self):
        Address.objects.create(contact=self.contact, address_1="Street 1")
        response = self.client.get(reverse("create_free_subscription", args=[self.contact.id]))

        # Having addresses is no reason to file a digital product under one of them.
        self.assertNotContains(response, 'id="address-{}"'.format(self.digital.id))
        self.assertContains(response, 'id="address-{}"'.format(self.paper.id))
