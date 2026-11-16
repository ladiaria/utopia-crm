# coding=utf-8
"""
The contact screen shows the address' own country, and warns about a missing state only where there are states to
choose from (it/utopia-crm-ladiaria#144).
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Address, Country, State

from tests.factory import create_contact


class AddressDetailCountryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.contact = create_contact("Address detail country", "29000144")
        cls.uruguay, _ = Country.objects.get_or_create(code="UY", defaults={"name": "Uruguay"})
        # A country with no states on file, like the foreign ones a PayPal address brings
        cls.foreign, _ = Country.objects.get_or_create(code="FJ", defaults={"name": "Fiyi"})
        State.objects.filter(country=cls.foreign).delete()
        cls.montevideo = State.objects.create(name="Montevideo (test)", country=cls.uruguay)
        cls.user = User.objects.create_superuser(username="address_detail_country", password="x")

    def address(self, **kwargs):
        return Address.objects.create(contact=self.contact, address_1="Treinta y Tres 1479", **kwargs)

    def detail_line(self, label):
        """The text of a line of the address card, from its label to the end of its div."""
        self.client.force_login(self.user)
        content = self.client.get(reverse("contact_detail", args=[self.contact.pk])).content.decode()
        return content.split(f"<strong>{label}:</strong>", 1)[1].split("</div>", 1)[0]

    def test_without_a_state_the_country_is_still_shown(self):
        self.address(country=self.foreign)
        line = self.detail_line("Country")
        self.assertIn(self.foreign.name, line)
        self.assertNotIn("fa-exclamation-triangle", line)

    def test_without_a_country_the_country_line_warns(self):
        self.address()
        line = self.detail_line("Country")
        self.assertIn("-", line)
        self.assertIn("fa-exclamation-triangle", line)

    def test_a_foreign_address_without_a_state_does_not_warn_about_it(self):
        self.address(country=self.foreign)
        self.assertNotIn("fa-exclamation-triangle", self.detail_line("State"))

    def test_an_address_of_a_country_with_states_warns_about_a_missing_one(self):
        self.address(country=self.uruguay)
        self.assertIn("fa-exclamation-triangle", self.detail_line("State"))

    def test_needs_state(self):
        self.assertFalse(self.address(state=self.montevideo).needs_state)
        self.assertTrue(self.address(country=self.uruguay).needs_state)
        self.assertTrue(self.address().needs_state)
        self.assertFalse(self.address(country=self.foreign).needs_state)
