# coding=utf-8
import requests
from requests.auth import HTTPBasicAuth

from django.contrib.auth.models import User
from django.conf import settings


class DummyStaffRequest(object):
    def __init__(self, staffusername):
        self.user = User.objects.get(username=staffusername)


def space_join(first_part, second_part):
    if first_part and second_part:
        return first_part + ' ' + second_part
    else:
        return first_part or second_part or ''
