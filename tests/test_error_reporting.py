import sys

from django.test import RequestFactory, SimpleTestCase
from django.views.debug import ExceptionReporter, get_exception_reporter_filter


class ErrorReportingTestCase(SimpleTestCase):
    """The error emails sent to ADMINS must not include the API key or basic auth of the request."""

    def setUp(self):
        self.request = RequestFactory().post(
            "/api/", {"email": "a@example.com"}, HTTP_AUTHORIZATION="Api-Key s3cr3t.v4lu3", HTTP_USER_AGENT="tests"
        )

    def test_authorization_header_is_hidden(self):
        reporter_filter = get_exception_reporter_filter(self.request)
        meta = reporter_filter.get_safe_request_meta(self.request)
        self.assertEqual(meta["HTTP_AUTHORIZATION"], reporter_filter.cleansed_substitute)
        self.assertEqual(meta["HTTP_USER_AGENT"], "tests")  # the rest of the request is still reported

    def test_authorization_header_is_not_in_the_email_text(self):
        try:
            raise ValueError("boom")
        except ValueError:
            text = ExceptionReporter(self.request, *sys.exc_info()).get_traceback_text()
        self.assertNotIn("s3cr3t.v4lu3", text)
        self.assertIn("HTTP_AUTHORIZATION", text)
