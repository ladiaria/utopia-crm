"""
Tests for the Activities tab of the contact detail: the timeline is loaded by htmx a page at a time, and the search box
filters it on the server.
"""

from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Activity
from support.views.contacts import CONTACT_ACTIVITIES_PAGE_SIZE
from tests.factories.core_factories import ContactFactory
from tests.factory import create_campaign

HX = {"HTTP_HX_REQUEST": "true"}


class ContactActivitiesHtmxTestCase(TestCase):
    # The activities and their notes are made up on purpose: each test needs a note it can search for.
    def setUp(self):
        User.objects.create_superuser(username="staff", password="testpass")
        self.client.login(username="staff", password="testpass")
        self.contact = ContactFactory()
        self.url = reverse("contact_activities_htmx", args=[self.contact.id])

    def create_activity(self, notes, when, **kwargs):
        return Activity.objects.create(
            contact=self.contact, activity_type="W", direction="I", status="C", datetime=when, notes=notes, **kwargs
        )

    def test_requires_htmx(self):
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_no_activities(self):
        response = self.client.get(self.url, **HX)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This contact has no activities")

    def test_notes_are_shown(self):
        self.create_activity("WhatsApp saliente\n\nTexto enviado:\nHola", datetime(2026, 10, 28, 17, 51))
        response = self.client.get(self.url, **HX)
        self.assertContains(response, "WhatsApp saliente\n\nTexto enviado:\nHola")
        self.assertContains(response, "17:51")

    def test_search_filters_notes_and_highlights_the_match(self):
        self.create_activity("Recibió bien la newsletter", datetime(2026, 10, 28, 10, 0))
        self.create_activity("No contesta", datetime(2026, 10, 28, 11, 0))
        response = self.client.get(self.url, {"q": "BIEN"}, **HX)
        self.assertContains(response, "Recibió <mark>bien</mark> la newsletter", html=False)
        self.assertNotContains(response, "No contesta")

    def test_search_by_campaign(self):
        campaign = create_campaign("Prueba WhatsApp call center")
        self.create_activity("Con campaña", datetime(2026, 10, 28, 10, 0), campaign=campaign)
        self.create_activity("Sin campaña", datetime(2026, 10, 28, 11, 0))
        response = self.client.get(self.url, {"q": "call center"}, **HX)
        self.assertContains(response, "Con campaña")
        self.assertNotContains(response, "Sin campaña")

    def test_search_without_results(self):
        self.create_activity("No contesta", datetime(2026, 10, 28, 11, 0))
        response = self.client.get(self.url, {"q": "newsletter"}, **HX)
        self.assertContains(response, 'No activities match "newsletter".')

    def test_highlight_escapes_the_notes(self):
        self.create_activity("<b>bien</b> & listo", datetime(2026, 10, 28, 10, 0))
        response = self.client.get(self.url, {"q": "b"}, **HX)
        self.assertContains(response, "&lt;<mark>b</mark>&gt;<mark>b</mark>ien&lt;/<mark>b</mark>&gt; &amp; listo")

    def test_pagination_does_not_repeat_the_day_label(self):
        # One more than a page, all on the same day: the second page continues the day, it doesn't start it again
        start = datetime(2026, 10, 28, 8, 0)
        for minute in range(CONTACT_ACTIVITIES_PAGE_SIZE + 1):
            self.create_activity(f"Nota {minute}", start + timedelta(minutes=minute))

        first = self.client.get(self.url, **HX)
        self.assertContains(first, 'class="time-label"', count=1)
        self.assertContains(first, "Load more")
        self.assertEqual(first.context["last_day"], "2026-10-28")

        second = self.client.get(self.url, {"page": 2, "last_day": "2026-10-28"}, **HX)
        self.assertContains(second, "Nota 0")
        self.assertNotContains(second, 'class="time-label"')
        self.assertNotContains(second, "Load more")

    def test_activities_without_date_go_last(self):
        self.create_activity("Sin fecha cargada", None)
        self.create_activity("Con fecha", datetime(2026, 10, 28, 10, 0))
        content = self.client.get(self.url, **HX).content.decode()
        self.assertLess(content.index("Con fecha"), content.index("Sin fecha cargada"))
