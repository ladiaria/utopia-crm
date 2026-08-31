# coding=utf-8
"""
Tests de la vista de gestion de takeovers.

Lo que mas importa acá es lo que NO se puede hacer: el permiso can_takeover_email es la separacion
de poderes entera. Un operador que puede editar contactos no puede aprobar el borrado de una cuenta
web, y eso tiene que valer tambien si escribe la URL a mano.
"""
from unittest import mock

from django.contrib.auth.models import Permission, User
from django.core import mail
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from core.models import EmailTakeoverRequest
from tests.factory import create_contact


EMAIL = "nuevo@example.com"
OLD_EMAIL = "viejo@example.com"
PREVIEW = {"mode": "merge", "drop_email": OLD_EMAIL, "keep_subscriber_id": 42}


@override_settings(
    WEB_UPDATE_USER_ENABLED=True,
    WEB_EMAIL_TAKEOVER_ENABLED=True,
    WEB_EMAIL_TAKEOVER_URI="http://cms.local/api/email_takeover/",
    WEB_UPDATE_USER_VALIDATION_MODULE=None,
)
class TestEmailTakeoverViews(TestCase):

    def setUp(self):
        with override_settings(WEB_UPDATE_USER_ENABLED=False, WEB_CREATE_USER_ENABLED=False):
            self.contact = create_contact(name="Cola Test", phone="099111222", email=OLD_EMAIL)
        self.operator = User.objects.create_user("operador", "op@example.com", "x", is_staff=True)
        self.reviewer = User.objects.create_user("supervisor", "sup@example.com", "x", is_staff=True)
        self.reviewer.user_permissions.add(Permission.objects.get(codename="can_takeover_email"))
        self.request_obj = EmailTakeoverRequest.objects.create(
            contact=self.contact, requested_email=EMAIL, preview_detail=PREVIEW
        )

    def test_sin_permiso_no_entra_a_la_cola(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("email_takeover_queue"))
        self.assertEqual(response.status_code, 403)

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    def test_sin_permiso_no_puede_aprobar_ni_escribiendo_la_url(self, mock_cms):
        self.client.force_login(self.operator)

        response = self.client.post(
            reverse("email_takeover_resolve", args=[self.request_obj.id]), {"action": "approve"}
        )

        self.assertEqual(response.status_code, 403)
        mock_cms.assert_not_called()
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, EmailTakeoverRequest.PENDING)

    def test_con_permiso_ve_el_pedido_y_lo_que_se_borraria(self):
        self.client.force_login(self.reviewer)

        response = self.client.get(reverse("email_takeover_queue"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, EMAIL)
        self.assertContains(response, OLD_EMAIL)  # la cuenta que se borraria, a la vista

    @mock.patch("core.models.validateEmailOnWeb")
    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    def test_aprobar_desde_la_vista(self, mock_cms, mock_validate):
        mock_cms.return_value = {"msg": "OK", "retval": 1, "detail": PREVIEW}
        mock_validate.return_value = {"msg": "OK"}
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse("email_takeover_resolve", args=[self.request_obj.id]), {"action": "approve"}
        )

        self.assertRedirects(response, reverse("email_takeover_queue"))
        self.request_obj.refresh_from_db()
        self.contact.refresh_from_db()
        self.assertEqual(self.request_obj.status, EmailTakeoverRequest.APPROVED)
        self.assertEqual(self.request_obj.resolved_by, self.reviewer)
        self.assertEqual(self.contact.email, EMAIL)

    def test_rechazar_desde_la_vista_guarda_la_nota(self):
        self.client.force_login(self.reviewer)

        self.client.post(
            reverse("email_takeover_resolve", args=[self.request_obj.id]),
            {"action": "reject", "resolution_note": "Son dos personas distintas"},
        )

        self.request_obj.refresh_from_db()
        self.contact.refresh_from_db()
        self.assertEqual(self.request_obj.status, EmailTakeoverRequest.REJECTED)
        self.assertEqual(self.request_obj.resolution_note, "Son dos personas distintas")
        self.assertEqual(self.contact.email, OLD_EMAIL)

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    def test_por_get_no_se_resuelve_nada(self, mock_cms):
        """Un link no puede borrar una cuenta web."""
        self.client.force_login(self.reviewer)

        response = self.client.get(reverse("email_takeover_resolve", args=[self.request_obj.id]))

        self.assertRedirects(response, reverse("email_takeover_queue"))
        mock_cms.assert_not_called()
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, EmailTakeoverRequest.PENDING)

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    def test_a_demanda_primero_muestra_el_preview_sin_ejecutar(self, mock_cms):
        mock_cms.return_value = {"msg": "OK", "retval": 1, "detail": PREVIEW}
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse("email_takeover_on_demand"), {"contact": self.contact.id, "email": EMAIL}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, OLD_EMAIL)  # que se borraria
        mock_cms.assert_called_once_with(self.contact.id, EMAIL, confirm=False)  # solo preview

    @mock.patch("core.models.validateEmailOnWeb")
    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    def test_a_demanda_ejecuta_y_deja_rastro(self, mock_cms, mock_validate):
        """Un takeover manual deja el mismo rastro que uno que vino de la cola."""
        mock_cms.side_effect = [
            {"msg": "OK", "retval": 1, "detail": PREVIEW},  # preview
            {"msg": "OK", "retval": 1, "detail": PREVIEW},  # ejecucion
        ]
        mock_validate.return_value = {"msg": "OK"}
        self.client.force_login(self.reviewer)
        other_email = "otro@example.com"

        self.client.post(
            reverse("email_takeover_on_demand"),
            {"contact": self.contact.id, "email": other_email, "action": "execute"},
        )

        created = EmailTakeoverRequest.objects.get(requested_email=other_email)
        self.assertEqual(created.status, EmailTakeoverRequest.APPROVED)
        self.assertEqual(created.requested_by, self.reviewer)
        self.assertEqual(created.resolved_by, self.reviewer)

    def test_el_item_esta_en_el_primer_nivel_del_sidebar(self):
        """
        Fuera de "Atencion al cliente": es una bandeja de trabajo pendiente y tiene que verse al
        entrar. Ademas, adentro de esa seccion no lo veia quien no estuviera en el grupo Support,
        aunque tuviera el permiso.
        """
        self.client.force_login(self.reviewer)

        response = self.client.get(reverse("contact_list"))

        self.assertContains(response, reverse("email_takeover_queue"))
        self.assertContains(response, "badge badge-warning right")  # el conteo de pendientes

    def test_sin_el_permiso_el_item_no_aparece(self):
        self.client.force_login(self.operator)

        response = self.client.get(reverse("contact_list"))

        self.assertNotContains(response, reverse("email_takeover_queue"))

    def test_a_demanda_sin_permiso_no_entra(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("email_takeover_on_demand"))
        self.assertEqual(response.status_code, 403)


@override_settings(
    WEB_UPDATE_USER_ENABLED=True,
    WEB_EMAIL_TAKEOVER_ENABLED=True,
    WEB_EMAIL_TAKEOVER_URI="http://cms.local/api/email_takeover/",
    WEB_UPDATE_USER_VALIDATION_MODULE=None,
    EMAIL_VALIDATION_ENABLED=False,
)
class TestEditContactQueues(TestCase):
    """
    La pantalla de editar contacto, por el camino real: POST al formulario.

    Los tests del enganche llaman a custom_clean directo, con el flag ya puesto. Eso no reproduce
    lo que pasa de verdad: un ModelForm corre Contact.clean() dentro de su _post_clean(), o sea
    ANTES de form_valid(), asi que lo que la vista prepare en form_valid llega tarde.
    """

    def setUp(self):
        with override_settings(WEB_UPDATE_USER_ENABLED=False, WEB_CREATE_USER_ENABLED=False):
            self.contact = create_contact(name="Contacto C", phone="099111222", email=OLD_EMAIL)
        self.operator = User.objects.create_user("operador2", "op2@example.com", "x", is_staff=True)
        self.client.force_login(self.operator)

    def _post(self, email, phone="092301380"):
        return self.client.post(
            reverse("edit_contact", args=[self.contact.id]),
            {"name": "Contacto C", "email": email, "phone": phone, "id_document_type": "", "tags": "[]"},
        )

    @staticmethod
    def _cms_veta_solo_el_nuevo(contact_id, email):
        """El CMS veta la direccion nueva; la que el contacto ya tiene esta sincronizada y da OK."""
        if email == EMAIL:
            return {"msg": "Ya existe otro usuario en la web utilizando ese email", "retval": 5}
        return {"msg": "OK", "retval": 0}

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    @mock.patch("core.models.validateEmailOnWeb")
    def test_el_conflicto_se_archiva_y_el_resto_se_guarda(self, mock_validate, mock_cms):
        mock_validate.side_effect = self._cms_veta_solo_el_nuevo
        mock_cms.return_value = {"msg": "OK", "retval": 1, "detail": PREVIEW}

        self._post(EMAIL)

        self.contact.refresh_from_db()
        # El email no se aplica...
        self.assertEqual(self.contact.email, OLD_EMAIL)
        # ...pero lo demas que el operador edito SI se guarda.
        self.assertIn("92301380", str(self.contact.phone))
        # ...y queda el pedido para el revisor.
        self.assertTrue(
            EmailTakeoverRequest.objects.filter(contact=self.contact, requested_email=EMAIL).exists()
        )

    @override_settings(EMAIL_TAKEOVER_NOTIFY_RECIPIENTS=["supervisor@example.com"])
    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    @mock.patch("core.models.validateEmailOnWeb")
    def test_el_correo_deja_comparar_las_dos_direcciones(self, mock_validate, mock_cms):
        """
        Por el camino real, la instancia llega a custom_clean con el email NUEVO ya asignado (lo
        pone el ModelForm), y recien despues del archivado se descarta. Si el correo lee de ahi,
        "Email actual" y "Email solicitado" salen iguales y el revisor no tiene que comparar.
        """
        mock_validate.side_effect = self._cms_veta_solo_el_nuevo
        mock_cms.return_value = {"msg": "OK", "retval": 1, "detail": PREVIEW}

        self._post(EMAIL)

        self.assertEqual(len(mail.outbox), 1)
        linea_actual = [
            ln for ln in mail.outbox[0].body.splitlines() if ln.startswith(("Email actual", "Current email"))
        ][0]
        self.assertIn(OLD_EMAIL, linea_actual)
        self.assertNotIn(EMAIL, linea_actual)

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    @mock.patch("core.models.validateEmailOnWeb")
    def test_conflicto_no_resoluble_muestra_el_motivo_del_cms(self, mock_validate, mock_cms):
        """Cuenta staff: el operador tiene que ver el motivo real, no el mensaje generico."""
        mock_validate.side_effect = self._cms_veta_solo_el_nuevo
        mock_cms.return_value = {
            "msg": "La cuenta web que tiene ese email es de un usuario STAFF de la diaria.",
            "retval": 0,
            "reason": "is_staff",
            "detail": {},
        }

        response = self._post(EMAIL)

        self.assertContains(response, "STAFF")
        self.assertFalse(EmailTakeoverRequest.objects.exists())
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.email, OLD_EMAIL)
