# coding=utf-8
from builtins import range
import string
import random

from django.contrib.auth.models import User


class DummyStaffRequest(object):
    def __init__(self, staffusername):
        self.user = User.objects.get(username=staffusername)


def space_join(first_part, second_part):
    if first_part and second_part:
        return first_part + ' ' + second_part
    else:
        return first_part or second_part or ''


def rand_chars(length=9):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))
