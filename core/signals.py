# coding=utf-8
import re

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.forms import ValidationError

from .models import Contact, Subscription, regex_alphanumeric, regex_alphanumeric_msg, update_web_user
from .forms import no_email_validation_msg
from .utils import updatewebuser


alphanumeric = re.compile(regex_alphanumeric)


@receiver(pre_save, sender=Contact)
def contact_pre_save_signal(sender, instance, **kwargs):
    # TODO: These validations should be consistent with the ones defined in the model attrs.

    if instance.no_email and instance.email:
        raise ValidationError(no_email_validation_msg)

    if not alphanumeric.match(instance.name):
        raise ValidationError(regex_alphanumeric_msg)
    print("Se ejecuta la pre save del Contact !!!!!")
    try:
        print("pre save contact", instance.id, instance.email)
        saved_email = Contact.objects.values_list("email", flat=True).get(pk=instance.id)
        print("El contact email salvado es: ", saved_email)
        if instance.email != saved_email:
            instance.old_email = saved_email
    except Contact.DoesNotExist:
        # do nothin on the new ones
        print("no encontro al contacto!!!")
        pass


@receiver(post_save, sender=Contact)
def contact_post_save_signal(sender, instance, created, **kwargs):
    print("se ejecuta post save del Contact !!!")
    if created:
        print("post save de conacto creado:", instance.pk, instance.email)
        # updatewebuser(instance.id, instance.name, instance.email, instance.email)
        update_web_user(instance)
    else:
        target_email = instance.old_email if hasattr(instance, 'old_email') else None
        update_web_user(instance, target_email)

@receiver(post_save, sender=Subscription)
def subscription_post_save_signal(sender, instance, **kwargs):
    # Adds history entries when subscriptions gets deactivated (or deactivated on pause).
    contact = instance.contact
    if instance.active is False:
        for product in instance.products.all():
            contact.add_product_history(instance, product, 'P' if instance.status == 'PA' else 'I', instance.campaign)
