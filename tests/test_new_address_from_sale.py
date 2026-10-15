# coding=utf-8
"""
"New address" opened from a sale (``agregar_direccion?stayhere=True``).

The address window used to go back to an empty form once the address was saved, and the sale only saw the new address
after pressing "Reload addresses". Whoever did not press it took the address for lost and loaded it again, so contacts
ended up with the same address several times. Now the window ends on direccion_guardada, which tells the sale's window
to reload its address lists on its own (static/js/new_address.js) and closes itself.
"""
from unittest import mock

from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Address

from tests.factory import create_contact


class NewAddressTestCase(TestCase):
    def setUp(self):
        User.objects.create_superuser(username="agent", password="x")
        self.client.login(username="agent", password="x")
        self.contact = create_contact(name="Sale", phone="099111999")

    def data(self, **kwargs):
        data = {"address_1": "Street 10", "address_2": "Apt 2", "city": "Montevideo", "address_type": "physical"}
        data.update(kwargs)
        return data


@override_settings(GEOREF_SERVICES=False)
class TestAddAddressFromSale(NewAddressTestCase):
    def add_url(self, stayhere=True):
        url = reverse("agregar_direccion", args=[self.contact.id])
        return url + "?stayhere=True" if stayhere else url

    def test_saving_ends_on_the_saved_page(self):
        response = self.client.post(self.add_url(), self.data(save="1"))
        address = Address.objects.get(contact=self.contact)
        self.assertRedirects(response, reverse("direccion_guardada", args=[self.contact.id, address.id]))

    def test_saving_without_georeferencing_ends_on_the_saved_page(self):
        response = self.client.post(self.add_url(), self.data(save_needs_georef="1"))
        address = Address.objects.get(contact=self.contact)
        self.assertTrue(address.needs_georef)
        self.assertRedirects(response, reverse("direccion_guardada", args=[self.contact.id, address.id]))

    def test_not_from_a_sale_still_goes_to_the_contact(self):
        response = self.client.post(self.add_url(stayhere=False), self.data(save="1"))
        self.assertRedirects(response, reverse("contact_detail", args=[self.contact.id]), fetch_redirect_response=False)

    def test_the_saved_page_tells_the_sale(self):
        address = Address.objects.create(contact=self.contact, address_1="Street 10", city="Montevideo")
        response = self.client.get(reverse("direccion_guardada", args=[self.contact.id, address.id]))
        self.assertContains(response, "js/new_address.js")
        self.assertContains(response, "announceNewAddress(%d, %d)" % (self.contact.id, address.id))

    def test_the_saved_page_only_shows_addresses_of_the_contact(self):
        other = create_contact(name="Other", phone="099111998")
        address = Address.objects.create(contact=other, address_1="Street 10", city="Montevideo")
        response = self.client.get(reverse("direccion_guardada", args=[self.contact.id, address.id]))
        self.assertEqual(response.status_code, 404)


@override_settings(GEOREF_SERVICES=True)
class TestNormalizeFromSale(NewAddressTestCase):
    """
    "Look for other alternatives" saves the address first and goes on to normalize it. From a sale, the address
    already exists there, so the sale has to hear about it even if no suggestion is ever chosen.
    """

    def setUp(self):
        super().setUp()
        self.address = Address.objects.create(
            contact=self.contact, address_1="Street 10", city="Montevideo", needs_georef=True
        )
        self.url = reverse("normalizar_direccion", args=[self.contact.id, self.address.id])

    def test_no_suggestions_ends_on_the_saved_page(self):
        with mock.patch("support.location.buscar_alternativas_normalizadas", return_value=[]):
            response = self.client.get(self.url + "?stayhere=True")
        self.assertRedirects(
            response,
            reverse("direccion_guardada", args=[self.contact.id, self.address.id]),
            fetch_redirect_response=False,
        )

    def test_no_suggestions_not_from_a_sale_still_goes_to_the_contact(self):
        with mock.patch("support.location.buscar_alternativas_normalizadas", return_value=[]):
            response = self.client.get(self.url)
        self.assertRedirects(response, reverse("contact_detail", args=[self.contact.id]), fetch_redirect_response=False)


class TestNewAddressLink(TestCase):
    def test_the_link_carries_what_the_script_needs(self):
        contact = create_contact(name="Link", phone="099111997")
        html = render_to_string("new_address_link.html", {"contact": contact})
        self.assertIn('class="new_address_link', html)
        self.assertIn('data-contact-id="%d"' % contact.id, html)
        self.assertIn(reverse("api_get_addresses", args=[contact.id]), html)
        self.assertIn(reverse("agregar_direccion", args=[contact.id]) + "?stayhere=True", html)
