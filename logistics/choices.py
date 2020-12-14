# coding=utf-8

from django.utils.translation import ugettext_lazy as _

RESORT_STATUS_CHOICES = (
    ('AC', _('To be confirmed')),
    ('NL', _('We don\'t deliver there')),
    ('P', _('Door to door')),
    ('R', _('Withdrawal')),
)

MESSAGE_PLACES = (
    ('P', _('Prints')),
    ('L', _('Labels')),
)
