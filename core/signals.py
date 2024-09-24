# coding=utf-8
import re
import traceback
from django.conf import settings
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.forms import ValidationError

from .models import Contact, Subscription, regex_alphanumeric, regex_alphanumeric_msg, update_web_user
from .forms import no_email_validation_msg
from .utils import cms_rest_api_request, mail_managers_on_errors


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


@receiver(post_delete, sender=Contact)
def contact_post_delete(sender, instance, **kwargs):
    """
    Call CMS to delete the "peer" user of this contact, if the CMS refuses to delete, the sync enters in
    inconsistency state (because this "peer" instance has already been deleted from the CRM).
    When this happen, managers should be notified and actions should be taken by hand, maybe also a good idea
    is to tag the user in CMS for easier identification and further back-to-consistency actions.
    """
    if settings.DEBUG:
        print("DEBUG: contact deletion post_delete signal executed (not implemented yet)")

    if settings.WEB_CREATE_USER_ENABLED and not getattr(instance, "updatefromweb", False):
        # Define the URL of the external service
        url = settings.WEB_DELETE_USER_URI
        data = {'contact_id': instance.id, 'email': instance.email}
        try:
            res = cms_rest_api_request("contact_post_delete", url, data, "DELETE")
            if isinstance(res, str) and res in ("TIMEOUT", "ERROR"):
                raise Exception(f"CMS server responds with error when we tried to remove contact_id: {instance.id}")
            elif not hasattr(res, "msg", None) or res.get("msg") != "OK":
                raise Exception("Something when wrong or unexpected when we tried to remove contact_id: {instance.id}")
        except Exception as ex:
            process_name = "Sync for delete on CMS"
            mail_managers_on_errors(process_name, str(ex), traceback.format_exc())
            print(f"Error sending delete request: {ex} trace: {traceback.format_exc()}")
