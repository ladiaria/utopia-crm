# coding=utf-8
"""
The update screen of a free subscription (update-free-subscription).

It used to save the contact and the dates and nothing else: checking or unchecking a product changed nothing, and
the template drew every product the subscription had twice (one card checked, one empty), so the empty one won the
POST. Now there is one card per offerable product, and saving makes the subscription's products match the checked
ones.

The products are built by hand: the base repo ships no product catalogue, and the tests need a paper product, a
digital one and one that is not offerable.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Address, ContactProductHistory, Product, SubscriptionProduct

from tests.factory import create_contact, create_subscription


class TestUpdateFreeSubscription(TestCase):
    def setUp(self):
        User.objects.create_superuser(username="manager", password="x")
        self.client.login(username="manager", password="x")
        self.contact = create_contact(name="Free Sub", phone="099111555")
        self.home = Address.objects.create(contact=self.contact, address_1="Home 1", default=True)
        self.office = Address.objects.create(contact=self.contact, address_1="Office 2")
        self.paper = Product.objects.create(name="Paper", slug="paper", type="S", offerable=True)
        self.weekend = Product.objects.create(name="Weekend", slug="weekend", type="S", offerable=True)
        self.digital = Product.objects.create(name="Online", slug="online", type="S", offerable=True, digital=True)
        self.hidden = Product.objects.create(name="Hidden", slug="hidden", type="S", offerable=False)
        self.subscription = create_subscription(self.contact, subscription_type="F", payment_type="S")
        self.subscription.active = True
        self.subscription.save()
        self.subscription.add_product(self.paper, address=self.home)
        self.url = reverse("update_free_subscription", args=[self.subscription.id])

    def post(self, products):
        data = {
            "name": self.contact.name,
            "last_name": self.contact.last_name or "",
            "phone": self.contact.phone,
            "mobile": "",
            "email": "",
            "notes": "",
            "start_date": "2026-09-01",
            "end_date": "2026-09-08",
            "free_subscription_requested_by": "PR",
        }
        for product, fields in products.items():
            data["check-{}".format(product.id)] = product.id
            for name, value in fields.items():
                data["{}-{}".format(name, product.id)] = value
        return self.client.post(self.url, data)

    def products(self):
        return set(self.subscription.subscriptionproduct_set.values_list("product__slug", flat=True))

    def test_draws_each_product_once(self):
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertEqual(content.count('name="check-{}"'.format(self.paper.id)), 1)
        self.assertEqual(content.count('name="check-{}"'.format(self.weekend.id)), 1)
        self.assertNotIn('name="check-{}"'.format(self.hidden.id), content)

    def test_an_empty_message_is_not_drawn_as_none(self):
        response = self.client.get(self.url)
        self.assertNotIn('value="None"', response.content.decode())

    def test_a_paper_product_with_no_address_starts_on_nothing(self):
        SubscriptionProduct.objects.filter(subscription=self.subscription).update(address=None)
        response = self.client.get(self.url)
        content = response.content.decode()
        select = content.split('id="address-{}"'.format(self.paper.id))[1].split("</select>")[0]
        self.assertRegex(select, r'value=""')
        self.assertNotIn("selected", select)

    def test_adds_the_checked_products(self):
        response = self.post(
            {self.paper: {"address": self.home.id}, self.weekend: {"address": self.office.id}, self.digital: {}}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.products(), {"paper", "weekend", "online"})
        weekend = self.subscription.subscriptionproduct_set.get(product=self.weekend)
        self.assertEqual(weekend.address, self.office)
        self.assertIsNone(self.subscription.subscriptionproduct_set.get(product=self.digital).address)

    def test_removes_the_unchecked_ones(self):
        self.subscription.add_product(self.weekend, address=self.home)
        self.post({self.weekend: {"address": self.home.id}})
        self.assertEqual(self.products(), {"weekend"})
        self.assertTrue(
            ContactProductHistory.objects.filter(
                subscription=self.subscription, product=self.paper, status="D"
            ).exists()
        )
        self.subscription.refresh_from_db()
        self.assertTrue(self.subscription.active)

    def test_updates_the_ones_it_already_had(self):
        self.post({self.paper: {"address": self.office.id, "copies": 2, "message": "Hi", "instructions": "Door"}})
        sp = self.subscription.subscriptionproduct_set.get(product=self.paper)
        self.assertEqual(
            (sp.address, sp.copies, sp.label_message, sp.special_instructions), (self.office, 2, "Hi", "Door")
        )

    def test_leaves_alone_the_products_it_does_not_show(self):
        self.subscription.add_product(self.hidden, address=self.home)
        self.post({self.paper: {"address": self.home.id}})
        self.assertEqual(self.products(), {"paper", "hidden"})

    def test_a_paper_product_without_an_address_changes_nothing(self):
        response = self.post({self.paper: {"address": self.home.id}, self.weekend: {"address": ""}})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Weekend", str(response.context["form"].non_field_errors()))
        self.assertEqual(self.products(), {"paper"})
        self.subscription.refresh_from_db()
        self.assertNotEqual(str(self.subscription.end_date), "2026-09-08")

    def test_an_address_of_somebody_else_does_not_count(self):
        other = Address.objects.create(contact=create_contact(name="Other", phone="099111666"), address_1="Elsewhere")
        response = self.post({self.weekend: {"address": other.id}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.products(), {"paper"})

    def test_unchecking_everything_is_refused(self):
        response = self.post({})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.products(), {"paper"})
        self.subscription.refresh_from_db()
        self.assertTrue(self.subscription.active)
