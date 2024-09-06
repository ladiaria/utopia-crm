# coding=utf-8
import re

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.forms import ValidationError

from .models import Contact, Subscription, regex_alphanumeric, regex_alphanumeric_msg, update_web_user
from .forms import no_email_validation_msg


alphanumeric = re.compile(regex_alphanumeric)


@receiver(pre_save, sender=Contact)
def contact_pre_save_signal(sender, instance, **kwargs):
    # TODO: These validations should be consistent with the ones defined in the model attrs.

    if instance.no_email and instance.email:
        raise ValidationError(no_email_validation_msg)

    if not alphanumeric.match(instance.name):
        raise ValidationError(regex_alphanumeric_msg)
    try:
        saved_email = Contact.objects.values_list("email", flat=True).get(pk=instance.id)
        print("new instance", instance.email, instance.name, instance.last_name, saved_email)
        instance.old_email = saved_email
    except Contact.DoesNotExist:
        # do nothing on the new ones
        pass
    instance.old_contact = instance


@receiver(post_save, sender=Contact)
def contact_post_save_signal(sender, instance, created, **kwargs):
    if created:
        update_web_user(instance.old_contact)
    else:
        target_email = instance.old_email if hasattr(instance, 'old_email') else None
        update_web_user(instance.old_contact, target_email)


@receiver(post_save, sender=Subscription)
def subscription_post_save_signal(sender, instance, **kwargs):
    # Adds history entries when subscriptions gets deactivated (or deactivated on pause).
    contact = instance.contact
    if instance.active is False:
        for product in instance.products.all():
            contact.add_product_history(instance, product, 'P' if instance.status == 'PA' else 'I', instance.campaign)
