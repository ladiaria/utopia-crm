# coding=utf-8
import os
import tempfile
from datetime import date, datetime
from io import StringIO

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.choices import CAMPAIGN_STATUS, get_contacted_statuses
from core.models import Activity, Campaign, ContactCampaignStatus
from support.models import Seller, SellerConsoleAction
from tests.factories.core_factories import ContactFactory


CUTOFF = "2026-05-31"


class CloseLostScheduleTestMixin:
    """
    Helpers compartidos: crea la acción de consola con el populate (así también se verifica que
    'close-lost-schedule' sobrevive a ese comando) y arma pares agenda + estado de campaña.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("populate_seller_console_actions", stdout=StringIO())
        cls.seller = Seller.objects.create(name="Vendedor", internal=True)
        cls.campaign = Campaign.objects.create(name="Campaña test", active=True, priority=3)

    def as_datetime(self, value):
        return timezone.make_aware(value) if settings.USE_TZ else value

    def make_activity(self, contact, when=datetime(2026, 5, 15, 10, 0), status="P", notes=None, campaign=None):
        return Activity.objects.create(
            contact=contact,
            campaign=self.campaign if campaign is None else campaign,
            seller=self.seller,
            datetime=self.as_datetime(when),
            activity_type="C",
            status=status,
            notes=notes,
        )

    def make_ccs(self, contact, status, campaign_resolution=None):
        return ContactCampaignStatus.objects.create(
            contact=contact,
            campaign=self.campaign,
            status=status,
            campaign_resolution=campaign_resolution,
            seller=self.seller,
        )

    def run_command(self, *args, date=CUTOFF, **kwargs):
        out = StringIO()
        call_command("close_lost_schedule_activities", "--date", date, *args, stdout=out, **kwargs)
        return out.getvalue()


class CloseLostScheduleCommandTest(CloseLostScheduleTestMixin, TestCase):
    def test_cierra_actividad_y_marca_accion(self):
        """La actividad queda completada, con la acción close-lost-schedule y la nota appendeada."""
        contact = ContactFactory()
        activity = self.make_activity(contact, notes="Pidió que la llamen el lunes")
        self.make_ccs(contact, CAMPAIGN_STATUS.CONTACTED, "SC")

        self.run_command()

        activity.refresh_from_db()
        self.assertEqual(activity.status, "C")
        self.assertEqual(activity.seller_console_action.slug, "close-lost-schedule")
        self.assertIn("Pidió que la llamen el lunes", activity.notes)
        self.assertIn("t1175", activity.notes)

    def test_no_modifica_datetime_de_la_actividad(self):
        """La fecha pactada es información: el cierre no la pisa."""
        contact = ContactFactory()
        activity = self.make_activity(contact)
        self.make_ccs(contact, CAMPAIGN_STATUS.CONTACTED, "SC")
        original_datetime = activity.datetime

        self.run_command()

        activity.refresh_from_db()
        self.assertEqual(activity.datetime, original_datetime)

    def test_contactado_pasa_a_finalizado_con_contacto(self):
        """Status 2 (contactado) → 4 (finalizado con contacto), resolución LS."""
        contact = ContactFactory()
        self.make_activity(contact)
        ccs = self.make_ccs(contact, CAMPAIGN_STATUS.CONTACTED, "SC")

        self.run_command()

        ccs.refresh_from_db()
        self.assertEqual(ccs.status, CAMPAIGN_STATUS.ENDED_WITH_CONTACT)
        self.assertEqual(ccs.campaign_resolution, "LS")
        self.assertEqual(ccs.last_console_action.slug, "close-lost-schedule")

    def test_no_contactado_pasa_a_finalizado_sin_contacto(self):
        """Status 3 (llamado, no se pudo contactar) → 5 (finalizado sin contacto), resolución LS."""
        contact = ContactFactory()
        self.make_activity(contact)
        ccs = self.make_ccs(contact, CAMPAIGN_STATUS.CALLED_COULD_NOT_CONTACT, "NF")

        self.run_command()

        ccs.refresh_from_db()
        self.assertEqual(ccs.status, CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT)
        self.assertEqual(ccs.campaign_resolution, "LS")

    def test_no_pisa_ccs_ya_terminal_con_venta(self):
        """Un ccs cerrado con venta queda intacto; la actividad colgada igual se cierra."""
        contact = ContactFactory()
        activity = self.make_activity(contact)
        ccs = self.make_ccs(contact, CAMPAIGN_STATUS.ENDED_WITH_CONTACT, "S2")

        self.run_command()

        ccs.refresh_from_db()
        self.assertEqual(ccs.status, CAMPAIGN_STATUS.ENDED_WITH_CONTACT)
        self.assertEqual(ccs.campaign_resolution, "S2")
        activity.refresh_from_db()
        self.assertEqual(activity.status, "C")

    def test_no_pisa_venta_aunque_el_status_no_sea_terminal(self):
        """Una venta (S1/S2) nunca se sobrescribe, ni siquiera si el status quedó en 2."""
        contact = ContactFactory()
        self.make_activity(contact)
        ccs = self.make_ccs(contact, CAMPAIGN_STATUS.CONTACTED, "S1")

        self.run_command()

        ccs.refresh_from_db()
        self.assertEqual(ccs.status, CAMPAIGN_STATUS.CONTACTED)
        self.assertEqual(ccs.campaign_resolution, "S1")

    def test_no_toca_agendas_posteriores_a_la_fecha_de_corte(self):
        """La fecha de corte es inclusive: el 31 de mayo entra, el 1 de junio no."""
        contact_in = ContactFactory()
        activity_in = self.make_activity(contact_in, when=datetime(2026, 5, 31, 23, 30))
        self.make_ccs(contact_in, CAMPAIGN_STATUS.CONTACTED, "SC")

        contact_out = ContactFactory()
        activity_out = self.make_activity(contact_out, when=datetime(2026, 6, 1, 9, 0))
        ccs_out = self.make_ccs(contact_out, CAMPAIGN_STATUS.CONTACTED, "SC")

        self.run_command()

        activity_in.refresh_from_db()
        self.assertEqual(activity_in.status, "C")
        activity_out.refresh_from_db()
        self.assertEqual(activity_out.status, "P")
        ccs_out.refresh_from_db()
        self.assertEqual(ccs_out.status, CAMPAIGN_STATUS.CONTACTED)

    def test_ignora_actividades_sin_campania(self):
        """Las actividades pendientes que no son de campaña no se tocan."""
        contact = ContactFactory()
        activity = Activity.objects.create(
            contact=contact,
            campaign=None,
            datetime=self.as_datetime(datetime(2026, 5, 15, 10, 0)),
            activity_type="C",
            status="P",
        )

        self.run_command()

        activity.refresh_from_db()
        self.assertEqual(activity.status, "P")

    def test_ignora_actividades_que_no_son_llamadas(self):
        """Sólo las llamadas (activity_type='C') funcionan como agenda en la consola."""
        contact = ContactFactory()
        activity = self.make_activity(contact)
        activity.activity_type = "M"
        activity.save()

        self.run_command()

        activity.refresh_from_db()
        self.assertEqual(activity.status, "P")

    def test_par_con_dos_agendas_cierra_ambas_y_un_solo_ccs(self):
        """Un par con dos agendas colgadas cierra las dos actividades y mapea el ccs una sola vez."""
        contact = ContactFactory()
        first = self.make_activity(contact, when=datetime(2026, 3, 1, 10, 0))
        second = self.make_activity(contact, when=datetime(2026, 5, 1, 10, 0))
        ccs = self.make_ccs(contact, CAMPAIGN_STATUS.CONTACTED, "SC")

        output = self.run_command()

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, "C")
        self.assertEqual(second.status, "C")
        ccs.refresh_from_db()
        self.assertEqual(ccs.status, CAMPAIGN_STATUS.ENDED_WITH_CONTACT)
        self.assertEqual(ccs.campaign_resolution, "LS")
        self.assertIn("Activities to close: 2 (1 contact/campaign pairs)", output)

    def test_actividad_sin_ccs_se_cierra_y_se_reporta(self):
        """Una agenda huérfana (con campaña, sin ContactCampaignStatus) se cierra y se informa."""
        contact = ContactFactory()
        activity = self.make_activity(contact)

        output = self.run_command()

        activity.refresh_from_db()
        self.assertEqual(activity.status, "C")
        self.assertIn("Without ContactCampaignStatus (only the activity is closed): 1", output)

    def test_dry_run_no_escribe_nada(self):
        contact = ContactFactory()
        activity = self.make_activity(contact)
        ccs = self.make_ccs(contact, CAMPAIGN_STATUS.CONTACTED, "SC")

        self.run_command("--dry-run")

        activity.refresh_from_db()
        self.assertEqual(activity.status, "P")
        self.assertIsNone(activity.seller_console_action)
        ccs.refresh_from_db()
        self.assertEqual(ccs.status, CAMPAIGN_STATUS.CONTACTED)
        self.assertEqual(ccs.campaign_resolution, "SC")

    def test_avisa_antes_de_cerrar_cuando_no_es_dry_run(self):
        contact = ContactFactory()
        self.make_activity(contact)
        self.make_ccs(contact, CAMPAIGN_STATUS.CONTACTED, "SC")

        output = self.run_command()

        self.assertIn("Closing 1 schedules and updating 1 campaign statuses now", output)

    def test_avisa_que_el_csv_solo_no_es_dry_run(self):
        """--csv no convierte la corrida en una prueba, y eso tiene que decirse."""
        contact = ContactFactory()
        self.make_activity(contact)
        self.make_ccs(contact, CAMPAIGN_STATUS.CONTACTED, "SC")

        with tempfile.TemporaryDirectory() as tmp:
            output = self.run_command("--csv", os.path.join(tmp, "salida.csv"))

        self.assertIn("The CSV was written, but this is NOT a dry run.", output)

    def test_el_dry_run_no_avisa_de_cierre(self):
        contact = ContactFactory()
        self.make_activity(contact)
        self.make_ccs(contact, CAMPAIGN_STATUS.CONTACTED, "SC")

        with tempfile.TemporaryDirectory() as tmp:
            output = self.run_command("--dry-run", "--csv", os.path.join(tmp, "salida.csv"))

        self.assertIn("DRY RUN: nothing was written.", output)
        self.assertNotIn("NOT a dry run", output)

    def test_es_idempotente(self):
        """La segunda corrida no encuentra nada: las agendas ya no están pendientes."""
        contact = ContactFactory()
        self.make_activity(contact)
        self.make_ccs(contact, CAMPAIGN_STATUS.CONTACTED, "SC")

        self.run_command()
        output = self.run_command()

        self.assertIn("No schedules to close", output)

    def test_no_modifica_last_action_date(self):
        """last_action_date es auto_now: bulk_update lo deja como estaba, save() lo pisaría."""
        contact = ContactFactory()
        self.make_activity(contact)
        ccs = self.make_ccs(contact, CAMPAIGN_STATUS.CONTACTED, "SC")
        # update() evita el auto_now, igual que en la base real.
        ContactCampaignStatus.objects.filter(pk=ccs.pk).update(last_action_date=date(2025, 11, 20))

        self.run_command()

        ccs.refresh_from_db()
        self.assertEqual(ccs.last_action_date, date(2025, 11, 20))

    def test_status_contactado_sigue_contando_en_get_contacted_statuses(self):
        """El guardarraíl de la métrica: quien fue contactado sigue en el balde de contactados."""
        contact = ContactFactory()
        self.make_activity(contact)
        ccs = self.make_ccs(contact, CAMPAIGN_STATUS.CONTACTED, "SC")

        self.run_command()

        ccs.refresh_from_db()
        self.assertIn(ccs.status, get_contacted_statuses())

    def test_acota_por_campania(self):
        """--campaign deja fuera las agendas de las demás campañas."""
        other_campaign = Campaign.objects.create(name="Otra campaña", active=True, priority=3)
        contact = ContactFactory()
        activity = self.make_activity(contact)
        other_contact = ContactFactory()
        other_activity = self.make_activity(other_contact, campaign=other_campaign)

        self.run_command("--campaign", str(self.campaign.id))

        activity.refresh_from_db()
        self.assertEqual(activity.status, "C")
        other_activity.refresh_from_db()
        self.assertEqual(other_activity.status, "P")

    def test_falla_sin_la_accion_de_consola(self):
        """Sin close-lost-schedule el comando aborta pidiendo correr el populate."""
        SellerConsoleAction.objects.filter(slug="close-lost-schedule").delete()
        contact = ContactFactory()
        self.make_activity(contact)

        with self.assertRaises(CommandError):
            self.run_command()

    def test_comando_viejo_esta_deprecado(self):
        with self.assertRaises(CommandError):
            call_command("close_old_pending_activities_and_campaign_status", "--date", CUTOFF, stdout=StringIO())


class PopulateSellerConsoleActionsTest(TestCase):
    def test_close_lost_schedule_queda_inactiva_y_sobrevive_al_populate(self):
        """
        La acción vive en la tupla del populate (si no, el comando la borraría y los FK SET_NULL
        se llevarían la marca de miles de filas), pero inactiva: no es un botón de la consola.
        """
        call_command("populate_seller_console_actions", stdout=StringIO())
        call_command("populate_seller_console_actions", stdout=StringIO())

        action = SellerConsoleAction.objects.get(slug="close-lost-schedule")
        self.assertFalse(action.is_active)
        self.assertEqual(action.campaign_resolution, "LS")
        self.assertIsNone(action.campaign_status)
        # Las acciones que sí son botones siguen activas.
        self.assertTrue(SellerConsoleAction.objects.get(slug="close-without-contact").is_active)


class CampaignStatisticsResolutionBreakdownTest(CloseLostScheduleTestMixin, TestCase):
    """
    El panel de estadísticas de campaña arma sus filas desde los breakdowns declarados en
    core.choices, así que una resolución nueva aparece sin tocar la vista ni el template.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = User.objects.create_superuser(username="manager", password="testpass")

    def setUp(self):
        self.client = Client()
        self.client.login(username="manager", password="testpass")

    def get_panel(self, **params):
        return self.client.get(reverse("campaign_statistics_detail", args=[self.campaign.id]), params)

    def test_el_panel_muestra_la_fila_de_agenda_perdida(self):
        contact = ContactFactory()
        self.make_activity(contact)
        self.make_ccs(contact, CAMPAIGN_STATUS.CONTACTED, "SC")
        self.run_command()

        response = self.get_panel()

        self.assertEqual(response.status_code, 200)
        rows = {row["key"]: row for row in response.context["contacted_resolutions"]}
        self.assertEqual(rows["lost_schedule"]["count"], 1)
        self.assertEqual(rows["scheduled"]["count"], 0)
        self.assertContains(response, "Closed due to lost schedule")

    def test_las_claves_viejas_del_contexto_siguen_estando(self):
        """Se conservan para no romper templates que las usen en instalaciones custom."""
        contact = ContactFactory()
        self.make_activity(contact)
        self.make_ccs(contact, CAMPAIGN_STATUS.CONTACTED, "SC")
        self.run_command()

        response = self.get_panel()

        self.assertEqual(response.context["lost_schedule_count"], 1)
        self.assertEqual(response.context["scheduled_count"], 0)
        self.assertIn("total_rejects_pct", response.context)

    def test_los_baldes_agrupan_varios_codigos(self):
        """La fila de rechazo suma las cuatro resoluciones de rechazo."""
        for resolution in ("AS", "DN", "LO", "NI"):
            self.make_ccs(ContactFactory(), CAMPAIGN_STATUS.ENDED_WITH_CONTACT, resolution)

        response = self.get_panel()

        rows = {row["key"]: row for row in response.context["contacted_resolutions"]}
        self.assertEqual(rows["total_rejects"]["count"], 4)

    def test_se_puede_filtrar_por_resolucion(self):
        contact = ContactFactory()
        self.make_activity(contact)
        self.make_ccs(contact, CAMPAIGN_STATUS.CONTACTED, "SC")
        self.make_ccs(ContactFactory(), CAMPAIGN_STATUS.ENDED_WITH_CONTACT, "S2")
        self.run_command()

        response = self.get_panel(campaign_resolution="LS")

        self.assertEqual(response.context["filtered_count"], 1)
