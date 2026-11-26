# coding=utf-8
"""
Access checks that used to say one thing and do another (it/utopia-crm-ladiaria#183, #184).

- Exporting the contact list: the button was only shown to Managers, but the view exported for any staff user.
- Editing a contact's campaign status asked for an "Admin" group that does not exist, so Admins could not do it.
- The campaign management menu showed Managers links to Admins-only tools.

Class-based views that checked nothing (it/utopia-crm-ladiaria#185):

- The free subscription views defined test_func without UserPassesTestMixin, so nothing called it.
- The corporate subscription and subscription update views had no check at all.
- The API log entry endpoint took POSTs without an API key.
"""
from django.contrib.auth.models import AnonymousUser, Group, Permission, User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse
from rest_framework.test import APIRequestFactory

from core.serializers import ApiLogEntryViewSet
from support.views.contacts import user_can_edit_campaign_status, user_can_export_contacts
from support.views.subscriptions import (
    CorporateSubscriptionCreateView,
    CreateFreeSubscriptionView,
    SubscriptionUpdateView,
    UpdateFreeSubscriptionView,
)

from tests.factory import create_contact, create_subscription


def staff_user(username, group=None):
    user = User.objects.create_user(username, f"{username}@example.com", "x", is_staff=True)
    if group:
        user.groups.add(Group.objects.get_or_create(name=group)[0])
    return user


class TestContactListExport(TestCase):
    def setUp(self):
        create_contact(name="Exported", phone="099111222")
        self.url = reverse("contact_list") + "?export=1"

    def test_managers_can_export(self):
        self.client.force_login(staff_user("manager", "Managers"))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])

    def test_staff_without_managers_cannot_export_with_a_link(self):
        self.client.force_login(staff_user("operator", "Support"))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_the_permission_lets_another_group_export(self):
        user = staff_user("gdc_admin", "Administradores GDC")
        user.user_permissions.add(Permission.objects.get(codename="can_export_contacts"))
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_admins_and_superusers_can_export(self):
        self.assertTrue(user_can_export_contacts(staff_user("admin", "Admins")))
        self.assertTrue(user_can_export_contacts(User.objects.create_superuser("super", "s@example.com", "x")))

    def test_the_list_without_export_is_still_open_to_staff(self):
        self.client.force_login(staff_user("operator2", "Support"))
        self.assertEqual(self.client.get(reverse("contact_list")).status_code, 200)


class TestEditCampaignStatus(TestCase):
    def test_admins_can_edit_the_campaign_status(self):
        self.assertTrue(user_can_edit_campaign_status(staff_user("admin", "Admins")))

    def test_managers_can_edit_the_campaign_status(self):
        self.assertTrue(user_can_edit_campaign_status(staff_user("manager", "Managers")))

    def test_support_cannot(self):
        self.assertFalse(user_can_edit_campaign_status(staff_user("operator", "Support")))


class TestCampaignManagementSidebar(TestCase):
    def render(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return render_to_string("components/sidebar_items/_campaign_management.html", request=request)

    def test_managers_do_not_see_the_admins_only_tools(self):
        html = self.render(staff_user("manager", "Managers"))
        self.assertNotIn(reverse("upload_do_not_call_numbers"), html)
        self.assertNotIn(reverse("bulk_delete_campaign_status"), html)

    def test_the_permission_shows_the_do_not_call_upload(self):
        user = staff_user("gdc_admin", "Managers")
        user.user_permissions.add(Permission.objects.get(codename="can_upload_do_not_call_numbers"))
        html = self.render(user)
        self.assertIn(reverse("upload_do_not_call_numbers"), html)
        self.assertNotIn(reverse("bulk_delete_campaign_status"), html)

    def test_admins_see_both(self):
        html = self.render(staff_user("admin", "Admins"))
        self.assertIn(reverse("upload_do_not_call_numbers"), html)
        self.assertIn(reverse("bulk_delete_campaign_status"), html)


class TestSubscriptionClassBasedViews(TestCase):
    """
    The views are called directly, not through their URL: a deployment can override those URLs with its own views
    (URLS_CUSTOM_MODULE), and these tests are about the base ones.
    """

    @classmethod
    def setUpTestData(cls):
        cls.contact = create_contact(name="Subscriber", phone="099333444")
        cls.subscription = create_subscription(cls.contact)
        cls.free_subscription = create_subscription(cls.contact, subscription_type="F")

    def call(self, view, user, **kwargs):
        request = RequestFactory().get("/")
        request.user = user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        try:
            return view.as_view()(request, **kwargs)
        except PermissionDenied:
            # Django's handler turns it into a 403 when the view runs through a real request.
            return HttpResponseForbidden()

    def user_with_perm(self, username, codename):
        user = staff_user(username)
        user.user_permissions.add(Permission.objects.get(codename=codename))
        return User.objects.get(pk=user.pk)

    def test_anonymous_users_are_sent_to_login(self):
        cases = [
            (CreateFreeSubscriptionView, {"contact_id": self.contact.id}),
            (UpdateFreeSubscriptionView, {"subscription_id": self.free_subscription.id}),
            (CorporateSubscriptionCreateView, {"contact_id": self.contact.id}),
            (SubscriptionUpdateView, {"contact_id": self.contact.id, "subscription_id": self.subscription.id}),
        ]
        for view, kwargs in cases:
            with self.subTest(view=view.__name__):
                response = self.call(view, AnonymousUser(), **kwargs)
                self.assertEqual(response.status_code, 302)
                self.assertIn("login", response.url)

    def test_free_subscriptions_need_the_permission(self):
        operator = staff_user("operator")
        kwargs = {"contact_id": self.contact.id}
        self.assertEqual(self.call(CreateFreeSubscriptionView, operator, **kwargs).status_code, 403)
        update_kwargs = {"subscription_id": self.free_subscription.id}
        self.assertEqual(self.call(UpdateFreeSubscriptionView, operator, **update_kwargs).status_code, 403)
        allowed = self.user_with_perm("free_subs", "can_add_free_subscription")
        self.assertEqual(self.call(CreateFreeSubscriptionView, allowed, **kwargs).status_code, 200)

    def test_corporate_subscriptions_need_the_permission(self):
        kwargs = {"contact_id": self.contact.id}
        self.assertEqual(self.call(CorporateSubscriptionCreateView, staff_user("operator"), **kwargs).status_code, 403)
        allowed = self.user_with_perm("corporate", "can_add_corporate_subscription")
        self.assertNotEqual(self.call(CorporateSubscriptionCreateView, allowed, **kwargs).status_code, 403)

    def test_editing_a_subscription_needs_staff(self):
        not_staff = User.objects.create_user("not_staff", "ns@example.com", "x")
        kwargs = {"contact_id": self.contact.id, "subscription_id": self.subscription.id}
        self.assertEqual(self.call(SubscriptionUpdateView, not_staff, **kwargs).status_code, 403)


class TestApiLogEntry(TestCase):
    def test_a_post_without_api_key_is_rejected(self):
        request = APIRequestFactory().post("/api/api-log-entry/", {}, format="json")
        response = ApiLogEntryViewSet.as_view({"post": "create"})(request)
        self.assertIn(response.status_code, (401, 403))
