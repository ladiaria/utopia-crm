# coding=utf-8
"""
Saving a contact from the edit screen asks the CMS about its email once.

Each check is a request to the CMS that takes seconds in production (it/utopia-crm-ladiaria#177).
"""
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from tests.factory import create_contact


EMAIL = "contacto@example.com"
CMS_OK = {"msg": "OK", "retval": 0}


# The email format check is not what these tests are about, and it would reject example.com.
@override_settings(WEB_UPDATE_USER_ENABLED=True, WEB_UPDATE_USER_VALIDATION_MODULE=None, EMAIL_VALIDATION_ENABLED=False)
class TestEditContactAsksTheCmsOnce(TestCase):
    def setUp(self):
        with override_settings(WEB_UPDATE_USER_ENABLED=False, WEB_CREATE_USER_ENABLED=False):
            self.contact = create_contact(name="Contacto", phone="099111222", email=EMAIL)
        self.client.force_login(User.objects.create_user("operador", "op@example.com", "x", is_staff=True))

    def _post(self, **data):
        fields = {"name": "Contacto", "email": EMAIL, "phone": "099111222", "id_document_type": "", "tags": "[]"}
        fields.update(data)
        return self.client.post(reverse("edit_contact", args=[self.contact.id]), fields)

    @mock.patch("core.models.updatewebuser", return_value={"msg": "OK"})
    @mock.patch("core.models.validateEmailOnWeb", return_value=CMS_OK)
    def test_a_save_checks_the_email_once(self, mock_validate, mock_update):
        response = self._post(name="Contacto editado")

        self.assertRedirects(response, reverse("contact_detail", args=[self.contact.id]), fetch_redirect_response=False)
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.name, "Contacto editado")
        self.assertEqual(mock_validate.call_count, 1)

    @mock.patch("core.models.updatewebuser", return_value={"msg": "OK"})
    @mock.patch("core.models.validateEmailOnWeb", return_value=CMS_OK)
    def test_tags_are_saved(self, mock_validate, mock_update):
        self._post(tags='[{"value": "una"}, {"value": "otra"}]')

        self.assertEqual(sorted(self.contact.tags.names()), ["otra", "una"])
        self.assertEqual(mock_validate.call_count, 1)

    @mock.patch("core.models.updatewebuser", return_value={"msg": "OK"})
    @mock.patch("core.models.validateEmailOnWeb")
    def test_a_rejected_email_is_not_saved(self, mock_validate, mock_update):
        mock_validate.return_value = {"msg": "Ya existe otro usuario en la web utilizando ese email", "retval": 5}

        response = self._post(email="otro@example.com")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya existe otro usuario en la web")
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.email, EMAIL)
        mock_update.assert_not_called()
