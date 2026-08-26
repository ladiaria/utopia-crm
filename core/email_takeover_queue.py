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
        takeover_request = EmailTakeoverRequest.objects.create(
            contact=contact,
            requested_email=email,
            preview_detail=preview_detail or {},
            origin=origin,
            requested_by=requested_by,
        )
        _notify_reviewers(takeover_request)
        return takeover_request
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


def queue_takeover_on_conflict(contact, user=None, origin=None):
    """
    Opt this contact save in to the queue.

    Without this the save behaves exactly as it always has (the CMS veto blocks it), which is what
    every batch job and management command should keep doing -- an import must not file hundreds of
    requests. Views that have a human in front of them call this before ``contact.save()`` and
    ``notify_takeover_queued()`` after it.
    """
    contact._takeover_enqueue = True
    contact._takeover_requested_by = user if (user is not None and user.is_authenticated) else None
    contact._takeover_origin = origin or EmailTakeoverRequest.ORIGIN_OTHER
    return contact


def takeover_queued_email(contact):
    """The email that went to the queue on the last save, if any. Consumes the mark."""
    queued = getattr(contact, "takeover_queued", None)
    if queued:
        del contact.takeover_queued
    return queued


def notify_takeover_queued(request, contact):
    """
    Tell the operator what happened to the email change: it was not applied, it was not lost, and
    it is not their call. Everything else they edited was saved.
    """
    from django.contrib import messages

    queued = takeover_queued_email(contact)
    if queued:
        messages.info(
            request,
            _(
                "The email could not be changed to %(email)s: another web account is using that address. "
                "The change was filed for a supervisor to review. Everything else was saved."
            )
            % {"email": queued},
        )
    return queued


def queue_takeover_after_create(contact, user=None):
    """
    File a request for a contact that was just created with an email the web says is taken.

    Creation is the one path where the CRM never asks the CMS: ``Contact.clean()`` only calls it
    ``if ... and self.id``, and during a create there is no id yet. So the contact is created no
    matter what the web says -- and that is the right outcome, the contact is the commercial entity
    and a web account holding its address is no reason for the person not to exist in the CRM. What
    is wrong today is that the conflict is *silent*: two identities for one person, and nobody finds
    out until something tries to create the web account.

    This runs the check right after the create, id in hand, and files a request if a takeover would
    fix it. Note the difference with an edit: here the email STAYS on the contact. Nothing is
    discarded, because nothing is in dispute on the CRM side.

    Usually the CMS answers ``attach_only`` for these -- the fresh contact has no web account of
    its own, so approving only links the orphan account to it, with nothing merged and nothing
    deleted. It still goes through the queue: the operator typed that address, and the guards
    cannot tell a typo, or somebody else's account, from the person's own.

    Never raises: a contact that was created stays created.
    """
    try:
        if not (takeover_queue_enabled() and contact.id and contact.email):
            return None
        if not getattr(settings, "WEB_UPDATE_USER_ENABLED", False):
            return None
        # Asking validateEmailOnWeb first would be useless here: it answers OK without looking at
        # the email whenever the contact has no web account of its own, and a contact that was just
        # created never has one. So the takeover preview is asked directly -- it is the one that
        # knows this shape (no account for the contact + an orphan holding the address) and answers
        # `attach_only`. It is also stricter than the check: with no orphan it returns NO_ORPHAN, so
        # nothing is filed for an address that is simply free.
        preview = preview_takeover(contact.id, contact.email)
        if not isinstance(preview, dict) or preview.get("retval") != 1:
            # Either the web is down or a takeover cannot fix this one. Nothing is filed: an
            # unresolvable request would sit in the queue with no action a reviewer could take.
            return None
        return enqueue_takeover(
            contact,
            contact.email,
            preview.get("detail"),
            origin=EmailTakeoverRequest.ORIGIN_CREATE_CONTACT,
            requested_by=user if (user is not None and user.is_authenticated) else None,
        )
    except Exception:
        logger.exception("Could not check the web for a conflict after creating contact %s", contact.id)
        return None


def notify_takeover_after_create(request, takeover_request):
    """Tell the operator the contact was created and the web link is waiting for review."""
    from django.contrib import messages

    if takeover_request:
        messages.info(
            request,
            _(
                "The contact was created. On the web, %(email)s belongs to another account, so linking "
                "them was filed for a supervisor to review."
            )
            % {"email": takeover_request.requested_email},
        )
    return takeover_request


def _notify_reviewers(takeover_request):
    """
    Let the people who can resolve requests know one arrived, so nobody has to watch the sidebar.

    Defensive by design: a mail server problem must never take down the contact save that filed the
    request.
    """
    try:
        from django.core.mail import mail_managers, send_mail
        from django.urls import reverse

        contact = takeover_request.contact
        # The email the contact HAS, read from the database, not from the instance in memory: on an
        # edit that instance is still carrying the address being requested (custom_clean discards it
        # right after filing this), and printing it as "current" leaves the reviewer comparing an
        # address against itself. On a create it reads the saved one, which is the right answer too.
        current_email = contact.get_old_email() or "-"
        base_url = getattr(settings, "EMAIL_TAKEOVER_NOTIFY_BASE_URL", "") or ""
        queue_url = base_url + reverse("email_takeover_queue")
        what_it_does = (
            _(
                "Approving merges the two web accounts: everything useful from the old one "
                "(newsletters included) moves to the one that stays, and only then is the old one "
                "deleted. Newsletters are merged, never replaced."
            )
            if takeover_request.deletes_an_account
            else _("Approving only links the web account. Nothing is deleted and nothing moves.")
        )
        subject = _("Email takeover request: %(email)s") % {"email": takeover_request.requested_email}
        body = "\n".join(
            [
                _("Contact: %(name)s (%(id)s)") % {"name": contact.get_full_name(), "id": contact.id},
                _("Current email: %(email)s") % {"email": current_email},
                _("Requested email: %(email)s") % {"email": takeover_request.requested_email},
                _("Origin: %(origin)s") % {"origin": takeover_request.get_origin_display()},
                _("Requested by: %(user)s") % {"user": takeover_request.requested_by or "-"},
                "",
                str(what_it_does),
                "",
                _("Resolve it here: %(url)s") % {"url": queue_url},
            ]
        )
        recipients = getattr(settings, "EMAIL_TAKEOVER_NOTIFY_RECIPIENTS", None)
        if recipients:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True)
        else:
            mail_managers(subject, body, fail_silently=True)
    except Exception:
        logger.exception("Could not notify reviewers about takeover request %s", takeover_request.id)
