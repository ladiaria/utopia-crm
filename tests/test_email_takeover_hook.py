# coding=utf-8
"""
Tests del enganche del takeover de email en Contact.custom_clean (tajada MercadoPago).

El takeover automatico corre SOLO cuando la instancia trae self._takeover_autoexec = True
(lo setea la vista de alta MercadoPago). En cualquier otro origen el flujo queda igual que
antes (dedupe/bloqueo) -> test de regresion del call center.
"""
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test.utils import override_settings

from tests.factory import create_contact


CONFLICT = {"msg": "Ya existe otro usuario en la web utilizando ese email", "retval": 5}
OK = {"msg": "OK"}
EMAIL = "nuevo@example.com"


@override_settings(WEB_UPDATE_USER_ENABLED=True, WEB_EMAIL_TAKEOVER_ENABLED=True)
class TestEmailTakeoverHook(TestCase):

    def _contact(self):
        with override_settings(WEB_CREATE_USER_ENABLED=False):
            return create_contact(name="Takeover Test", phone="099111222")

    @mock.patch("core.models.emailTakeoverOnWeb")
    @mock.patch("core.models.validateEmailOnWeb")
    def test_mp_autoexec_takeover_applicable_saves(self, mock_validate, mock_takeover):
        """MP: hay conflicto, el takeover aplica (retval=1) y la reconsulta da OK -> no lanza."""
        contact = self._contact()
        mock_validate.side_effect = [CONFLICT, OK]  # 1a conflicto, 2a (post-takeover) OK
        mock_takeover.return_value = {"msg": "OK", "retval": 1, "reason": "ok"}
        contact._takeover_autoexec = True

        contact.custom_clean(EMAIL, debug=False)  # no debe lanzar

        mock_takeover.assert_called_once_with(contact.id, EMAIL, confirm=True)
        self.assertEqual(mock_validate.call_count, 2)  # conflicto + reconsulta

    @mock.patch("core.models.emailTakeoverOnWeb")
    @mock.patch("core.models.validateEmailOnWeb")
    def test_mp_autoexec_not_applicable_raises_human_msg(self, mock_validate, mock_takeover):
        """MP: el takeover no aplica (staff) -> lanza ValidationError con el msg legible del CMS."""
        contact = self._contact()
        mock_validate.return_value = CONFLICT
        mock_takeover.return_value = {
            "msg": "La cuenta web que tiene ese email es de un usuario STAFF de la diaria.",
            "retval": 0,
            "reason": "is_staff",
        }
        contact._takeover_autoexec = True

        with self.assertRaises(ValidationError) as cm:
            contact.custom_clean(EMAIL, debug=False)
        self.assertIn("STAFF", str(cm.exception))
        mock_takeover.assert_called_once()

    @mock.patch("core.models.emailTakeoverOnWeb")
    @mock.patch("core.models.validateEmailOnWeb")
    def test_call_center_no_flag_no_takeover_regression(self, mock_validate, mock_takeover):
        """Sin _takeover_autoexec (call center/ediciones): NO llama al takeover y mantiene el
        comportamiento viejo (bloquea con el msg generico)."""
        contact = self._contact()
        mock_validate.return_value = CONFLICT

        with override_settings(WEB_UPDATE_USER_VALIDATION_MODULE=None):
            with self.assertRaises(ValidationError) as cm:
                contact.custom_clean(EMAIL, debug=False)

        self.assertIn("Ya existe", str(cm.exception))
        mock_takeover.assert_not_called()

    @mock.patch("core.models.emailTakeoverOnWeb")
    @mock.patch("core.models.validateEmailOnWeb")
    def test_kill_switch_disabled_no_takeover(self, mock_validate, mock_takeover):
        """Kill switch: con WEB_EMAIL_TAKEOVER_ENABLED=False, aunque haya _takeover_autoexec,
        NO se llama al takeover y el flujo cae al comportamiento de siempre (bloquea)."""
        contact = self._contact()
        mock_validate.return_value = CONFLICT
        contact._takeover_autoexec = True

        with override_settings(WEB_EMAIL_TAKEOVER_ENABLED=False, WEB_UPDATE_USER_VALIDATION_MODULE=None):
            with self.assertRaises(ValidationError) as cm:
                contact.custom_clean(EMAIL, debug=False)

        self.assertIn("Ya existe", str(cm.exception))
        mock_takeover.assert_not_called()
