# coding=utf-8
from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Product, Subscription, SubscriptionProduct
from support.models import Seller
from tests.factories.core_factories import AddressFactory, ContactFactory


class TestProductChangeSellerPreservation(TestCase):
    """
    Verifica que product_change (vista base) preserve el seller de SubscriptionProducts
    existentes y asigne el seller del operador solo a los productos nuevos.
    """

    fixtures = ["core_product"]

    def setUp(self):
        self.client = Client()

        self.operator_user = User.objects.create_superuser(username="operator", password="testpass")
        self.operator_seller = Seller.objects.create(name="Operador", user=self.operator_user)
        self.client.login(username="operator", password="testpass")

        self.original_user = User.objects.create_superuser(username="original", password="testpass")
        self.original_seller = Seller.objects.create(name="Original", user=self.original_user)

        self.contact = ContactFactory()
        self.address = AddressFactory(contact=self.contact)

        offerable = list(Product.objects.filter(type="S", offerable=True).order_by("id")[:2])
        if len(offerable) < 2:
            self.skipTest("No hay suficientes productos ofertables en los fixtures")
        self.product1, self.product2 = offerable[0], offerable[1]

    def _make_subscription_with_seller(self, seller=None):
        sub = Subscription.objects.create(
            contact=self.contact,
            type="N",
            start_date=date.today(),
            payment_type="O",
            status="OK",
            active=True,
            frequency=1,
        )
        sp = sub.add_product(self.product1, self.address)
        sp.seller = seller
        sp.save()
        return sub

    def test_product_change_preserves_seller_on_existing_products(self):
        """Al hacer cambio de producto, el producto existente conserva su seller original."""
        sub = self._make_subscription_with_seller(self.original_seller)
        self.client.post(
            reverse("product_change", args=[sub.id]),
            data={
                "end_date": date.today().strftime("%Y-%m-%d"),
                "unsubscription_channel": 4,
                "unsubscription_addendum": "",
            },
        )
        new_sub = Subscription.objects.get(updated_from=sub)
        sp = SubscriptionProduct.objects.get(subscription=new_sub, product=self.product1)
        self.assertEqual(sp.seller, self.original_seller)

    def test_product_change_new_products_get_current_seller(self):
        """Al hacer cambio de producto, el producto nuevo toma el seller del operador."""
        sub = self._make_subscription_with_seller(self.original_seller)
        self.client.post(
            reverse("product_change", args=[sub.id]),
            data={
                "end_date": date.today().strftime("%Y-%m-%d"),
                "unsubscription_channel": 4,
                "unsubscription_addendum": "",
                f"activateproduct-{self.product2.id}": "on",
            },
        )
        new_sub = Subscription.objects.get(updated_from=sub)
        sp = SubscriptionProduct.objects.get(subscription=new_sub, product=self.product2)
        self.assertEqual(sp.seller, self.operator_seller)

    def test_product_change_null_seller_stays_null(self):
        """Si el SP original no tiene seller, el nuevo tampoco debe heredar el del operador."""
        sub = self._make_subscription_with_seller(seller=None)
        self.client.post(
            reverse("product_change", args=[sub.id]),
            data={
                "end_date": date.today().strftime("%Y-%m-%d"),
                "unsubscription_channel": 4,
                "unsubscription_addendum": "",
            },
        )
        new_sub = Subscription.objects.get(updated_from=sub)
        sp = SubscriptionProduct.objects.get(subscription=new_sub, product=self.product1)
        self.assertIsNone(sp.seller)
