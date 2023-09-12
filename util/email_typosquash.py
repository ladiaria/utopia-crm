from validate_email_address import validate_email
from pymailcheck import split_email, suggest

from core.models import EmailReplacement


def email_replacement_add(domain, replacement):
    obj, created = EmailReplacement.objects.get_or_create(domain=domain, replacement=replacement)
    if created:
        # TODO: alert managers about a new request pending approve/reject
        pass


def clean_email(email):
    """
    If the email received does not have a valid domain, email returned will be the email given replacing the domain
    with the replacement existing on our replacement list.
    @returns: a dict with valid=bool, email=original or replaced email, suggestion=suggested email to be used.
    """
    splitted, replacements, result = split_email(email), EmailReplacement.approved(), {}

    domain = splitted["domain"]
    replacement = replacements.get(domain) if replacements else None
    replaced = "%s@%s" % (splitted["address"], replacement) if replacement else None

    if validate_email(email, True):
        result.update({"valid": True, "email": email})
        if replaced:
            # valid but present in our replacements (a valid domain which is considered by us as a typo)
            result["suggestion"] = replaced
    else:
        if replaced:
            # invalid but we know how to fix
            result.update({"valid": True, "email": replaced})
        else:
            # invalid, suggestion (if any) is given by pymailcheck module and no already rejected by us
            result["valid"], result["email"], suggestion = False, email, suggest(email)
            if suggestion and not EmailReplacement.is_rejected(domain, suggestion["domain"]):
                result["suggestion"] = suggestion["full"]
    return result
