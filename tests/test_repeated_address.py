# coding=utf-8
"""
Loading an address the contact already has.

Contacts ended up with the same address several times: the screens that create one never looked at the ones the
contact had. Now "New address" warns and offers the existing one, and the issue and scheduled address change forms use
it instead of creating another. Two addresses are the same one when street, second line, city and state match, with no
regard for case or repeated spaces (Address.same_place_key). The lists to choose from show the second line, which is
what tells apart two addresses on the same street.
"""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Address, State
from support.forms import NewAddressChangeScheduledTaskForm
from support.models import ScheduledTask

from tests.factory import create_contact


class TestSameAddress(TestCase):
    def setUp(self):
        self.contact = create_contact(name="Same", phone="099222111")
        self.state = State.objects.create(name="Montevideo")
        self.address = Address.objects.create(
            contact=self.contact, address_1="Havre 1910", address_2="Apto 2", city="Montevideo", state=self.state
        )

    def test_case_and_spaces_do_not_matter(self):
        same = Address.find_same(self.contact, " havre  1910", "APTO 2 ", "montevideo", self.state)
        self.assertEqual(same, self.address)

    def test_an_empty_second_line_is_the_same_as_none(self):
        address = Address.objects.create(contact=self.contact, address_1="Rivera 1", address_2=None, city="Montevideo")
        self.assertEqual(Address.find_same(self.contact, "Rivera 1", "", "Montevideo", None), address)

    def test_another_apartment_is_another_address(self):
        self.assertIsNone(Address.find_same(self.contact, "Havre 1910", "Apto 3", "Montevideo", self.state))

    def test_another_state_is_another_address(self):
        other_state = State.objects.create(name="Canelones")
        self.assertIsNone(Address.find_same(self.contact, "Havre 1910", "Apto 2", "Montevideo", other_state))

    def test_only_the_contact_addresses(self):
        other = create_contact(name="Other", phone="099222112")
        self.assertIsNone(Address.find_same(other, "Havre 1910", "Apto 2", "Montevideo", self.state))

    def test_the_verified_one_goes_first(self):
        verified = Address.objects.create(
            contact=self.contact, address_1="Havre 1910", address_2="Apto 2", city="Montevideo", state=self.state
        )
        Address.objects.filter(pk=verified.pk).update(verified=True)
        self.assertEqual(Address.find_same(self.contact, "Havre 1910", "Apto 2", "Montevideo", self.state), verified)

    def test_find_same_or_create_uses_the_existing_one_and_keeps_the_notes(self):
        address, created = Address.find_same_or_create(
            self.contact, "HAVRE 1910", "Apto 2", "Montevideo", self.state, notes="Timbre roto"
        )
        self.assertFalse(created)
        self.assertEqual(address, self.address)
        self.address.refresh_from_db()
        self.assertIn("Timbre roto", self.address.notes)
        self.assertEqual(Address.objects.filter(contact=self.contact).count(), 1)

    def test_find_same_or_create_creates_a_new_one(self):
        address, created = Address.find_same_or_create(self.contact, "Havre 1910", "Apto 3", "Montevideo", self.state)
        self.assertTrue(created)
        self.assertEqual((address.contact, address.address_2), (self.contact, "Apto 3"))

    def test_the_option_label_shows_the_second_line(self):
        self.assertEqual(self.address.get_option_label(), "Havre 1910, Apto 2, Montevideo, Montevideo")


@override_settings(GEOREF_SERVICES=False)
class TestAddRepeatedAddress(TestCase):
    def setUp(self):
        User.objects.create_superuser(username="agent", password="x")
        self.client.login(username="agent", password="x")
        self.contact = create_contact(name="Repeated", phone="099222113")
        self.address = Address.objects.create(
            contact=self.contact, address_1="Havre 1910", address_2="Apto 2", city="Montevideo"
        )
        self.url = reverse("agregar_direccion", args=[self.contact.id]) + "?stayhere=True"

    def data(self, **kwargs):
        data = {"address_1": "havre 1910", "address_2": "Apto 2", "city": "Montevideo", "address_type": "physical"}
        data.update(kwargs)
        return data

    def test_warns_instead_of_saving(self):
        response = self.client.post(self.url, self.data(save="1"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["repetida"], self.address)
        self.assertEqual(Address.objects.filter(contact=self.contact).count(), 1)
        # From a sale, using the one it has tells the sale about that one
        self.assertContains(
            response, reverse("direccion_guardada", args=[self.contact.id, self.address.id]) + "?ya_existia=1"
        )
        self.assertContains(response, 'name="guardar_igual"')

    def test_save_it_again_anyway(self):
        response = self.client.post(self.url, self.data(guardar_igual="save"))
        new = Address.objects.filter(contact=self.contact).exclude(pk=self.address.pk).get()
        self.assertRedirects(response, reverse("direccion_guardada", args=[self.contact.id, new.id]))

    def test_save_it_again_anyway_without_georeferencing(self):
        self.client.post(self.url, self.data(guardar_igual="save_needs_georef"))
        new = Address.objects.filter(contact=self.contact).exclude(pk=self.address.pk).get()
        self.assertTrue(new.needs_georef)

    def test_an_unknown_action_saves_nothing(self):
        response = self.client.post(self.url, self.data(guardar_igual="delete"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Address.objects.filter(contact=self.contact).count(), 1)

    def test_another_apartment_is_saved_right_away(self):
        response = self.client.post(self.url, self.data(save="1", address_2="Apto 3"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Address.objects.filter(contact=self.contact).count(), 2)

    def test_the_saved_page_for_the_existing_one(self):
        response = self.client.get(
            reverse("direccion_guardada", args=[self.contact.id, self.address.id]) + "?ya_existia=1"
        )
        self.assertContains(response, "announceNewAddress(%d, %d, true)" % (self.contact.id, self.address.id))

    def test_the_address_lists_show_the_second_line(self):
        response = self.client.post(
            reverse("api_get_addresses", args=[self.contact.id]), HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.json(), [{"value": self.address.id, "text": "Havre 1910, Apto 2, Montevideo"}])


class TestScheduledAddressChangeToARepeatedAddress(TestCase):
    def setUp(self):
        User.objects.create_superuser(username="agent", password="x")
        self.client.login(username="agent", password="x")
        self.contact = create_contact(name="Moving", phone="099222114")
        self.state = State.objects.create(name="Montevideo")
        self.address = Address.objects.create(
            contact=self.contact, address_1="Havre 1910", address_2="Apto 2", city="Montevideo", state=self.state
        )

    def test_uses_the_address_the_contact_has(self):
        activity_type = NewAddressChangeScheduledTaskForm().fields["activity_type"].choices[0][0]
        response = self.client.post(
            reverse("new_scheduled_task_address_change", args=[self.contact.id]),
            {
                "date_1": "2030-01-01",
                "new_address": "on",
                "new_address_1": "HAVRE 1910",
                "new_address_2": "Apto 2",
                "new_address_city": "Montevideo",
                "new_address_state": self.state.id,
                "activity_type": activity_type,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Address.objects.filter(contact=self.contact).count(), 1)
        self.assertEqual(ScheduledTask.objects.get(contact=self.contact).address, self.address)
