# coding=utf-8
import re
import traceback
import json

from django.conf import settings
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.forms import ValidationError

from .models import (
    Address,
    Contact,
    Subscription,
    regex_alphanumeric,
    regex_alphanumeric_msg,
    update_web_user,
    update_web_user_newsletters,
)
from .forms import no_email_validation_msg
from .utils import cms_rest_api_request, mail_managers_on_errors


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
        instance.old_email = saved_email
    except Contact.DoesNotExist:
        # do nothing on the new ones
        pass


@receiver(post_save, sender=Contact)
def contact_post_save_signal(sender, instance, created, **kwargs):
    if created:
        update_web_user(instance, method="POST" if settings.WEB_CREATE_USER_ENABLED else "PUT")
    else:
        target_email = instance.old_email if hasattr(instance, 'old_email') else None
        update_web_user(instance, target_email)
    update_web_user_newsletters(instance)


@receiver(post_save, sender=Subscription)
def subscription_post_save_signal(sender, instance, **kwargs):
    # Adds history entries when subscriptions gets deactivated (or deactivated on pause).
    contact = instance.contact
    if instance.active is False:
        for product in instance.products.all():
            contact.add_product_history(instance, product, 'P' if instance.status == 'PA' else 'I', instance.campaign)


# Address signals.
# TODO: do test cases using the matrix below:
#
# operation | contact field transition | default field transition | expected result
# ---------------------------------------------------------------------------------
# create    | unchanged (blank)        | any                      | None
# create    | changed (blank -> value) | unchanged (False)        | None
# create    | changed (blank -> value) | changed (False -> True)  | api-call
# ---------------------------------------------------------------------------------
# update    | unchanged (blank)        | any                      | None
# update    | changed (blank -> value) | unchanged (False)        | None
# update    | changed (blank -> value) | changed (False -> True)  | api-call
# update    | changed (blank -> value) | unchanged (True)         | api-call
# update    | changed (blank -> value) | changed (True -> False)  | None
# update    | unchanged (value)        | unchanged (False)        | None
# update    | unchanged (value)        | changed (False -> True)  | api-call
# update    | unchanged (value)        | unchanged (True)         | api-call
# update    | unchanged (value)        | changed (True -> False)  | api-call
# update    | changed (value -> value) | unchanged (False)        | None
# update    | changed (value -> value) | changed (False -> True)  | api-call
# update    | changed (value -> value) | unchanged (True)         | 2 api-calls
# update    | changed (value -> value) | changed (True -> False)  | api-call
# update    | changed (value -> blank) | unchanged (False)        | None
# update    | changed (value -> blank) | changed (False -> True)  | api-call
# update    | changed (value -> blank) | unchanged (True)         | api-call
# update    | changed (value -> blank) | changed (True -> False)  | api-call
# ---------------------------------------------------------------------------------
# delete    | unchanged (blank)        | any                      | None
# delete    | unchanged (value)        | unchanged (False)        | None
# delete    | unchanged (value)        | unchanged (True)         | api-call


@receiver(pre_save, sender=Address)
def address_pre_save_signal(sender, instance, **kwargs):
    if settings.WEB_UPDATE_USER_ENABLED:
        if instance.pk and not hasattr(instance, "cms_updated"):
            old_instance = Address.objects.get(id=instance.id)
            old_contact, instance.default_changed = old_instance.contact, old_instance.default != instance.default
            if old_contact:
                if old_contact != instance.contact:
                    instance.old_contact = old_contact
                elif hasattr(instance, "old_contact"):
                    del instance.old_contact
            else:
                if instance.contact:
                    instance.old_contact = None
                elif hasattr(instance, "old_contact"):
                    del instance.old_contact
            if settings.DEBUG:
                print("DEBUG: address_pre_save_signal end")


def cms_address_values(address):
    return json.dumps(
        {
            "address_1": address.address_1,
            "city_fk": address.city_fk.name if address.city_fk else None,
            "country": address.country_name,
            "state": address.state_name,
        } if address else {"address_1": None, "city_fk": None, "country": None, "state": None}
    )


def cms_address_api_call(contact, address=None):
    if not getattr(settings, "WEB_ADDRESS_SYNC_ENABLED", True):
        return
    data = {"contact_id": contact.id, "fields": cms_address_values(address)}
    cms_rest_api_request("address_post_save", settings.WEB_UPDATE_USER_URI, data, "PATCH")


@receiver(post_save, sender=Address)
def address_post_save(sender, instance, created, **kwargs):
    if settings.DEBUG:
        print("DEBUG: address_post_save, instance: %s, created: %s" % (instance, created))
    if settings.WEB_UPDATE_USER_ENABLED:
        cms_updated = hasattr(instance, "cms_updated")
        if cms_updated:
            del instance.cms_updated
        else:
            contact = instance.contact
            if created:
                if contact and instance.default:
                    cms_address_api_call(contact, instance)
            else:
                default_changed = getattr(instance, "default_changed", False)
                if hasattr(instance, "old_contact"):
                    old_contact = instance.old_contact
                    if old_contact:
                        # contact field changed: value -> value
                        if instance.default:
                            if default_changed:
                                # default changed: False -> True (this was not the default for the old contact), then
                                # only sync this default address for the new contact value
                                cms_address_api_call(contact, instance)
                            else:
                                # old contact has lost its default address and new contact has a default address
                                cms_address_api_call(old_contact)
                                cms_address_api_call(contact, instance)
                        elif default_changed:
                            # old contact has lost its default address (default True -> False)
                            cms_address_api_call(old_contact)
                    else:
                        # contact changed: None -> value, only if default is True needs to be synced
                        if instance.default:
                            cms_address_api_call(contact, instance)
                else:
                    # contact field was unchanged
                    if settings.DEBUG:
                        debug_data = {
                            "contact": contact, "default_changed": default_changed, "default": instance.default
                        }
                        print("DEBUG: address_post_save - %s" % debug_data)
                    if contact:
                        if instance.default:
                            # default is True, no matter if it changed or not, sync it
                            cms_address_api_call(contact, instance)
                        elif default_changed:
                            # default changed: True -> False (address lost its default, sync it)
                            # or also if inconsistent state of more than 1 default address, find it and sync it
                            args = (contact,)
                            try:
                                args += (contact.addresses.get(default=True),)
                            except (Address.DoesNotExist, Address.MultipleObjectsReturned):
                                pass
                            if settings.DEBUG:
                                print(f"DEBUG: address_post_save - args: {args}")
                            cms_address_api_call(*args)


@receiver(post_delete, sender=Address)
def address_post_delete_signal(sender, instance, **kwargs):
    if settings.WEB_UPDATE_USER_ENABLED and instance.contact and instance.default:
        cms_address_api_call(instance.contact)


# end Address signals.


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
            # TODO: maybe errors 404 can be silently ignored, evaluate and do it
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
