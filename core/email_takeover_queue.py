# coding=utf-8
"""
The email takeover queue: operators request, reviewers resolve.

When the CMS vetoes a contact's email because it belongs to another web account, the CRM does not
resolve it on the spot. Executing a takeover can delete a web account, and nothing in the CRM can
tell whether two addresses belong to the same person -- so the operator saving the contact only
files a request here, and someone holding ``core.can_takeover_email`` reviews it.

The flow, end to end:

    save contact -> CMS says the email is taken
      -> preview (confirm=0): would a takeover fix it? what exactly would it do?
         -> not resolvable  -> the operator sees the CMS's own readable message, nothing is queued
         -> resolvable      -> enqueue_takeover(): request stored with the preview,
                               the contact is saved WITHOUT the new email
      -> [later] a reviewer opens the queue and sees the preview
         -> approve_takeover(): executes against the CMS (confirm=1), and only if the CMS
            confirms, applies the email to the contact
         -> reject_takeover(): nothing is touched

Approval re-asks the CMS rather than trusting the stored preview: accounts can gain a subscription
or a ``contact_id`` between the request and its review, and the guards have to run against the
world as it is at execution time.
"""

import logging

from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import EmailTakeoverRequest
from .utils import emailTakeoverOnWeb


logger = logging.getLogger(__name__)

# Returned by resolve helpers so callers can tell apart "the CMS said no" from "the CMS did not
# answer": the first is a decision, the second is an outage and the request must stay pending.
RESOLVED, REFUSED, UNREACHABLE, FAILED = "resolved", "refused", "unreachable", "failed"


def takeover_queue_enabled():
    """
    The queue rides on the same kill switch as the takeover itself: with the switch off the CMS
    endpoint must not be called at all, so there is nothing to preview and nothing to queue, and
    the contact edit falls back to the plain block it has always had.
    """
    return bool(
        getattr(settings, "WEB_EMAIL_TAKEOVER_ENABLED", False) and getattr(settings, "WEB_EMAIL_TAKEOVER_URI", None)
    )


def preview_takeover(contact_id, email):
    """
    Ask the CMS what a takeover of ``email`` for ``contact_id`` would do, without touching
    anything. Returns the CMS response dict, or "TIMEOUT"/"ERROR".
    """
    return emailTakeoverOnWeb(contact_id, email, confirm=False)


def enqueue_takeover(contact, email, preview_detail=None, origin=None, requested_by=None):
    """
    File a pending request for ``contact`` to take over ``email``, or return the one already open.

    Never raises: a failure to queue must not take down the contact save that triggered it. Returns
    the request, or None if it could not be stored.
    """
    origin = origin or getattr(contact, "_takeover_origin", EmailTakeoverRequest.ORIGIN_OTHER)
    requested_by = requested_by or getattr(contact, "_takeover_requested_by", None)
    try:
        existing = EmailTakeoverRequest.objects.filter(
            contact=contact, requested_email=email, status=EmailTakeoverRequest.PENDING
        ).first()
        if existing:
            # Refresh the preview: the operator may be retrying days later, and a stale snapshot
            # is worse than none -- the reviewer decides by what it shows.
            if preview_detail:
                existing.preview_detail = preview_detail
                existing.save(update_fields=["preview_detail"])
            return existing
        return EmailTakeoverRequest.objects.create(
            contact=contact,
            requested_email=email,
            preview_detail=preview_detail or {},
            origin=origin,
            requested_by=requested_by,
        )
    except IntegrityError:
        # Lost a race against a concurrent save of the same contact: the other one queued it.
        return EmailTakeoverRequest.objects.filter(
            contact=contact, requested_email=email, status=EmailTakeoverRequest.PENDING
        ).first()
    except Exception:
        logger.exception("Could not queue an email takeover request for contact %s", contact.id)
        return None


def approve_takeover(takeover_request, user=None, note=""):
    """
    Execute the takeover on the CMS and, only if it confirms, apply the email to the contact.

    Returns ``(outcome, message)`` where outcome is one of RESOLVED / REFUSED / UNREACHABLE /
    FAILED. The request is only closed on RESOLVED: a refusal by the CMS or an outage leaves it
    pending, because both are states the reviewer may want to retry.
    """
    if not takeover_request.is_pending:
        return FAILED, _("This request was already resolved.")
    if not takeover_queue_enabled():
        return FAILED, _("Email takeovers are disabled.")

    contact, email = takeover_request.contact, takeover_request.requested_email
    run = emailTakeoverOnWeb(contact.id, email, confirm=True)

    if run in ("TIMEOUT", "ERROR") or not isinstance(run, dict):
        logger.warning("Takeover approval could not reach the CMS for request %s (%s)", takeover_request.id, run)
        return UNREACHABLE, _("The web did not answer. The request is still pending, try again.")

    if run.get("retval") != 1:
        # The CMS refused: staff account, active subscription, unmovable content, or the situation
        # changed since the preview. Its message is written for a human, so pass it through.
        return REFUSED, run.get("msg") or _("The web refused the takeover.")

    # The takeover happened. From here on the world already changed, so the request is closed even
    # if applying the email fails -- and that failure is recorded rather than swallowed.
    detail = run.get("detail") or {}
    takeover_request.status = EmailTakeoverRequest.APPROVED
    takeover_request.resolved_by = user
    takeover_request.resolved_at = timezone.now()
    takeover_request.preview_detail = detail or takeover_request.preview_detail
    takeover_request.resolution_note = note

    try:
        contact.email = email
        contact.save()
    except Exception as exc:
        logger.exception("Takeover ran on the CMS but the email could not be applied to contact %s", contact.id)
        takeover_request.resolution_note = (
            "%s\n%s" % (note, _("The takeover ran on the web but the email could not be saved: %s") % exc)
        ).strip()
        takeover_request.save()
        return FAILED, _("The takeover ran on the web, but the email could not be saved on the contact: %s") % exc

    takeover_request.save()
    return RESOLVED, _("Takeover done and email applied to the contact.")


def reject_takeover(takeover_request, user=None, note=""):
    """Close the request without touching anything on either side."""
    if not takeover_request.is_pending:
        return FAILED, _("This request was already resolved.")
    takeover_request.status = EmailTakeoverRequest.REJECTED
    takeover_request.resolved_by = user
    takeover_request.resolved_at = timezone.now()
    takeover_request.resolution_note = note
    takeover_request.save()
    return RESOLVED, _("Request rejected. Nothing was changed.")


def pending_takeover_count():
    """Pending requests, for the sidebar badge."""
    return EmailTakeoverRequest.objects.filter(status=EmailTakeoverRequest.PENDING).count()


def pending_takeover_for(contact, email):
    """The open request for this contact and email, if any. Used by the edit views to tell the
    operator that the change they are trying to make is already waiting for review."""
    return EmailTakeoverRequest.objects.filter(
        contact=contact, requested_email=email, status=EmailTakeoverRequest.PENDING
    ).first()
