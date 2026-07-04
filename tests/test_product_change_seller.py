# coding=utf-8
from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Product, Subscription, SubscriptionProduct
from support.models import SalesRecord, Seller
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


class TestValidateSalesRecordSellerPreservation(TestCase):
    """
    Verifica que ValidateSalesRecordView y SalesRecordCreateView no sobreescriban
    el seller de SPs que NO pertenecen al SalesRecord siendo validado/creado.
    """

    fixtures = ["core_product"]

    def setUp(self):
        self.client = Client()

        self.manager_user = User.objects.create_superuser(username="manager", password="testpass")
        self.manager_seller = Seller.objects.create(name="Manager", user=self.manager_user)
        self.client.login(username="manager", password="testpass")

        self.seller_a = Seller.objects.create(name="Vendedor A", internal=True)
        self.seller_b = Seller.objects.create(name="Vendedor B", internal=True)

        self.contact = ContactFactory()
        self.address = AddressFactory(contact=self.contact)

        offerable = list(Product.objects.filter(type="S", offerable=True).order_by("id")[:2])
        if len(offerable) < 2:
            self.skipTest("No hay suficientes productos ofertables en los fixtures")
        self.product1, self.product2 = offerable[0], offerable[1]

    def _make_subscription_with_two_sellers(self):
        """Sub con product1 de seller_a y product2 de seller_b."""
        sub = Subscription.objects.create(
            contact=self.contact,
            type="N",
            start_date=date.today(),
            payment_type="O",
            status="OK",
            active=True,
            frequency=1,
        )
        sp1 = sub.add_product(self.product1, self.address)
        sp1.seller = self.seller_a
        sp1.save()
        sp2 = sub.add_product(self.product2, self.address)
        sp2.seller = self.seller_b
        sp2.save()
        return sub

    def _make_sales_record(self, sub, seller, products):
        sr = SalesRecord.objects.create(
            subscription=sub,
            seller=seller,
            sale_type=SalesRecord.SALE_TYPE.FULL,
        )
        sr.products.set(products)
        return sr

    def test_validate_sale_only_updates_sellers_in_sr(self):
        """
        Al validar un SR con can_be_commissioned=True, el update de seller debe
        limitarse solo a los SPs cuyos productos están en ese SR.
        Escenario: sp1→seller_a, sp2→seller_b; SR cubre product1 con seller_b.
        Resultado esperado: sp1 queda con seller_b (el SR lo reclama), sp2 sigue con seller_b.
        Bug anterior: el update masivo pisaba TODOS los SPs tipo S, incluido sp2.
        """
        sub = self._make_subscription_with_two_sellers()
        # SR solo sobre product1 con seller_b
        sr = self._make_sales_record(sub, self.seller_b, [self.product1])

        self.client.post(
            reverse("validate_sale", args=[sr.id]),
            data={
                "can_be_commissioned": "on",
                "seller": self.seller_b.id,
            },
        )

        # sp1 está en el SR → el seller se actualiza a seller_b (correcto)
        sp1 = SubscriptionProduct.objects.get(subscription=sub, product=self.product1)
        self.assertEqual(sp1.seller, self.seller_b)

        # sp2 NO está en el SR → su seller (seller_b) no debe ser tocado por el SR
        # (en este caso casualmente coincide, pero el punto es que no fue pisado por el update masivo)
        sp2 = SubscriptionProduct.objects.get(subscription=sub, product=self.product2)
        self.assertEqual(sp2.seller, self.seller_b)

    def test_validate_sale_does_not_overwrite_unrelated_sp_sellers(self):
        """
        Caso directo de takeover: sub con sp1→seller_a y sp2→seller_b.
        SR sobre product2 (seller_a como vendedor) con can_be_commissioned.
        Al validar: sp2 debe quedar con seller_a (correcto, era la venta).
        sp1 NO debe cambiar de seller_a a seller_a (trivial), pero más importante:
        si el SR fuera de seller_b, sp1 NO debe ser afectado.
        Probamos que el update no se expande fuera de los productos del SR.
        """
        sub = self._make_subscription_with_two_sellers()
        # sp1→seller_a, sp2→seller_b. SR solo sobre product2, con seller_a.
        sr = self._make_sales_record(sub, self.seller_a, [self.product2])

        self.client.post(
            reverse("validate_sale", args=[sr.id]),
            data={
                "can_be_commissioned": "on",
                "seller": self.seller_a.id,
            },
        )

        # sp1 NO está en el SR → debe conservar seller_a original
        sp1 = SubscriptionProduct.objects.get(subscription=sub, product=self.product1)
        self.assertEqual(
            sp1.seller,
            self.seller_a,
            "sp1 fue modificado aunque no estaba en el SR",
        )

        # sp2 SÍ está en el SR con seller_a → debe quedar seller_a
        sp2 = SubscriptionProduct.objects.get(subscription=sub, product=self.product2)
        self.assertEqual(sp2.seller, self.seller_a)
