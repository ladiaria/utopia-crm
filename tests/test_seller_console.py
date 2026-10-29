# coding=utf-8
from django.contrib.auth.models import User
from django.contrib.messages import WARNING, get_messages
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from datetime import datetime, time, timedelta
from io import StringIO
from unittest.mock import patch

from core.models import Activity, Campaign, ContactCampaignStatus
from core.choices import CAMPAIGN_STATUS, get_contacted_q
from support.models import Seller, SellerConsoleAction, Shift
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


class TestSellerConsoleContactRemovedFromCampaign(TestCase):
    """
    Verifica el comportamiento cuando el contacto ya no está en la campaña pero sobrevive una actividad
    pendiente apuntando a ella.

    Regresión t1176: sacar un contacto de una campaña borra el ContactCampaignStatus pero no las
    actividades, que apuntan directo a la campaña. La pendiente seguía apareciendo en la cola "act" y, al
    resolverla, la consola la marcaba como completada antes de verificar el estado de campaña: el vendedor
    veía el error y la actividad quedaba cerrada igual.
    """

    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_superuser(username="vendedor", password="testpass")
        self.seller = Seller.objects.create(name="Vendedor", user=self.user, internal=True)
        self.client.login(username="vendedor", password="testpass")

        self.contact = ContactFactory()
        self.campaign = Campaign.objects.create(name="Campaña test", active=True, priority=3)

        self.call_later = SellerConsoleAction.objects.create(
            slug="call-later",
            name="Llamar más tarde",
            action_type=SellerConsoleAction.ACTION_TYPES.CALL_LATER,
            campaign_status=CAMPAIGN_STATUS.CALLED_COULD_NOT_CONTACT,
            campaign_resolution="CL",
            is_active=True,
        )

        # La actividad pendiente que quedó huérfana: el contacto ya no tiene ContactCampaignStatus.
        self.activity = Activity.objects.create(
            contact=self.contact,
            campaign=self.campaign,
            seller=self.seller,
            activity_type="C",
            status="P",
            datetime=timezone.now() - timedelta(days=1),
        )

    def test_orphan_activity_is_not_completed(self):
        """Resolver una actividad de un contacto que ya no está en la campaña no debe cerrarla."""
        self.client.post(
            reverse("seller_console", args=["act", self.campaign.id]),
            data={
                "result": "call-later",
                "category": "act",
                "instance_id": self.activity.id,
                "seller_id": self.seller.id,
                "offset": 1,
                "notes": "No contesta",
            },
        )

        self.activity.refresh_from_db()
        self.assertEqual(self.activity.status, "P")
        # Tampoco debe haberse creado una pendiente nueva para una campaña de la que ya salió.
        self.assertEqual(Activity.objects.filter(contact=self.contact, campaign=self.campaign).count(), 1)

    def test_orphan_activity_is_not_listed_in_console(self):
        """La cola de la consola no debe ofrecer actividades de contactos que ya salieron de la campaña."""
        # Con la única actividad huérfana, la cola queda vacía y la consola manda de vuelta a la lista.
        response = self.client.get(reverse("seller_console", args=["act", self.campaign.id]))
        self.assertRedirects(
            response, reverse("seller_console_list_campaigns"), fetch_redirect_response=False
        )

        ContactCampaignStatus.objects.create(
            contact=self.contact, campaign=self.campaign, status=1, seller=self.seller
        )
        response = self.client.get(reverse("seller_console", args=["act", self.campaign.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.contact.get_full_name())

    def test_activity_is_listed_again_when_contact_is_back_in_campaign(self):
        """Con el ContactCampaignStatus en su lugar, la misma actividad sí se puede trabajar."""
        ContactCampaignStatus.objects.create(
            contact=self.contact, campaign=self.campaign, status=1, seller=self.seller
        )

        self.client.post(
            reverse("seller_console", args=["act", self.campaign.id]),
            data={
                "result": "call-later",
                "category": "act",
                "instance_id": self.activity.id,
                "seller_id": self.seller.id,
                "offset": 1,
                "notes": "No contesta",
            },
        )

        self.activity.refresh_from_db()
        self.assertEqual(self.activity.status, "C")


class FixedDatetime(datetime):
    """datetime cuyo now() devuelve la hora que fija el test, para ubicar la consola en un turno."""

    fixed = None

    @classmethod
    def now(cls, tz=None):
        return cls.fixed


def at(hour, minute=0, second=0):
    """Fija la hora de la consola para el bloque with."""
    FixedDatetime.fixed = datetime(2026, 10, 29, hour, minute, second)
    return patch("support.views.seller_console.datetime", FixedDatetime)


def create_shifts(morning_end=time(14, 59, 59)):
    """Los dos turnos de producción: Matutino y Vespertino."""
    Shift.objects.create(name="Matutino", start_time=time(9, 0), end_time=morning_end)
    Shift.objects.create(name="Vespertino", start_time=time(15, 0), end_time=time(21, 0))


class TestShiftSwitchStatus(TestCase):
    """Shift.switch_status_at: a qué turno se pasa un contacto según la hora (#72 de utopia-crm-ladiaria)."""

    def status_at(self, hour, minute=0, second=0):
        return Shift.switch_status_at(datetime(2026, 10, 29, hour, minute, second))

    def test_morning_moves_to_afternoon_and_afternoon_to_morning(self):
        create_shifts()
        self.assertEqual(self.status_at(9, 0), CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON)
        self.assertEqual(self.status_at(14, 59, 59), CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON)
        self.assertEqual(self.status_at(15, 0), CAMPAIGN_STATUS.SWITCH_TO_MORNING)
        self.assertEqual(self.status_at(21, 0, 30), CAMPAIGN_STATUS.SWITCH_TO_MORNING)

    def test_no_gap_when_the_end_has_no_seconds(self):
        """Con el fin cargado como 14:59, 14:59:30 sigue siendo el turno de la mañana."""
        create_shifts(morning_end=time(14, 59))
        self.assertEqual(self.status_at(14, 59, 30), CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON)

    def test_outside_the_shifts(self):
        create_shifts()
        self.assertIsNone(self.status_at(8, 59))
        self.assertIsNone(self.status_at(21, 1))

    def test_needs_exactly_two_shifts(self):
        self.assertIsNone(self.status_at(10, 0))
        Shift.objects.create(name="Matutino", start_time=time(9, 0), end_time=time(14, 59, 59))
        self.assertIsNone(self.status_at(10, 0))


class TestFirstNotFoundSwitchesShift(TestCase):
    """
    El primer «No encontrado» de un contacto en una campaña lo pasa al otro turno según la hora, y durante un turno
    sólo se ofrece pasar al otro (#72 de utopia-crm-ladiaria). La llamada queda registrada como «No encontrado»:
    es lo que cuenta el WhatsApp del call center para habilitar el botón (#45).
    """

    @classmethod
    def setUpTestData(cls):
        # Las acciones reales de la consola, las mismas que carga producción
        call_command("populate_seller_console_actions", stdout=StringIO())
        create_shifts()

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(username="vendedor", password="testpass")
        self.seller = Seller.objects.create(name="Vendedor", user=self.user, internal=True)
        self.client.login(username="vendedor", password="testpass")

        self.contact = ContactFactory()
        self.campaign = Campaign.objects.create(name="Campaña test", active=True, priority=3)
        self.ccs = ContactCampaignStatus.objects.create(
            contact=self.contact, campaign=self.campaign, status=1, seller=self.seller
        )

    def post(self, result, category="new", instance_id=None):
        return self.client.post(
            reverse("seller_console", args=[category, self.campaign.id]),
            data={
                "result": result,
                "category": category,
                "instance_id": instance_id or self.ccs.id,
                "seller_id": self.seller.id,
                "offset": 1,
                "notes": "",
            },
        )

    def unanswered_calls(self):
        """Lo que cuenta el WhatsApp del call center (llamadas_sin_respuesta en utopia-crm-ladiaria)."""
        return Activity.objects.filter(
            contact=self.contact,
            campaign=self.campaign,
            activity_type="C",
            status="C",
            seller_console_action__action_type=SellerConsoleAction.ACTION_TYPES.NOT_FOUND,
        ).count()

    def assert_redirects_to_offset(self, response, category, offset):
        url = reverse("seller_console", args=[category, self.campaign.id])
        self.assertRedirects(response, f"{url}?offset={offset}", fetch_redirect_response=False)

    def test_first_not_found_in_the_morning_moves_to_the_afternoon(self):
        with at(10, 0):
            response = self.post("not-found")

        self.ccs.refresh_from_db()
        self.assertEqual(self.ccs.status, CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON)
        self.assertIsNone(self.ccs.seller)
        self.assertEqual(self.ccs.last_console_action_id, "not-found")
        self.assertEqual(self.unanswered_calls(), 1)
        # El contacto sale de la lista: el siguiente ya está en el mismo offset
        self.assert_redirects_to_offset(response, "new", 1)
        warning = [m for m in get_messages(response.wsgi_request) if m.level == WARNING]
        self.assertEqual(len(warning), 1)
        self.assertIn("moved to the afternoon shift", str(warning[0]))

    def test_first_not_found_in_the_afternoon_moves_to_the_morning(self):
        with at(16, 0):
            response = self.post("not-found")

        self.ccs.refresh_from_db()
        self.assertEqual(self.ccs.status, CAMPAIGN_STATUS.SWITCH_TO_MORNING)
        self.assertIsNone(self.ccs.seller)
        self.assertEqual(self.unanswered_calls(), 1)
        warning = [m for m in get_messages(response.wsgi_request) if m.level == WARNING]
        self.assertIn("moved to the morning shift", str(warning[0]))

    def assert_usual_not_found(self, response):
        self.ccs.refresh_from_db()
        self.assertEqual(self.ccs.status, CAMPAIGN_STATUS.CALLED_COULD_NOT_CONTACT)
        self.assertEqual(self.ccs.seller, self.seller)
        self.assert_redirects_to_offset(response, "new", 2)
        self.assertFalse([m for m in get_messages(response.wsgi_request) if m.level == WARNING])

    def test_second_not_found_behaves_as_usual(self):
        """Ya hubo un «No encontrado» (por ejemplo, del otro turno): este no vuelve a cambiar de turno."""
        Activity.objects.create(
            contact=self.contact,
            campaign=self.campaign,
            activity_type="C",
            status="C",
            datetime=datetime(2026, 10, 28, 10, 0),
            seller_console_action_id="not-found",
        )
        with at(16, 0):
            response = self.post("not-found")

        self.assert_usual_not_found(response)
        self.assertEqual(self.unanswered_calls(), 2)

    def test_not_found_outside_the_shifts_behaves_as_usual(self):
        with at(22, 0):
            response = self.post("not-found")

        self.assert_usual_not_found(response)
        self.assertEqual(self.unanswered_calls(), 1)

    @override_settings(SELLER_CONSOLE_FIRST_NOT_FOUND_SWITCHES_SHIFT=False)
    def test_switch_turned_off(self):
        with at(10, 0):
            response = self.post("not-found")

        self.assert_usual_not_found(response)

    def test_first_not_found_from_the_activities_queue(self):
        """En la cola «act» no se crea la pendiente nueva: el contacto se va al otro turno."""
        activity = Activity.objects.create(
            contact=self.contact,
            campaign=self.campaign,
            seller=self.seller,
            activity_type="C",
            status="P",
            datetime=datetime(2026, 10, 29, 9, 0),
        )
        with at(10, 0):
            response = self.post("not-found", category="act", instance_id=activity.id)

        activity.refresh_from_db()
        self.assertEqual(activity.status, "C")
        self.assertEqual(activity.seller_console_action_id, "not-found")
        self.assertFalse(Activity.objects.filter(contact=self.contact, status="P").exists())
        self.ccs.refresh_from_db()
        self.assertEqual(self.ccs.status, CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON)
        self.assertEqual(self.unanswered_calls(), 1)
        self.assert_redirects_to_offset(response, "act", 1)

    def test_only_the_move_to_the_other_shift_is_shown(self):
        url = reverse("seller_console", args=["new", self.campaign.id])
        with at(10, 0):
            response = self.client.get(url)
        self.assertContains(response, 'data-result="move-afternoon"')
        self.assertNotContains(response, 'data-result="move-morning"')

        with at(16, 0):
            response = self.client.get(url)
        self.assertContains(response, 'data-result="move-morning"')
        self.assertNotContains(response, 'data-result="move-afternoon"')

        with at(22, 0):
            response = self.client.get(url)
        self.assertContains(response, 'data-result="move-morning"')
        self.assertContains(response, 'data-result="move-afternoon"')

    def test_move_to_the_current_shift_is_rejected(self):
        with at(10, 0):
            self.post("move-morning")
        self.ccs.refresh_from_db()
        self.assertEqual(self.ccs.status, 1)
        self.assertEqual(self.ccs.seller, self.seller)
        self.assertFalse(Activity.objects.filter(contact=self.contact).exists())

        with at(10, 0):
            self.post("move-afternoon")
        self.ccs.refresh_from_db()
        self.assertEqual(self.ccs.status, CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON)


class TestContactedExcludesNotFoundShiftSwitch(TestCase):
    """Un contacto que pasó de turno por su primer «No encontrado» no cuenta como contactado (#72)."""

    @classmethod
    def setUpTestData(cls):
        call_command("populate_seller_console_actions", stdout=StringIO())

    def test_contacted_q(self):
        campaign = Campaign.objects.create(name="Campaña test", active=True, priority=3)
        rows = {
            "not_found_switch": (CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON, "not-found"),
            "moved_by_hand": (CAMPAIGN_STATUS.SWITCH_TO_MORNING, "move-morning"),
            "contacted_without_action": (CAMPAIGN_STATUS.CONTACTED, None),
            "not_found_not_switched": (CAMPAIGN_STATUS.CALLED_COULD_NOT_CONTACT, "not-found"),
        }
        ids = {}
        for name, (status, action) in rows.items():
            ids[name] = ContactCampaignStatus.objects.create(
                contact=ContactFactory(), campaign=campaign, status=status, last_console_action_id=action
            ).id

        contacted = set(ContactCampaignStatus.objects.filter(get_contacted_q()).values_list("id", flat=True))
        self.assertEqual(contacted, {ids["moved_by_hand"], ids["contacted_without_action"]})
