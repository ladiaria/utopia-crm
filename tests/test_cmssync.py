# coding:utf-8
from builtins import range
import string
import random

from django.conf import settings
from django.test import TestCase, override_settings

from core.utils import cms_rest_api_request
from tests.factory import create_contact


def rand_chars(length=9):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))


class CMSyncTestCase(TestCase):

    def setUp(self):
        self.api_key = settings.LDSOCIAL_API_KEY
        with override_settings(WEB_CREATE_USER_ENABLED=True):
            # create a user with very low collission probability on email field
            name, email_pre_prefix, phone = "Jane Doe", "cms_test_crmsync_", "12345678"
            email = f"{email_pre_prefix}{rand_chars()}@gmail.com"
            self.contact = create_contact(name, phone, email)

    def tearDown(self):
        # TODO: (doing) Review the flow for remove a user from the CMS for tests
        #       (trying call the deletion api directly
        """
        api_uri = settings.WEB_DELETE_USER_URI
        if api_uri and self.api_key:
            post_to_cms_rest_api(
                "delete_contact_sync", api_uri, {"contact_id": self.contact.id, "email": self.contact.email}, "DELETE"
            )
        else:
            print("WARNING: Skipping delete on teardown due to missing API configuration")
        """
        pass

    def test1_create_contact_sync(self):
        self.assertIsNotNone(self.contact)
        self.assertIsNotNone(self.contact.id)

        # check on CMS, try to create the user again, it must fail
        res = cms_rest_api_request(
            "test1_create_contact_sync", settings.WEB_UPDATE_USER_URI, {"newemail": self.contact.email}
        )
        self.assertEqual(res, "ERROR")

    def test2_delete_contact_sync(self):
        self.assertIsNotNone(self.contact)
        self.assertIsNotNone(self.contact.id)
        self.contact.delete()

        # check on CMS, try to create the user again, it must be allowed
        # TODO: deletion sync is not yet implemented, uncomment lines left in this test when it's ready
        res = cms_rest_api_request(
            "test2_delete_contact_sync", settings.WEB_UPDATE_USER_URI, {"newemail": self.contact.email}
        )
        self.assertEqual(res.get("msg"), "OK")

    def test3_not_create_contact_without_sync(self):
        with override_settings(
            WEB_CREATE_USER_ENABLED=False, WEB_CREATE_USER_POST_WHITELIST=[settings.WEB_EMAIL_CHECK_URI]
        ):
            name, email_pre_prefix, phone = "Jane Doe", "cms_test_crmsync_", "12345678"
            email = f"{email_pre_prefix}{rand_chars()}@gmail.com"

            # create a user with very low collission probability on email field
            no_sync_conctact = create_contact(name, phone, email)
            # check on CMS email availability
            # if it were created, this check with a different id and the same emasil should fail
            # as we're testing the creation is disabled, this call return should be "ok"
            api_url = settings.WEB_EMAIL_CHECK_URI
            if api_url and self.api_key:
                res = cms_rest_api_request(
                    "sync_disabled", api_url, {"contact_id": no_sync_conctact.id + 1, "email": no_sync_conctact.email}
                )
                self.assertEqual(res.get("msg"), "OK")
                self.assertEqual(res.get("retval"), 0)
            else:
                print("WARNING: Skipping test_not_create_contact_without_sync due to missing API configuration")
