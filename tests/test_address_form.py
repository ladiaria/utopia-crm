# coding=utf-8
"""
The address screens (add, edit, normalize) and their form, SugerenciaGeorefForm.

The form used to include "default", "contact" and "verified", which no screen draws. A checkbox missing from the POST
reads as False, so editing a default address took the mark away. The screens also swallowed the form errors, and
the address search could not tell a georeferencing service that is down from a search with no results.
"""
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Address
from support.forms import SugerenciaGeorefForm

from tests.factory import create_contact


@override_settings(GEOREF_SERVICES=False)
class TestAddressForm(TestCase):
    def setUp(self):
        User.objects.create_superuser(username="agent", password="x")
        self.client.login(username="agent", password="x")
        self.contact = create_contact(name="Address", phone="099111777")
        self.address = Address.objects.create(
            contact=self.contact, address_1="Street 1", address_2="Apt 2", city="Montevideo", default=True
        )

    def data(self, **kwargs):
        data = {"address_1": "Street 10", "address_2": "Apt 2", "city": "Montevideo", "address_type": "physical"}
        data.update(kwargs)
        return data

    def test_the_form_has_no_default_contact_or_verified(self):
        self.assertFalse({"default", "contact", "verified"} & set(SugerenciaGeorefForm().fields))

    def test_editing_a_default_address_keeps_it_default(self):
        response = self.client.post(
            reverse("editar_direccion", args=[self.contact.id, self.address.id]), self.data(save="1")
        )
        self.assertEqual(response.status_code, 302)
        self.address.refresh_from_db()
        self.assertEqual(self.address.address_1, "Street 10")
        self.assertTrue(self.address.default)
        self.assertEqual(self.address.contact, self.contact)

    def test_editing_keeps_verified(self):
        Address.objects.filter(pk=self.address.pk).update(verified=True)
        form = SugerenciaGeorefForm(self.data(), instance=Address.objects.get(pk=self.address.pk))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save().verified)

    def test_a_new_address_is_not_default(self):
        response = self.client.post(reverse("agregar_direccion", args=[self.contact.id]), self.data(save="1"))
        self.assertEqual(response.status_code, 302)
        new = Address.objects.get(contact=self.contact, address_1="Street 10")
        self.assertFalse(new.default)

    def test_edit_shows_the_errors(self):
        response = self.client.post(
            reverse("editar_direccion", args=[self.contact.id, self.address.id]), self.data(save="1", address_1="")
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("address_1", response.context["form"].errors)
        self.assertContains(response, "alert alert-danger")
        self.address.refresh_from_db()
        self.assertEqual(self.address.address_1, "Street 1")

    def test_add_shows_the_errors_instead_of_crashing(self):
        # It used to fall through to the suggestion branch and split a missing "sugerencias": a 500.
        response = self.client.post(
            reverse("agregar_direccion", args=[self.contact.id]), self.data(save="1", address_2="")
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("address_2", response.context["form"].errors)
        self.assertContains(response, "alert alert-danger")


@override_settings(SERVICIO_DIRECCION_AUTOCOMPLETADO="http://georef.test/autocompletar")
class TestAddressSearch(TestCase):
    def setUp(self):
        self.url = reverse("ajax_sugerir_direccion_autocompletar")

    def test_warns_when_the_service_is_down(self):
        with mock.patch("util.location_utils._georef_get", return_value=None):
            response = self.client.get(self.url, {"q_direccion": "Calle 123"})
        self.assertTrue(response.context["servicio_caido"])
        self.assertContains(response, "alert-warning")

    def test_no_results_is_not_a_service_down(self):
        with mock.patch("util.location_utils._georef_get", return_value=[]):
            response = self.client.get(self.url, {"q_direccion": "Calle 123"})
        self.assertFalse(response.context["servicio_caido"])
        self.assertNotContains(response, "alert-warning")

    def test_an_empty_search_asks_nothing(self):
        with mock.patch("util.location_utils._georef_get") as georef_get:
            response = self.client.get(self.url, {"q_direccion": ""})
        georef_get.assert_not_called()
        self.assertFalse(response.context["servicio_caido"])


@override_settings(GEOREF_SERVICES=False)
class TestAddressWithNoType(TestCase):
    def setUp(self):
        User.objects.create_superuser(username="agent", password="x")
        self.client.login(username="agent", password="x")
        self.contact = create_contact(name="Old address", phone="099111888")
        # Thousands of old addresses have no type, and the screens carry it in a hidden field.
        self.address = Address.objects.create(
            contact=self.contact, address_1="Street 1", address_2="Apt 2", city="Montevideo", address_type=""
        )

    def test_can_be_edited_and_becomes_physical(self):
        response = self.client.post(
            reverse("editar_direccion", args=[self.contact.id, self.address.id]),
            {"address_1": "Street 10", "address_2": "Apt 2", "city": "Montevideo", "address_type": "", "save": "1"},
        )
        self.assertEqual(response.status_code, 302)
        self.address.refresh_from_db()
        self.assertEqual((self.address.address_1, self.address.address_type), ("Street 10", "physical"))
