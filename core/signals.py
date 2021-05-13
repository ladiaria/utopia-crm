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
from .forms import no_email_validation_msg


alphanumeric = re.compile(regex_alphanumeric)


@receiver(pre_save, sender=Contact)
def contact_pre_save_signal(sender, instance, **kwargs):
    # These validations should be consistent with the ones defined in the model attrs.

    if instance.no_email and instance.email:
        raise ValidationError(no_email_validation_msg)

    if not alphanumeric.match(instance.name):
        raise ValidationError(regex_alphanumeric_msg)


@receiver(post_save, sender=Subscription)
def subscription_post_save_signal(sender, instance, **kwargs):
    # Adds history entries when subscriptions gets deactivated (or deactivated on pause).
    contact = instance.contact
    if instance.active is False:
        for product in instance.products.all():
            contact.add_product_history(instance, product, 'P' if instance.status == 'PA' else 'I', instance.campaign)
