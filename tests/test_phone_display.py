from phonenumber_field.phonenumber import PhoneNumber

from django.test import SimpleTestCase, override_settings

from core.templatetags.core_tags import phone_display


@override_settings(PHONENUMBER_DEFAULT_REGION="UY")
class PhoneDisplayTestCase(SimpleTestCase):
    def test_local_number_keeps_national_format(self):
        number = PhoneNumber.from_string("+59899123456")
        self.assertEqual(phone_display(number), number.as_national)

    def test_foreign_number_shows_international_format_and_flag(self):
        number = PhoneNumber.from_string("+5491123456789")
        self.assertHTMLEqual(
            phone_display(number), '+54 9 11 2345-6789 <span class="flag-icon flag-icon-ar" title="AR"></span>'
        )

    def test_empty_value(self):
        self.assertEqual(phone_display(""), "")
        self.assertEqual(phone_display(None), "")

    def test_invalid_number_keeps_national_format(self):
        number = PhoneNumber.from_string("123", region="UY")
        self.assertEqual(phone_display(number), number.as_national)
