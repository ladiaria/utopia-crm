# coding=utf-8
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse


class TestLogin(TestCase):

    def setUp(self):
        self.credentials = {'username': 'user', 'password': 'secret'}
        User.objects.create_user(**self.credentials)

    def test1_post_login(self):
        c = Client()
        # This should redirect you (302) to the login URL, so the status code won't be a 200
        response = c.post(reverse('contact_list'))
        self.assertEqual(response.status_code, 302)

        # This should let you login, and also should be authenticated
        response = c.post(reverse('login'), self.credentials, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)

        # From here the user should be able to see the contact list, so the status code will be a 200
        response = c.post(reverse('contact_list'))
        self.assertEqual(response.status_code, 200)
