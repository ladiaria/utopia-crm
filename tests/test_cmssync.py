# coding:utf-8
from builtins import range
import string
import random
import requests

from django.conf import settings
from django.test import TestCase, override_settings
from tests.factory import create_contact


def rand_chars(length=9):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))


class CMSyncTestCase(TestCase):

    def setUp(self):
        settings.WEB_UPDATE_USER_VERIFY_SSL = False

    def tearDown(self):
        # TODO: Review the flow for remove a user from the CMS for tests
        # It may be sensitive for data inside the CMS
        pass

    def test_create_contact_sync(self):
        with override_settings(WEB_UPDATE_USER_ENABLED=True):
            name, email_pre_prefix, phone = "Jane Doe", "cms_test_crmsync_", "12345678"
            email = "%s%s@%s" % (email_pre_prefix, rand_chars(), "yoogle.com")
            # create a user with very low collission probability on email field
            self.contact = create_contact(name, phone, email)
            # get contact from CMS
            api_url = settings.WEB_EMAIL_CHECK_URI
            api_key = getattr(settings, "LDSOCIAL_API_KEY", None)
            if api_url and api_key:
                res = requests.post(
                    api_url,
                    headers={'Authorization': 'Api-Key ' + api_key},
                    data={"contact_id": self.contact.id, "email": self.contact.email},
                    verify=settings.WEB_UPDATE_USER_VERIFY_SSL
                )
                self.assertEqual(res.json()["msg"], "OK")
                self.assertEqual(res.json()["retval"], 0)

    def test_not_create_contact_without_sync(self):
        with override_settings(WEB_UPDATE_USER_ENABLED=False):
            name, email_pre_prefix, phone = "Jane Doe", "cms_test_crmsync_", "12345678"
            email = "%s%s@%s" % (email_pre_prefix, rand_chars(), "yoogle.com")
            # create a user with very low collission probability on email field
            no_sync_conctact = create_contact(name, phone, email)
            # get the contact from CMS
            api_url = settings.WEB_EMAIL_CHECK_URI
            api_key = getattr(settings, "LDSOCIAL_API_KEY", None)
            if api_url and api_key:
                res = requests.post(
                    api_url,
                    headers={'Authorization': 'Api-Key ' + api_key},
                    data={"contact_id": no_sync_conctact.id, "email": no_sync_conctact.email},
                    verify=settings.WEB_UPDATE_USER_VERIFY_SSL
                )
                self.assertEqual(res.json()["msg"], "OK")
                self.assertEqual(res.json()["retval"], 0)
