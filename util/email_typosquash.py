from pydoc import locate

from validate_email_address import validate_email
from pymailcheck import split_email, suggest

from django.conf import settings
from django.core.mail import mail_managers
from django.utils.translation import gettext as _

from core.models import EmailReplacement


def replacement_request_add(domain, replacement, target_obj=None):
    notify = False
    try:
        obj = EmailReplacement.objects.get(domain=domain)
    except EmailReplacement.DoesNotExist:
        EmailReplacement.objects.create(domain=domain, replacement=replacement, status="requested")
        notify = True
    else:
        if obj.status == "suggested":
            obj.status = "requested"
            obj.save()
            notify = True
    if notify:
        # TODO: include 3 links in the email to approve/reject (new views to make) and another to the object_list
        email_body = "%s ==> %s" % (domain, replacement)
        if target_obj:
            email_body += "\nfor %s: %s (id=%s)" % (type(target_obj), target_obj, target_obj.pk or "new_instance")
        mail_managers(_("A new email replacement request is pending approval"), email_body, True)


def clean_email(email):
    """
    If the email received is not whitelisted or not have a valid domain, email returned will be the email given
    replacing the domain with the replacement existing on our replacement list.
    @returns: a dict with:
      valid: bool,
      email: original email
      replaced: email replaced if match any replacement
      suggestion: suggested email to be used
    """
    splitted = split_email(email)
    domain, whitelisted_domains = splitted["domain"], getattr(settings, "CORE_WHITELISTED_DOMAINS", [])
    if type(whitelisted_domains) is str:
        whitelisted_domains = locate(whitelisted_domains)()
    whitelisted = domain in whitelisted_domains

    valid = whitelisted or bool(validate_email(email, True))
    result = {"valid": valid, "email": email}

    if not whitelisted:
        replacements = EmailReplacement.approved()
        replacement = replacements.get(domain) if replacements else None
        replaced = "%s@%s" % (splitted["address"], replacement) if replacement else None

        if replaced:
            result["replacement"] = replaced
        elif not valid:
            suggestion = suggest(email)
            if suggestion and not EmailReplacement.is_rejected(domain, suggestion["domain"]):
                result["suggestion"] = suggestion["full"]

    return result
