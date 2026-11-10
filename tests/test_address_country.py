# coding=utf-8
"""An address without a country takes its state's (it/utopia-crm-ladiaria#122)."""
import importlib

from django.apps import apps
from django.test import TestCase

from core.models import Address, Country, State

from tests.factory import create_contact

# import_module and not `import`: the module name starts with a digit
MIGRATION = importlib.import_module("core.migrations.0125_address_country_from_state")


class AddressCountryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.contact = create_contact("Address country", "29000127")
        cls.uruguay, _ = Country.objects.get_or_create(code="UY", defaults={"name": "Uruguay"})
        cls.argentina, _ = Country.objects.get_or_create(code="AR", defaults={"name": "Argentina"})
        cls.montevideo = State.objects.create(name="Montevideo (test)", country=cls.uruguay)

    def address(self, **kwargs):
        return Address.objects.create(contact=self.contact, address_1="Treinta y Tres 1479", **kwargs)

    def test_without_a_country_it_takes_the_state_one(self):
        self.assertEqual(self.address(state=self.montevideo).country, self.uruguay)

    def test_a_country_that_comes_with_the_address_is_kept(self):
        # A foreign billing address (PayPal) brings its own country
        self.assertEqual(self.address(state=self.montevideo, country=self.argentina).country, self.argentina)

    def test_without_a_state_it_stays_without_a_country(self):
        self.assertIsNone(self.address().country)

    def test_the_migration_fills_the_existing_ones_and_leaves_the_rest(self):
        with_state, without_state = self.address(state=self.montevideo), self.address()
        foreign = self.address(state=self.montevideo, country=self.argentina)
        # As they were before: created without a country, bypassing save
        Address.objects.filter(pk__in=[with_state.pk, without_state.pk]).update(country=None)
        MIGRATION.country_from_state(apps, None)
        with_state.refresh_from_db(), without_state.refresh_from_db(), foreign.refresh_from_db()
        self.assertEqual(with_state.country, self.uruguay)
        self.assertIsNone(without_state.country)
        self.assertEqual(foreign.country, self.argentina)
