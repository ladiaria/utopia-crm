from django import forms
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.test import TestCase, override_settings

from core.models import Product

from tests.factory import create_address, create_contact, create_product, create_subscription


@override_settings(WEB_UPDATE_USER_ENABLED=False)
class TestBillingPriorityOrder(TestCase):
    # The base repo ships no product catalogue, and these products tie on purpose: the case the order must settle.

    def setUp(self):
        self.contact = create_contact("billing priority", "29000808")
        self.subscription = create_subscription(self.contact)

    def test_tie_is_broken_by_product_id(self):
        first = create_product(name="First", price=100, billing_priority=10)
        second = create_product(name="Second", price=100, billing_priority=10)
        # Added in reverse order, so the result cannot come from the insertion order
        self.subscription.add_product(second)
        self.subscription.add_product(first)
        self.assertEqual(self.subscription.get_first_product_by_priority(), first)

    def test_product_without_priority_goes_last(self):
        without = create_product(name="Without", price=100, billing_priority=None)
        with_priority = create_product(name="With", price=100, billing_priority=50)
        self.subscription.add_product(without)
        self.subscription.add_product(with_priority)
        self.assertEqual(self.subscription.get_first_product_by_priority(), with_priority)

    def test_only_subscription_and_other_products_count(self):
        newsletter = create_product(name="Newsletter", price=0, type="N", billing_priority=1)
        other = create_product(name="Other", price=100, type="O", billing_priority=5)
        self.subscription.add_product(newsletter)
        self.subscription.add_product(other)
        self.assertEqual(self.subscription.get_first_product_by_priority(), other)

    def test_no_billing_product(self):
        self.assertIsNone(self.subscription.get_first_product_by_priority())

    def test_address_by_priority_uses_the_same_order(self):
        first = create_product(name="First", price=100, billing_priority=10)
        second = create_product(name="Second", price=100, billing_priority=10)
        first_address = create_address("First street 1", self.contact)
        second_address = create_address("Second street 2", self.contact)
        self.subscription.add_product(second, address=second_address)
        self.subscription.add_product(first, address=first_address)
        self.assertEqual(self.subscription.get_full_address_by_priority(), first_address)
        self.assertEqual(self.subscription.get_address_by_priority(), "First street 1")


class TestBillingPriorityValidation(TestCase):

    def setUp(self):
        self.taken = create_product(name="Taken", price=100, billing_priority=10)

    def assert_tie_error(self, product):
        with self.assertRaises(ValidationError) as raised:
            product.full_clean()
        self.assertIn("billing_priority", raised.exception.message_dict)
        self.assertIn(f"Taken (id {self.taken.id})", raised.exception.message_dict["billing_priority"][0])

    def test_new_product_cannot_tie(self):
        self.assert_tie_error(Product(name="New", type="S", active=True, billing_priority=10))

    def test_other_type_cannot_tie(self):
        self.assert_tie_error(Product(name="New", type="O", active=True, billing_priority=10))

    def test_changing_the_priority_to_a_taken_one(self):
        product = create_product(name="Mine", price=100, billing_priority=20)
        product.billing_priority = 10
        self.assert_tie_error(product)

    def test_activating_a_tied_product(self):
        product = Product.objects.create(name="Mine", type="S", active=False, billing_priority=10)
        product.active = True
        self.assert_tie_error(product)

    def test_allowed(self):
        for product in (
            Product(name="Empty", type="S", active=True, billing_priority=None),
            Product(name="Inactive", type="S", active=False, billing_priority=10),
            Product(name="Newsletter", type="N", active=True, billing_priority=10),
            Product(name="Discount", type="D", active=True, billing_priority=10, discount_category="P"),
            Product(name="Free", type="S", active=True, billing_priority=11),
        ):
            with self.subTest(product=product.name):
                product.full_clean()

    def test_inactive_product_does_not_block(self):
        self.taken.active = False
        self.taken.save()
        Product(name="New", type="S", active=True, billing_priority=10).full_clean()

    def test_saved_tie_does_not_block_other_fields(self):
        # A tie saved before the rule existed: editing anything else must still work
        tied = create_product(name="Tied", price=100, billing_priority=10)
        tied.price = 200
        tied.full_clean()

    def test_form_without_the_field_gets_a_non_field_error(self):
        # Like the admin product list, whose editable columns do not include the priority
        product = create_product(name="Mine", price=100, type="N", billing_priority=10)
        form_class = forms.modelform_factory(Product, fields=["name", "type", "price"])
        form = form_class({"name": "Mine", "type": "S", "price": "100"}, instance=product)
        self.assertFalse(form.is_valid())
        self.assertIn(f"Taken (id {self.taken.id})", form.errors[NON_FIELD_ERRORS][0])
