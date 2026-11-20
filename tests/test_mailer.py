from unittest import mock

from django.core import mail
from django.core.mail.backends.locmem import EmailBackend as LocmemBackend
from django.test import SimpleTestCase, override_settings

from util.mailer import send_html_email

RENDER = "util.mailer.render_to_string"


class ReplyToBackend(LocmemBackend):
    """A backend that changes the messages, to check that send_html_email goes through EMAIL_BACKEND."""

    def send_messages(self, email_messages):
        for message in email_messages:
            message.reply_to = ["it@example.com"]
        return super().send_messages(email_messages)


class SendHtmlEmailTests(SimpleTestCase):
    def test_sends_the_rendered_template_as_html(self):
        with mock.patch(RENDER, return_value="<p>Hello</p>") as render:
            sent = send_html_email("crm@example.com", ["a@example.com", "b@example.com"], "Subject", "x.html", {"k": 1})
        render.assert_called_once_with("x.html", {"k": 1})
        self.assertEqual(sent, 1)
        message = mail.outbox[0]
        self.assertEqual(message.from_email, "crm@example.com")
        self.assertEqual(message.to, ["a@example.com", "b@example.com"])
        self.assertEqual(message.subject, "Subject")
        self.assertEqual(message.body, "<p>Hello</p>")
        self.assertEqual(message.message().get_content_type(), "text/html")

    def test_context_defaults_to_empty(self):
        with mock.patch(RENDER, return_value="") as render:
            send_html_email("crm@example.com", ["a@example.com"], "Subject", "x.html")
        render.assert_called_once_with("x.html", {})

    def test_accepts_a_tuple_of_recipients(self):
        with mock.patch(RENDER, return_value=""):
            send_html_email("crm@example.com", ("a@example.com",), "Subject", "x.html")
        self.assertEqual(mail.outbox[0].to, ["a@example.com"])

    @override_settings(EMAIL_BACKEND=f"{__name__}.ReplyToBackend")
    def test_goes_through_the_configured_email_backend(self):
        with mock.patch(RENDER, return_value=""):
            send_html_email("crm@example.com", ["a@example.com"], "Subject", "x.html")
        self.assertEqual(mail.outbox[0].message()["Reply-To"], "it@example.com")
