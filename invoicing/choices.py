# coding=utf-8
from django.utils.translation import gettext_lazy as _


INVOICEITEM_TYPE_CHOICES = (
    ('I', _('Item')),
    ('D', _('Discount')),
    ('R', _('Surcharge')),
)

INVOICEITEM_DR_TYPE_CHOICES = (
    ('1', _('Value')),
    ('2', _('Percentage')),
)
