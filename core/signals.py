# coding=utf-8
import re
try:
    import simplejson as json
except ImportError:
    import json  # noqa
from datetime import date
from dateutil.relativedelta import relativedelta

from django.utils.translation import gettext as _
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.forms import ValidationError

from .models import Contact, Subscription, regex_alphanumeric, regex_alphanumeric_msg


alphanumeric = re.compile(regex_alphanumeric)


@receiver(pre_save, sender=Contact)
def contact_pre_save_signal(sender, instance, **kwargs):
    # Estas validaciones deben estar acorde con las definidas en la
    # definición de los atributos, que al parecer se validan sólo en el
    # admin, o a veces ni siquiera en el admin.
    # Por otro lado estas se van a ejecutar siempre.
    # TODO: check this commented blocks

    # if instance.expiration_month or instance.expiration_year:
    #    try:
    #        date(
    #            int(instance.expiration_year), int(instance.expiration_month),
    #            1)
    #    except (ValueError, TypeError):
    #        raise ValidationError(u'Mes y año no válidos')

    # if instance.no_email and instance.email:
    #     raise ValidationError(
    #         u'Si no tiene email entonces se debe dejar en blanco el email')

    if not alphanumeric.match(instance.name):
        raise ValidationError(regex_alphanumeric_msg)


# TODO: check this
# @receiver(pre_save, sender=Ocupation)
# def table_changes_forbidden_signal(sender, instance, **kwargs):
#     raise ValidationError(u"No se permiten cambios en esta tabla")


@receiver(post_save, sender=Subscription)
def subscription_post_save_signal(sender, instance, **kwargs):
    # Adds history entries when subscriptions gets deactivated (or deactivated on pause).
    contact = instance.contact
    if instance.active is False:
        for product in instance.products.all():
            contact.add_product_history(instance, product, 'P' if instance.status == 'PA' else 'I', instance.campaign)
