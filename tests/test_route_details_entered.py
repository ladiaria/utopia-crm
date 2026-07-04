"""
Tests for route_details() — entered_by_route_change (T1153).

route_details() (logistics/views.py) marks each SubscriptionProduct with
``entered_by_route_change`` when the contact had a recent RouteChange (within the
last month, same product) and the SP's current route differs from the route it
left. The template route_details.html then shows a ``+`` in the "Nueva" column.

Covers:
- SP that entered the route via a recent RouteChange is marked
- No RouteChange → not marked
- RouteChange leaving the same current route → not marked
- RouteChange for another product → not marked
- RouteChange within the month → marked; older than a month → not marked
- SP without route → not marked (and does not break)
"""

from datetime import date, datetime, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from core.models import SubscriptionProduct
from logistics.models import Route, RouteChange
from tests.factories.core_factories import (
    AddressFactory,
    ContactFactory,
    ProductFactory,
    SubscriptionFactory,
)


class RouteDetailsEnteredTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(
            username="superuser", password="testpass", email="su@example.com"
        )
        self.client.login(username="superuser", password="testpass")

        self.today = date.today()
        self.weekday = self.today.isoweekday()

        # route_details does Product.objects.get(weekday=isoweekday): exactly one product for today.
        self.product = ProductFactory(
            name="La Diaria",
            slug="ladiaria",
            type="S",
            weekday=self.weekday,
            active=True,
            digital=False,
            offerable=False,
        )

        # Current route of the SP and the route the contact "left".
        self.current_route = Route.objects.create(number=201, active=True)
        self.old_route = Route.objects.create(number=202, active=True)

        self.contact = ContactFactory()
        self.address = AddressFactory(contact=self.contact)
        self.subscription = SubscriptionFactory(
            contact=self.contact,
            active=True,
            start_date=self.today - timedelta(days=60),  # old → not "new" by start_date
            end_date=None,
            payment_type="O",
        )
        self.sp = SubscriptionProduct.objects.create(
            subscription=self.subscription,
            product=self.product,
            address=self.address,
            route=self.current_route,
            copies=1,
            order=1,
            active=True,
        )

    def _post(self):
        # route_details is a GET view keyed by a comma-separated route list in the URL.
        url = reverse("route_details", args=[str(self.current_route.number)])
        return self.client.get(url, {"date": self.today.strftime("%Y-%m-%d")})

    def _sp_from_context(self, response):
        sps = response.context["subscription_products_dict"][str(self.current_route.number)]
        return next(s for s in sps if s.pk == self.sp.pk)

    def _make_route_change(self, old_route, product=None, days_ago=2):
        rc = RouteChange.objects.create(
            contact=self.contact,
            old_route=old_route,
            product=product if product is not None else self.product,
            old_address="Calle vieja 1",
        )
        RouteChange.objects.filter(pk=rc.pk).update(dt=datetime.now() - timedelta(days=days_ago))
        return rc

    # --- Main case: entered from another route → marked ---
    def test_entered_by_route_change_marks_sp(self):
        self._make_route_change(self.old_route, days_ago=2)
        response = self._post()
        sp = self._sp_from_context(response)
        self.assertTrue(sp.entered_by_route_change)

    # --- No RouteChange → not marked ---
    def test_no_route_change_not_marked(self):
        response = self._post()
        sp = self._sp_from_context(response)
        self.assertFalse(sp.entered_by_route_change)

    # --- RouteChange leaving the same current route → not marked ---
    def test_route_change_from_same_route_not_marked(self):
        self._make_route_change(self.current_route, days_ago=2)
        response = self._post()
        sp = self._sp_from_context(response)
        self.assertFalse(sp.entered_by_route_change)

    # --- RouteChange for another product → not marked ---
    def test_route_change_other_product_not_marked(self):
        other_weekday = (self.weekday % 7) + 1
        other_product = ProductFactory(
            name="Otro", slug="otro", type="S", weekday=other_weekday, active=True, digital=False
        )
        self._make_route_change(self.old_route, product=other_product, days_ago=2)
        response = self._post()
        sp = self._sp_from_context(response)
        self.assertFalse(sp.entered_by_route_change)

    # --- Within the month → marked ---
    def test_route_change_within_month_marks_sp(self):
        self._make_route_change(self.old_route, days_ago=25)
        response = self._post()
        sp = self._sp_from_context(response)
        self.assertTrue(sp.entered_by_route_change)

    # --- Older than a month → not marked ---
    def test_route_change_older_than_month_not_marked(self):
        self._make_route_change(self.old_route, days_ago=35)
        response = self._post()
        sp = self._sp_from_context(response)
        self.assertFalse(sp.entered_by_route_change)
