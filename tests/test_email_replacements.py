# coding=utf-8
from django.test import TestCase

from util.email_typosquash import clean_email


class TestEmailReplacements(TestCase):

    fixtures = ['email_replacements']

    def test1(self):

        # 1. no valid and no suggestions
        self.assertEqual(clean_email("address@gmalis.com"), {'valid': False, 'email': 'address@gmalis.com'})

        # 2. no valid but suggest
        self.assertEqual(
            clean_email("address@gmaill.com"),
            {'valid': False, 'email': 'address@gmaill.com', 'suggestion': 'address@gmail.com'},
        )

        # 3. domain is not valid but the replacement using our replacement list is valid
        self.assertEqual(
            clean_email("address@hotamil.com"),
            {'valid': False, 'email': "address@hotamil.com", "replacement": 'address@hotmail.com'},
        )

        # 4. valid
        self.assertEqual(clean_email("address@hotmail.com"), {'valid': True, 'email': 'address@hotmail.com'})

        # 5. valid domain but we have this domain in our replacement list as typo
        self.assertEqual(
            clean_email("address@hotmil.com"),
            {'valid': True, 'email': 'address@hotmil.com', 'replacement': 'address@hotmail.com'},
        )
