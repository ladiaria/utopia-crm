from validate_email_address import validate_email
from pymailcheck import split_email, suggest

from core.models import EmailReplacement


def email_replacement_add(domain, replacement):
    obj, created = EmailReplacement.objects.get_or_create(domain=domain, replacement=replacement)
    if created:
        print("TODO: alert managers about a new request pending approve/reject")


def clean_email(email):
    """
    If the email received does not have a valid domain, email returned will be the email given replacing the domain
    with the replacement existing on our replacement list.
    @returns: a dict with:
      valid: bool,
      email: original email
      replaced: email replaced if match any replacement
      suggestion: suggested email to be used
    """
    splitted, replacements, valid = split_email(email), EmailReplacement.approved(), bool(validate_email(email, True))

    result, domain = {"valid": valid, "email": email}, splitted["domain"]
    replacement = replacements.get(domain) if replacements else None
    replaced = "%s@%s" % (splitted["address"], replacement) if replacement else None

    if replaced:
        result["replacement"] = replaced
    elif not valid:
        suggestion = suggest(email)
        if suggestion and not EmailReplacement.is_rejected(domain, suggestion["domain"]):
            result["suggestion"] = suggestion["full"]

    return result
