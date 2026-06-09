# coding=utf-8
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Activity, Campaign, ContactCampaignStatus
from core.choices import CAMPAIGN_STATUS
from support.models import Seller, SellerConsoleAction
from tests.factories.core_factories import ContactFactory


class TestSellerConsoleRegistersActivity(TestCase):
    """
    Verifica que al resolver un contacto desde la consola de vendedores en la categoría "new"
    siempre se cree una actividad, incluso para acciones terminales (DECLINED) y con notas vacías.

    Regresión: antes "No interesado" (action_type DECLINED) hacía un early-return en
    register_new_activity y no quedaba ningún registro de actividad para el contacto.
    """

    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_superuser(username="vendedor", password="testpass")
        self.seller = Seller.objects.create(name="Vendedor", user=self.user, internal=True)
        self.client.login(username="vendedor", password="testpass")

        self.contact = ContactFactory()
        self.campaign = Campaign.objects.create(name="Campaña test", active=True, priority=3)

        # Contacto no contactado (status=1) asignado al vendedor → entra en la cola "new".
        self.ccs = ContactCampaignStatus.objects.create(
            contact=self.contact,
            campaign=self.campaign,
            status=1,
            seller=self.seller,
        )

        self.not_interested = SellerConsoleAction.objects.create(
            slug="not-interested",
            name="No interesado",
            action_type=SellerConsoleAction.ACTION_TYPES.DECLINED,
            campaign_status=CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
            campaign_resolution="NI",
            is_active=True,
        )

    def _post_result(self, result, notes=""):
        return self.client.post(
            reverse("seller_console", args=["new", self.campaign.id]),
            data={
                "result": result,
                "category": "new",
                "instance_id": self.ccs.id,
                "seller_id": self.seller.id,
                "offset": 1,
                "notes": notes,
            },
        )

    def test_declined_action_creates_completed_activity(self):
        """'No interesado' (DECLINED) debe crear una actividad completada para el contacto."""
        self._post_result("not-interested", notes="No le interesa")

        activities = Activity.objects.filter(contact=self.contact, campaign=self.campaign)
        self.assertEqual(activities.count(), 1)
        activity = activities.first()
        self.assertEqual(activity.status, "C")
        self.assertEqual(activity.activity_type, "C")
        self.assertEqual(activity.seller_console_action, self.not_interested)
        self.assertEqual(activity.notes, "No le interesa")

    def test_declined_action_with_empty_notes_still_creates_activity(self):
        """Aunque las notas estén vacías, igual debe crearse la actividad (con notas vacías)."""
        self._post_result("not-interested", notes="")

        activities = Activity.objects.filter(contact=self.contact, campaign=self.campaign)
        self.assertEqual(activities.count(), 1)
        self.assertEqual(activities.first().notes, "")

    def test_ccs_status_and_resolution_updated(self):
        """El ContactCampaignStatus debe quedar con el estado y la resolución de la acción."""
        self._post_result("not-interested", notes="")

        self.ccs.refresh_from_db()
        self.assertEqual(self.ccs.status, CAMPAIGN_STATUS.ENDED_WITH_CONTACT)
        self.assertEqual(self.ccs.campaign_resolution, "NI")
        self.assertEqual(self.ccs.last_console_action, self.not_interested)


class TestSellerConsoleScheduledActivity(TestCase):
    """
    Verifica que al agendar (action_type SCHEDULED) la actividad pendiente futura quede con la
    acción de consola 'Agendar', no sin acción.

    Regresión: create_scheduled_activity creaba la pendiente sin seller_console_action, así que
    la llamada agendada no mostraba "Agendar" en las actividades.
    """

    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_superuser(username="vendedor", password="testpass")
        self.seller = Seller.objects.create(name="Vendedor", user=self.user, internal=True)
        self.client.login(username="vendedor", password="testpass")

        self.contact = ContactFactory()
        self.campaign = Campaign.objects.create(name="Campaña test", active=True, priority=3)

        self.ccs = ContactCampaignStatus.objects.create(
            contact=self.contact,
            campaign=self.campaign,
            status=1,
            seller=self.seller,
        )

        self.schedule = SellerConsoleAction.objects.create(
            slug="schedule",
            name="Agendar",
            action_type=SellerConsoleAction.ACTION_TYPES.SCHEDULED,
            campaign_status=CAMPAIGN_STATUS.CONTACTED,
            campaign_resolution="SC",
            is_active=True,
        )

    def test_scheduled_pending_activity_has_console_action(self):
        """La actividad pendiente agendada debe llevar seller_console_action='schedule'."""
        self.client.post(
            reverse("seller_console", args=["new", self.campaign.id]),
            data={
                "result": "schedule",
                "category": "new",
                "instance_id": self.ccs.id,
                "seller_id": self.seller.id,
                "offset": 1,
                "notes": "",
                "call_date": "2026-07-01",
                "call_time": "10:30",
            },
        )

        pending = Activity.objects.filter(
            contact=self.contact, campaign=self.campaign, status="P"
        )
        self.assertEqual(pending.count(), 1)
        self.assertEqual(pending.first().seller_console_action, self.schedule)
