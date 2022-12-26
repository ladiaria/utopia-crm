# coding=utf-8
from django.utils.translation import gettext_lazy as _

from django.dispatch import receiver
from django.db.models.signals import pre_save
from .models import Invoice

"""
@receiver(pre_save, sender=Invoice)
@receiver(pre_save, sender=InvoiceItem)
def table_changes_forbidden_signal(sender, instance, **kwargs):
    raise ValidationError(u"No se permiten cambios en esta tabla")
"""


@receiver(pre_save, sender=Invoice)
def invoice_pre_save_signal(sender, instance, **kwargs):
    return  # This should be migrated to a form instead of a signal
    if not instance.canceled:
        assert (
            (instance.paid or instance.debited) and instance.payment_date) or \
            (not instance.paid and not instance.debited and
                not instance.payment_date), _('A paid invoice must have a payment date and vice versa')
