# coding=utf-8
import re
import traceback
from django.conf import settings
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.forms import ValidationError

from core.models import Contact, Subscription, regex_alphanumeric, regex_alphanumeric_msg, update_web_user
from core.forms import no_email_validation_msg
from core.utils import cms_rest_api_request, mail_managers_on_errors


alphanumeric = re.compile(regex_alphanumeric)


@receiver(pre_save, sender=Contact)
def contact_pre_save_signal(sender, instance, **kwargs):
    # TODO: These validations should be consistent with the ones defined in the model attrs.

    if instance.no_email and instance.email:
        raise ValidationError(no_email_validation_msg)

    if not alphanumeric.match(instance.name) and getattr(settings, "ENABLE_ALPHANUMERIC_VALIDATION_FOR_NAME", True):
        raise ValidationError(regex_alphanumeric_msg)
    try:
        saved_email = Contact.objects.values_list("email", flat=True).get(pk=instance.id)
        instance.old_email = saved_email  # NOTE: may be deprecated with the work i'll do for the next TODO
    except Contact.DoesNotExist:
        # do nothing on the new ones
        pass
    instance.old_contact = instance  # TODO: (fixing) this is a very bad OO mistake, instances are always the same ref.


@receiver(post_save, sender=Contact)
def contact_post_save_signal(sender, instance, created, **kwargs):
    if created:
        update_web_user(instance.old_contact, method="POST" if settings.WEB_CREATE_USER_ENABLED else "PUT")
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
    if settings.WEB_CREATE_USER_ENABLED and not getattr(instance, "updatefromweb", False):
        # Define the URL of the external service
        uri = settings.WEB_DELETE_USER_URI
        data = {'contact_id': instance.id, 'email': instance.email}
        try:
            res = cms_rest_api_request("contact_post_delete", uri, data, "DELETE")
            if settings.DEBUG:
                print(f"DEBUG: (contact_post_delete) cms_rest_api_request returned: {res}")
            if isinstance(res, str) and res in ("TIMEOUT", "ERROR"):
                raise Exception(res)
            elif res.get("msg") != "OK":
                raise Exception("internal error when tried to remove related CMS user")
        except Exception as ex:
            process_name = "Sync for delete on CMS"
            tb = traceback.format_exc()
            mail_managers_on_errors(process_name, str(ex), tb)
            if settings.DEBUG:
                print(f"ERROR: (contact_post_delete) sending delete request: {ex} trace: {tb}")
    elif settings.DEBUG and getattr(settings, "DEBUG_NOOP_SIGNALS", True):
        print("DEBUG: (contact_post_delete) signal called - noop")
