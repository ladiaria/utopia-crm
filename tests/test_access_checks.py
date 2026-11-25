# coding=utf-8
"""
Access checks that used to say one thing and do another (it/utopia-crm-ladiaria#183, #184).

- Exporting the contact list: the button was only shown to Managers, but the view exported for any staff user.
- Editing a contact's campaign status asked for an "Admin" group that does not exist, so Admins could not do it.
- The campaign management menu showed Managers links to Admins-only tools.
"""
from django.contrib.auth.models import Group, Permission, User
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

from support.views.contacts import user_can_edit_campaign_status, user_can_export_contacts

from tests.factory import create_contact


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
