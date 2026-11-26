"""
Exception reporter filter for the error emails Django sends to ADMINS.

Django's SafeExceptionReporterFilter hides settings and request.META keys that match API, TOKEN, KEY, SECRET, PASS,
SIGNATURE or HTTP_COOKIE, but not HTTP_AUTHORIZATION. That header carries the API key other systems use to call the
CRM ("Authorization: Api-Key ...", from djangorestframework-api-key) and any HTTP basic auth credentials, so without
this filter every 500 on an API view emails them in clear text.
"""
import re

from django.views.debug import SafeExceptionReporterFilter as DjangoSafeExceptionReporterFilter


class SafeExceptionReporterFilter(DjangoSafeExceptionReporterFilter):
    hidden_settings = re.compile("API|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE|AUTHORIZATION", flags=re.I)
