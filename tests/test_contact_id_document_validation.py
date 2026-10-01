from django import forms
from django.test import TestCase, override_settings

from core.forms import ContactAdminForm, ContactUpdateForm


def reject_all(id_document, id_document_type):
    raise forms.ValidationError("invalid document %s" % id_document)


VALIDATOR = "tests.test_contact_id_document_validation.reject_all"


@override_settings(WEB_UPDATE_USER_ENABLED=False, WEB_EMAIL_CHECK_URI=None)
class ContactIdDocumentValidationTest(TestCase):

    def data(self, **extra):
        return dict({"name": "Persona", "id_document": "12345672"}, **extra)

    def test_admin_form_keeps_the_document(self):
        # clean_id_document used to return None, so saving this form dropped the document.
        form = ContactAdminForm(data=self.data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["id_document"], "12345672")

    def test_no_validator_by_default(self):
        for form_class in (ContactAdminForm, ContactUpdateForm):
            with self.subTest(form=form_class.__name__):
                self.assertTrue(form_class(data=self.data()).is_valid())

    @override_settings(CONTACT_ID_DOCUMENT_VALIDATOR=VALIDATOR)
    def test_validator_rejects(self):
        for form_class in (ContactAdminForm, ContactUpdateForm):
            with self.subTest(form=form_class.__name__):
                form = form_class(data=self.data())
                self.assertFalse(form.is_valid())
                self.assertIn("invalid document 12345672", form.errors["id_document"])

    @override_settings(CONTACT_ID_DOCUMENT_VALIDATOR=VALIDATOR)
    def test_validator_skipped_without_document(self):
        self.assertTrue(ContactUpdateForm(data=self.data(id_document="")).is_valid())
