# coding=utf-8
from django.core.mail import EmailMessage
from django.template.loader import render_to_string


def send_html_email(from_address, to_addresses, subject, template, context=None):
    """
    Sends an HTML email rendered from a template.

    It goes through Django's email backend (EMAIL_BACKEND), like send_mail, so whatever a deployment configures there
    applies to these emails too (for example a backend that sets a Reply-To), and tests can read it from mail.outbox.
    Returns the number of messages sent; raises on SMTP errors, as it always did.
    """
    message = EmailMessage(subject, render_to_string(template, context or {}), from_address, list(to_addresses))
    message.content_subtype = "html"
    return message.send()
