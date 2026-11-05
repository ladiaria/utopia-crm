# coding=utf-8
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core.models import Subscription

from tests.factory import create_address, create_contact, create_subscription


class TestSubscriptionAdminAdd(TestCase):
    """
    Subscriptions are created from the contact. The add page of the admin skipped that flow and built a dropdown with
    every address in the database, so nobody can use it, superusers included.
    """

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser("admin", "admin@example.com", "password")
        cls.contact = create_contact("Contact", "29000808", "contact@example.com")
        cls.other_contact = create_contact("Other", "29000809", "other@example.com")
        cls.address = create_address("Own address 123", cls.contact)
        cls.other_address = create_address("Other address 456", cls.other_contact)
        cls.subscription = create_subscription(cls.contact)

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_superuser_cannot_open_the_add_page(self):
        response = self.client.get(reverse("admin:core_subscription_add"))

        self.assertEqual(response.status_code, 403)

    def test_superuser_cannot_post_to_the_add_page(self):
        response = self.client.post(reverse("admin:core_subscription_add"), {"contact": self.contact.id})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Subscription.objects.count(), 1)

    def test_the_list_has_no_add_button(self):
        response = self.client.get(reverse("admin:core_subscription_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("admin:core_subscription_add"))

    def test_the_change_page_only_lists_the_addresses_of_the_contact(self):
        response = self.client.get(reverse("admin:core_subscription_change", args=[self.subscription.id]))

        self.assertEqual(response.status_code, 200)
        billing_address = response.context["adminform"].form.fields["billing_address"]
        self.assertEqual(list(billing_address.queryset), [self.address])

    def test_the_form_without_a_subscription_lists_no_addresses(self):
        request = RequestFactory().get("/")
        request.user = self.superuser
        form_class = admin.site._registry[Subscription].get_form(request)

        self.assertFalse(form_class().fields["billing_address"].queryset.exists())
