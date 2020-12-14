# coding=utf-8
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE
from email.Utils import formatdate

from django.conf import settings
from django.template.loader import render_to_string


def send_html_email(from_address, to_addresses, subject, template, context={}):
    msg = MIMEMultipart()
    msg['From'] = from_address
    msg['To'] = COMMASPACE.join(to_addresses)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    html = MIMEText(render_to_string(template, context), 'html', 'utf-8')
    msg.attach(html)

    server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
    try:
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
    except smtplib.SMTPException:
        # ignore if server doesn't support authentication
        pass
    server.sendmail(from_address, to_addresses, msg.as_string())
    server.quit()
