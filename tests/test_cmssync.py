# coding:utf-8
import unittest

from django.conf import settings
from django.test import TestCase, override_settings

from util import rand_chars
from core.utils import cms_rest_api_request
from tests.factory import create_contact


class CMSyncTestCase(TestCase):

    api_key = settings.LDSOCIAL_API_KEY
    contact = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if hasattr(settings, 'WEB_UPDATE_USER_URI') and settings.WEB_UPDATE_USER_URI and cls.api_key:
            # create a user with very low collission probability on email field
            name, email_pre_prefix, phone = "Jane Doe", "cms_test_crmsync_", "12345678"
            email = f"{email_pre_prefix}{rand_chars()}@gmail.com"
            cls.contact = create_contact(name, phone, email)
        else:
            print("WARNING: CMS sync tests are disabled due to missing configuration.")
            raise unittest.SkipTest("CMS sync tests are disabled.")

    def tearDown(self):
        if self.contact.id:
            self.contact.delete()
        super().tearDown()

    def test1_create_contact(self):
        self.assertIsNotNone(self.contact)
        self.assertIsNotNone(self.contact.id)
        # if "fullsync" is enabled, try to create the user again, it must fail
        if settings.WEB_CREATE_USER_ENABLED:
            self.assertEqual(
                cms_rest_api_request(
                    "test1_create_contact",
                    settings.WEB_UPDATE_USER_URI,
                    {"contact_id": self.contact.id, "newemail": self.contact.email},
                ),
                "ERROR",
            )
        else:
            print("NOTICE: Skipping sync check on test1_create_contact_sync due to fullsync disabled")

    def test2_delete_contact(self):
        if not self.contact.id:
            self.setUpClass()
        self.assertIsNotNone(self.contact)
        self.assertIsNotNone(self.contact.id)
        contact_id, newemail = self.contact.id, self.contact.email
        self.contact.delete()
        # if "fullsync" is enabled, try to create the user again, it must be allowed
        if settings.WEB_CREATE_USER_ENABLED:
            self.assertEqual(
                cms_rest_api_request(
                    "test2_delete_contact",
                    settings.WEB_UPDATE_USER_URI,
                    {"contact_id": contact_id, "newemail": newemail},
                ).get("message"),
                "OK",
            )
        else:
            print("NOTICE: Skipping sync check on test2_delete_contact_sync due to fullsync disabled")

    def test3_not_create_contact_without_sync(self):
        api_uri = settings.WEB_EMAIL_CHECK_URI
        if api_uri:
            with override_settings(WEB_CREATE_USER_ENABLED=False, WEB_CREATE_USER_POST_WHITELIST=[api_uri]):
                name, email_pre_prefix, phone = "Jane Doe", "cms_test_crmsync_", "12345678"
                email = f"{email_pre_prefix}{rand_chars()}@gmail.com"
                # create a user with very low collission probability on email field
                no_sync_conctact = create_contact(name, phone, email)
                # check on CMS email availability
                # if it were created, this check with a different id and the same email should fail
                # as we're testing the creation is disabled, this call return should be "ok"
                res = cms_rest_api_request(
                    "sync_disabled", api_uri, {"contact_id": no_sync_conctact.id + 1, "email": email}
                )
                self.assertEqual(res.get("msg"), "OK")
                self.assertEqual(res.get("retval"), 0)
        else:
            print("NOTICE: Skipping test_not_create_contact_without_sync due to missing API configuration")
