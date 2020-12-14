# coding=utf-8
import requests
from django.test import TestCase

import django
django.setup()

from django.core.management import execute_from_command_line  # noqa
from django.conf import settings  # noqa
from django.test import Client  # noqa
from django.contrib.auth.models import User  # noqa


class TestCaseUtopia(TestCase):

    def login_admin(self, url=None, user=None, password=None):
        """
        Hace login de usuario con una requests.Session
        """
        s = requests.Session()
        s.get((url or self.ss_url) + 'admin/', verify=settings.WEB_UPDATE_USER_VERIFY_SSL)
        data = {'username': user or 'admin', 'password': password or 'admin', 'this_is_the_login_form': 1}
        csrftoken = s.cookies.get('csrftoken')
        if csrftoken:
            data['csrfmiddlewaretoken'] = csrftoken
        r = s.post((url or self.ss_url) + 'admin/', data=data, verify=settings.WEB_UPDATE_USER_VERIFY_SSL)
        r.raise_for_status()
        return s

    def html2text(self, text):
        """
        Trata de utilizar html2text para renderear html como texto en pantalla
        si no esta instalado el modulo lo imprime como viene.
        """
        try:
            import html2text
            print(html2text.html2text(text))
        except ImportError:
            print(text)


class TestCaseUtopiaDS(TestCaseUtopia):

    @classmethod
    def setUpClass(self):
        super(TestCaseUtopiaDS, self).setUpClass()

        self.client = Client()
        self.client.force_login(User.objects.get_or_create(username='admin')[0])
        self.ss_url = 'http://localhost:8000/'
