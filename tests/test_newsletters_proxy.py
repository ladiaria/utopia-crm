# coding=utf-8
"""
Tests for the CRM proxy views that read/edit a contact's newsletters on demand against the CMS. The CMS
call (cms_rest_api_request) is mocked, so these are pure unit tests of the proxy + partials.
"""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from tests.factories.core_factories import ContactFactory

HX = {"HTTP_HX_REQUEST": "true"}

SAMPLE_READ = {
    "exists": True,
    "publication": [
        {"slug": "semanal", "name": "La semanal", "subscribed": True},
        {"slug": "tarde", "name": "La tarde", "subscribed": False},
    ],
    "category": [
        {"slug": "salto", "name": "Salto", "subscribed": True},
    ],
}


class NewslettersProxyTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(username="staff", password="testpass")
        self.client.login(username="staff", password="testpass")
        self.contact = ContactFactory()

    # --- overview ---

    @patch("support.views.newsletters.cms_rest_api_request", return_value=SAMPLE_READ)
    def test_overview_shows_only_subscribed(self, _mock):
        url = reverse("contact_newsletters_overview", args=[self.contact.id])
        resp = self.client.get(url, **HX)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn("La semanal", content)   # subscribed publication
        self.assertIn("Salto", content)        # subscribed category
        self.assertNotIn("La tarde", content)  # not subscribed -> hidden

    @patch("support.views.newsletters.cms_rest_api_request", return_value="ERROR")
    def test_overview_cms_error_shows_warning(self, _mock):
        url = reverse("contact_newsletters_overview", args=[self.contact.id])
        resp = self.client.get(url, **HX)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("No se pudieron cargar las newsletters", resp.content.decode())

    @patch("support.views.newsletters.cms_rest_api_request", return_value={"exists": False})
    def test_overview_no_web_account(self, _mock):
        url = reverse("contact_newsletters_overview", args=[self.contact.id])
        resp = self.client.get(url, **HX)
        self.assertIn("todavía no existe en la web", resp.content.decode())

    def test_overview_requires_htmx_header(self):
        url = reverse("contact_newsletters_overview", args=[self.contact.id])
        self.assertEqual(self.client.get(url).status_code, 404)

    # --- form ---

    @patch("support.views.newsletters.cms_rest_api_request", return_value=SAMPLE_READ)
    def test_form_renders_checkboxes_with_state(self, _mock):
        url = reverse("contact_newsletters_form", args=[self.contact.id])
        resp = self.client.get(url, **HX)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        # both types rendered, including not-subscribed ones (editable)
        self.assertIn("La tarde", content)
        self.assertIn('id="nl-publication-semanal"', content)
        self.assertIn('id="nl-category-salto"', content)

    # --- toggle ---

    @patch("support.views.newsletters.cms_rest_api_request")
    def test_toggle_subscribe_calls_cms_with_delta(self, mock_req):
        mock_req.return_value = {"exists": True, "subscribed": True}
        url = reverse("contact_newsletter_toggle", args=[self.contact.id])
        resp = self.client.post(
            url,
            {"nl_type": "publication", "slug": "tarde", "name": "La tarde", "subscribed": "on"},
            **HX,
        )
        self.assertEqual(resp.status_code, 200)
        # the CMS delta was called with subscribe
        _args, kwargs = mock_req.call_args
        sent = _args[2]
        self.assertEqual(sent["action"], "subscribe")
        self.assertEqual(sent["nl_type"], "publication")
        self.assertEqual(sent["slug"], "tarde")
        self.assertIn("checked", resp.content.decode())

    @patch("support.views.newsletters.cms_rest_api_request")
    def test_toggle_unsubscribe_when_checkbox_absent(self, mock_req):
        mock_req.return_value = {"exists": True, "subscribed": False}
        url = reverse("contact_newsletter_toggle", args=[self.contact.id])
        resp = self.client.post(
            url,
            {"nl_type": "category", "slug": "salto", "name": "Salto"},  # no "subscribed" -> unchecked
            **HX,
        )
        _args, _kwargs = mock_req.call_args
        self.assertEqual(_args[2]["action"], "unsubscribe")
        self.assertNotIn("checked", resp.content.decode())

    @patch("support.views.newsletters.cms_rest_api_request", return_value="ERROR")
    def test_toggle_cms_error_shows_error_and_reverts(self, _mock):
        url = reverse("contact_newsletter_toggle", args=[self.contact.id])
        resp = self.client.post(
            url,
            {"nl_type": "publication", "slug": "tarde", "name": "La tarde", "subscribed": "on"},
            **HX,
        )
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn("No se guardó", content)
        # tried to subscribe but failed -> rendered unchecked (reverted)
        self.assertNotIn("checked", content)
