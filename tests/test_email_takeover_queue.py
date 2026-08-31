# coding=utf-8
"""
Tests de la cola de takeovers de email (tajada call center).

A diferencia de MercadoPago -- que ejecuta el takeover en el momento porque es self-service --
el call center NO ejecuta: la vista opta por la cola seteando self._takeover_enqueue = True, el
conflicto resoluble se archiva como EmailTakeoverRequest, el cambio de email se descarta y el
resto del contacto se guarda. Un revisor con can_takeover_email lo aprueba o lo rechaza despues.

Regresion importante: sin el flag, todo sigue exactamente como antes (bloqueo).
"""
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test.utils import override_settings

from core.email_takeover_queue import (
    FAILED,
    REFUSED,
    RESOLVED,
    UNREACHABLE,
    approve_takeover,
    queue_takeover_after_create,
    reject_takeover,
)
from core.models import EmailTakeoverRequest
from tests.factory import create_contact


CONFLICT = {"msg": "Ya existe otro usuario en la web utilizando ese email", "retval": 5}
OK = {"msg": "OK"}
EMAIL = "nuevo@example.com"
OLD_EMAIL = "viejo@example.com"

# Preview del CMS: el takeover aplica y absorberia (y borraria) la cuenta vieja.
PREVIEW_MERGE = {
    "msg": "OK",
    "retval": 1,
    "reason": "ok",
    "detail": {"mode": "merge", "drop_email": OLD_EMAIL, "keep_subscriber_id": 42},
}
# Preview del sub-caso simple: no hay cuenta propia, solo se vincula la huerfana. No borra nada.
PREVIEW_ATTACH = {"msg": "OK", "retval": 1, "reason": "ok", "detail": {"mode": "attach_only"}}
# El CMS dice que no: cuenta staff.
PREVIEW_STAFF = {
    "msg": "La cuenta web que tiene ese email es de un usuario STAFF de la diaria.",
    "retval": 0,
    "reason": "is_staff",
    "detail": {},
}


@override_settings(
    WEB_UPDATE_USER_ENABLED=True,
    WEB_EMAIL_TAKEOVER_ENABLED=True,
    WEB_EMAIL_TAKEOVER_URI="http://cms.local/api/email_takeover/",
    WEB_UPDATE_USER_VALIDATION_MODULE=None,
)
class TestTakeoverQueueHook(TestCase):
    """El enganche en Contact.custom_clean: cuando encola, cuando bloquea, cuando no toca nada."""

    def _contact(self, email=OLD_EMAIL):
        with override_settings(WEB_CREATE_USER_ENABLED=False, WEB_UPDATE_USER_ENABLED=False):
            return create_contact(name="Cola Test", phone="099111222", email=email)

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    @mock.patch("core.models.validateEmailOnWeb")
    def test_conflicto_resoluble_encola_y_no_lanza(self, mock_validate, mock_cms):
        """Call center: el conflicto se archiva, el email se descarta y el guardado sigue vivo."""
        contact = self._contact()
        mock_validate.return_value = CONFLICT
        mock_cms.return_value = PREVIEW_MERGE
        contact._takeover_enqueue = True

        contact.custom_clean(EMAIL, debug=False)  # no debe lanzar

        # El CMS fue consultado en modo preview: NO se ejecuto nada.
        mock_cms.assert_called_once_with(contact.id, EMAIL, confirm=False)
        # El cambio de email se descarto y quedo la marca para que la vista avise.
        self.assertEqual(contact.email, OLD_EMAIL)
        self.assertEqual(contact.takeover_queued, EMAIL)
        # Quedo el pedido, con el preview guardado para el revisor.
        request = EmailTakeoverRequest.objects.get(contact=contact, requested_email=EMAIL)
        self.assertEqual(request.status, EmailTakeoverRequest.PENDING)
        self.assertEqual(request.takeover_mode, "merge")
        self.assertTrue(request.deletes_an_account)

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    @mock.patch("core.models.validateEmailOnWeb")
    def test_attach_only_no_borra_ninguna_cuenta(self, mock_validate, mock_cms):
        """El sub-caso simple se encola igual, pero el pedido dice que no se borra nada."""
        contact = self._contact()
        mock_validate.return_value = CONFLICT
        mock_cms.return_value = PREVIEW_ATTACH
        contact._takeover_enqueue = True

        contact.custom_clean(EMAIL, debug=False)

        request = EmailTakeoverRequest.objects.get(contact=contact, requested_email=EMAIL)
        self.assertEqual(request.takeover_mode, "attach_only")
        self.assertFalse(request.deletes_an_account)

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    @mock.patch("core.models.validateEmailOnWeb")
    def test_no_resoluble_muestra_el_motivo_del_cms_y_no_encola(self, mock_validate, mock_cms):
        """Staff / suscripcion activa / contenido no movible: el operador ve el motivo real."""
        contact = self._contact()
        mock_validate.return_value = CONFLICT
        mock_cms.return_value = PREVIEW_STAFF
        contact._takeover_enqueue = True

        with self.assertRaises(ValidationError) as cm:
            contact.custom_clean(EMAIL, debug=False)

        self.assertIn("STAFF", str(cm.exception))
        self.assertFalse(EmailTakeoverRequest.objects.exists())

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    @mock.patch("core.models.validateEmailOnWeb")
    def test_cms_caido_bloquea_como_siempre_y_no_encola(self, mock_validate, mock_cms):
        """Sin respuesta del CMS no se archiva nada: no se abre un pedido sobre una suposicion."""
        contact = self._contact()
        mock_validate.return_value = CONFLICT
        mock_cms.return_value = "TIMEOUT"
        contact._takeover_enqueue = True

        with self.assertRaises(ValidationError) as cm:
            contact.custom_clean(EMAIL, debug=False)

        self.assertIn("Ya existe", str(cm.exception))
        self.assertFalse(EmailTakeoverRequest.objects.exists())

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    @mock.patch("core.models.validateEmailOnWeb")
    def test_sin_flag_no_encola_regresion(self, mock_validate, mock_cms):
        """Batch, comandos, cualquier otro save: el comportamiento de siempre, intacto."""
        contact = self._contact()
        mock_validate.return_value = CONFLICT

        with self.assertRaises(ValidationError) as cm:
            contact.custom_clean(EMAIL, debug=False)

        self.assertIn("Ya existe", str(cm.exception))
        mock_cms.assert_not_called()
        self.assertFalse(EmailTakeoverRequest.objects.exists())

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    @mock.patch("core.models.validateEmailOnWeb")
    def test_kill_switch_apagado_no_encola(self, mock_validate, mock_cms):
        """Con el kill switch en False el CMS no se toca, aunque la vista pida la cola."""
        contact = self._contact()
        mock_validate.return_value = CONFLICT
        contact._takeover_enqueue = True

        with override_settings(WEB_EMAIL_TAKEOVER_ENABLED=False):
            with self.assertRaises(ValidationError):
                contact.custom_clean(EMAIL, debug=False)

        mock_cms.assert_not_called()
        self.assertFalse(EmailTakeoverRequest.objects.exists())

    @override_settings(EMAIL_TAKEOVER_NOTIFY_RECIPIENTS=["supervisor@example.com"])
    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    @mock.patch("core.models.validateEmailOnWeb")
    def test_avisa_a_los_revisores_al_archivar(self, mock_validate, mock_cms):
        """Nadie tiene que estar mirando el sidebar para enterarse."""
        contact = self._contact()
        mock_validate.return_value = CONFLICT
        mock_cms.return_value = PREVIEW_MERGE
        contact._takeover_enqueue = True

        contact.custom_clean(EMAIL, debug=False)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(EMAIL, mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["supervisor@example.com"])
        # El revisor tiene que poder COMPARAR: el que tiene contra el que le piden. Si los dos
        # campos dicen lo mismo, el correo no sirve para decidir nada.
        cuerpo = mail.outbox[0].body
        self.assertIn(OLD_EMAIL, cuerpo)
        self.assertIn(EMAIL, cuerpo)
        actual = [ln for ln in cuerpo.splitlines() if ln.startswith(("Email actual", "Current email"))][0]
        self.assertIn(OLD_EMAIL, actual)
        self.assertNotIn(EMAIL, actual)
        # El aviso tiene que decir que los datos SE MUDAN, no solo que se borra una cuenta: a secas
        # asusta y hace dudar de lo que mas importa, que son las newsletters.
        cuerpo = mail.outbox[0].body.lower()
        self.assertIn("newsletter", cuerpo)
        self.assertTrue("mud" in cuerpo or "move" in cuerpo, cuerpo)

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    @mock.patch("core.models.validateEmailOnWeb")
    def test_reintento_no_duplica_el_pedido(self, mock_validate, mock_cms):
        """El operador que reintenta no llena la cola de pedidos identicos."""
        contact = self._contact()
        mock_validate.return_value = CONFLICT
        mock_cms.return_value = PREVIEW_MERGE
        contact._takeover_enqueue = True

        contact.custom_clean(EMAIL, debug=False)
        contact.custom_clean(EMAIL, debug=False)

        self.assertEqual(EmailTakeoverRequest.objects.filter(requested_email=EMAIL).count(), 1)


@override_settings(
    WEB_UPDATE_USER_ENABLED=True,
    WEB_EMAIL_TAKEOVER_ENABLED=True,
    WEB_EMAIL_TAKEOVER_URI="http://cms.local/api/email_takeover/",
    WEB_UPDATE_USER_VALIDATION_MODULE=None,
)
class TestTakeoverResolution(TestCase):
    """Aprobar y rechazar: que se ejecuta, que se aplica y que queda pendiente."""

    def setUp(self):
        with override_settings(WEB_UPDATE_USER_ENABLED=False, WEB_CREATE_USER_ENABLED=False):
            self.contact = create_contact(name="Cola Test", phone="099111222", email=OLD_EMAIL)
        self.reviewer = User.objects.create_user("supervisor", "sup@example.com", "x")
        self.request = EmailTakeoverRequest.objects.create(
            contact=self.contact, requested_email=EMAIL, preview_detail=PREVIEW_MERGE["detail"]
        )

    @mock.patch("core.models.validateEmailOnWeb")
    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    def test_aprobar_ejecuta_y_aplica_el_email(self, mock_cms, mock_validate):
        mock_cms.return_value = {"msg": "OK", "retval": 1, "detail": PREVIEW_MERGE["detail"]}
        mock_validate.return_value = OK  # tras el takeover el email ya no esta en conflicto

        outcome, _msg = approve_takeover(self.request, user=self.reviewer)

        self.assertEqual(outcome, RESOLVED)
        mock_cms.assert_called_once_with(self.contact.id, EMAIL, confirm=True)
        self.request.refresh_from_db()
        self.contact.refresh_from_db()
        self.assertEqual(self.request.status, EmailTakeoverRequest.APPROVED)
        self.assertEqual(self.request.resolved_by, self.reviewer)
        self.assertIsNotNone(self.request.resolved_at)
        self.assertEqual(self.contact.email, EMAIL)

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    def test_el_cms_se_niega_deja_el_pedido_pendiente(self, mock_cms):
        """Entre el pedido y la revision la otra cuenta pudo ganar una suscripcion activa."""
        mock_cms.return_value = {
            "msg": "La otra cuenta tiene una suscripcion activa.", "retval": 0, "reason": "has_subscription"
        }

        outcome, msg = approve_takeover(self.request, user=self.reviewer)

        self.assertEqual(outcome, REFUSED)
        self.assertIn("suscripcion activa", msg)
        self.request.refresh_from_db()
        self.contact.refresh_from_db()
        self.assertEqual(self.request.status, EmailTakeoverRequest.PENDING)
        self.assertEqual(self.contact.email, OLD_EMAIL)

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    def test_cms_caido_al_aprobar_no_cierra_el_pedido(self, mock_cms):
        mock_cms.return_value = "TIMEOUT"

        outcome, _msg = approve_takeover(self.request, user=self.reviewer)

        self.assertEqual(outcome, UNREACHABLE)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, EmailTakeoverRequest.PENDING)

    def test_rechazar_no_toca_nada(self):
        outcome, _msg = reject_takeover(self.request, user=self.reviewer, note="Son dos personas distintas")

        self.assertEqual(outcome, RESOLVED)
        self.request.refresh_from_db()
        self.contact.refresh_from_db()
        self.assertEqual(self.request.status, EmailTakeoverRequest.REJECTED)
        self.assertEqual(self.request.resolution_note, "Son dos personas distintas")
        self.assertEqual(self.contact.email, OLD_EMAIL)

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    def test_no_se_resuelve_dos_veces(self, mock_cms):
        reject_takeover(self.request, user=self.reviewer)

        outcome, _msg = approve_takeover(self.request, user=self.reviewer)

        self.assertEqual(outcome, FAILED)
        mock_cms.assert_not_called()


@override_settings(
    WEB_UPDATE_USER_ENABLED=True,
    WEB_EMAIL_TAKEOVER_ENABLED=True,
    WEB_EMAIL_TAKEOVER_URI="http://cms.local/api/email_takeover/",
    WEB_UPDATE_USER_VALIDATION_MODULE=None,
)
class TestTakeoverAfterCreate(TestCase):
    """
    Crear un contacto es el unico camino donde el CRM nunca le pregunta al CMS: Contact.clean()
    solo consulta `if ... and self.id`, y en una creacion todavia no hay id. El contacto se crea
    igual --es la entidad comercial-- pero el conflicto tiene que quedar archivado en vez de pasar
    en silencio.
    """

    def _contacto_nuevo(self, email=EMAIL):
        with override_settings(WEB_UPDATE_USER_ENABLED=False, WEB_CREATE_USER_ENABLED=False):
            return create_contact(name="Alta Test", phone="099333444", email=email)

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    def test_le_pregunta_al_takeover_no_al_email_check(self, mock_cms):
        """
        Preguntarle a validateEmailOnWeb aca no sirve: contesta OK sin mirar el email cuando el
        contacto no tiene cuenta web propia, y un contacto recien creado nunca la tiene. Por eso
        se consulta el preview del takeover, que es el que conoce esta forma y contesta
        attach_only.
        """
        contact = self._contacto_nuevo()
        mock_cms.return_value = PREVIEW_ATTACH

        queued = queue_takeover_after_create(contact)

        self.assertIsNotNone(queued)
        mock_cms.assert_called_once_with(contact.id, EMAIL, confirm=False)  # preview, no ejecucion
        self.assertEqual(queued.origin, EmailTakeoverRequest.ORIGIN_CREATE_CONTACT)
        self.assertEqual(queued.takeover_mode, "attach_only")
        self.assertFalse(queued.deletes_an_account)

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    def test_el_email_queda_en_el_contacto(self, mock_cms):
        """A diferencia de una edicion, aca no se descarta nada: no hay nada en disputa del lado
        del CRM."""
        contact = self._contacto_nuevo()
        mock_cms.return_value = PREVIEW_ATTACH

        queue_takeover_after_create(contact)

        contact.refresh_from_db()
        self.assertEqual(contact.email, EMAIL)

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    def test_email_libre_no_archiva_nada(self, mock_cms):
        """Sin cuenta huerfana que reclamar, el CMS contesta NO_ORPHAN y no hay pedido que hacer."""
        contact = self._contacto_nuevo()
        mock_cms.return_value = {"msg": "No hay cuenta web con ese email", "retval": 0, "reason": "no_orphan"}

        self.assertIsNone(queue_takeover_after_create(contact))
        self.assertFalse(EmailTakeoverRequest.objects.exists())

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    def test_no_archiva_lo_que_no_tiene_nada_que_decidir(self, mock_cms):
        """
        fix_email_only = la cuenta que tiene la direccion YA es la del contacto, porque el push
        normal del CRM al CMS la vinculo entre el guardado y este chequeo. Aprobar eso no vincula
        ni borra nada. Un pedido que no cambia nada le enseña al revisor a aprobar sin leer.
        """
        contact = self._contacto_nuevo()
        mock_cms.return_value = {"msg": "OK", "retval": 1, "detail": {"mode": "fix_email_only"}}

        self.assertIsNone(queue_takeover_after_create(contact))
        self.assertFalse(EmailTakeoverRequest.objects.exists())

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    def test_nunca_revienta_un_alta(self, mock_cms):
        """Un contacto que se creo se queda creado, pase lo que pase con el CMS."""
        contact = self._contacto_nuevo()
        mock_cms.side_effect = Exception("boom")

        self.assertIsNone(queue_takeover_after_create(contact))
        contact.refresh_from_db()
        self.assertEqual(contact.email, EMAIL)

    @mock.patch("core.email_takeover_queue.emailTakeoverOnWeb")
    def test_kill_switch_apagado_no_consulta(self, mock_cms):
        contact = self._contacto_nuevo()

        with override_settings(WEB_EMAIL_TAKEOVER_ENABLED=False):
            self.assertIsNone(queue_takeover_after_create(contact))

        mock_cms.assert_not_called()


class TestCascadaSeparada(TestCase):
    """
    El inventario de cascada del CMS es la respuesta de Collector a "que destruiria borrar esta
    cuenta", y se calcula ANTES de mover los datos. Mostrarlo tal cual, bajo un titulo que dice
    borrar, le hace creer al revisor que la persona pierde las newsletters. No las pierde: se unen
    con las de la cuenta que queda.
    """

    def _pedido(self, cascade):
        return EmailTakeoverRequest(preview_detail={"mode": "merge", "cascade_would_delete": cascade})

    def test_las_newsletters_van_del_lado_que_se_muda(self):
        req = self._pedido({"Subscriber_category_newsletters": 2, "Subscriber_newsletters": 3})

        self.assertEqual(req.cascade_moved, {"Subscriber_category_newsletters": 2, "Subscriber_newsletters": 3})
        self.assertEqual(req.cascade_lost, {})

    def test_la_cuenta_en_si_no_cuenta_como_perdida(self):
        """User y Subscriber son las filas de la cuenta: son lo que el takeover borra a proposito,
        no algo que se pierda de paso."""
        req = self._pedido({"User": 1, "Subscriber": 1, "Subscriber_category_newsletters": 2})

        self.assertEqual(req.cascade_lost, {})
        self.assertNotIn("User", req.cascade_moved)

    def test_lo_que_no_se_mueve_si_se_reporta_como_perdida(self):
        req = self._pedido({"User": 1, "Contribution": 2, "Follow": 5})

        self.assertEqual(req.cascade_lost, {"Contribution": 2})
        self.assertEqual(req.cascade_moved, {"Follow": 5})
