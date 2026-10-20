import logging

from django.conf import settings
from django.core.mail import mail_managers, send_mail
from django.db import transaction
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import gettext as _

from core.models import Address
from support.models import ScheduledTask

logger = logging.getLogger(__name__)


@receiver(pre_delete, sender=Address)
def address_pre_delete_pending_address_changes(sender, instance, **kwargs):
    """
    Deleting an address leaves the pending address changes that pointed to it with no address (SET_NULL): they are
    not executed until someone gives them a new one. Tell someone once, now, instead of every day from the command.
    """
    task_ids = list(
        ScheduledTask.objects.filter(address=instance, category="AC", completed=False).values_list("id", flat=True)
    )
    if not task_ids:
        return
    # The address is gone by the time the transaction commits
    address = f"{instance.address_1 or ''} {instance.address_2 or ''}".strip()
    transaction.on_commit(
        lambda: notify_address_change_without_address(task_ids, address), using=kwargs.get("using")
    )


def notify_address_change_without_address(task_ids, address):
    """A mail server problem must never take down the delete that triggered this."""
    try:
        # Deleting the whole contact deletes its tasks too: then there is nothing left to warn about
        tasks = list(
            ScheduledTask.objects.filter(id__in=task_ids, address__isnull=True, completed=False)
            .select_related("contact")
            .prefetch_related("subscription_products__product")
            .order_by("execution_date", "id")
        )
        if not tasks:
            return
        contact = tasks[0].contact
        base_url = getattr(settings, "SCHEDULED_TASK_NOTIFY_BASE_URL", "") or ""
        subject = _("Pending address change left without an address: %(name)s (%(id)s)") % {
            "name": contact.get_full_name(),
            "id": contact.id,
        }
        body = "\n".join(
            [
                _("Contact: %(name)s (%(id)s)") % {"name": contact.get_full_name(), "id": contact.id},
                _("Deleted address: %(address)s") % {"address": address},
                "",
                _("These address changes were pending and pointed to it:"),
                *[
                    f"#{task.id} ({task.execution_date:%Y-%m-%d}): "
                    + ", ".join(sp.product.name for sp in task.subscription_products.all())
                    for task in tasks
                ],
                "",
                _(
                    "They will not be executed until they have an address: the products keep the one they have now. "
                    "Give them a new address or delete them."
                ),
                "",
                *[base_url + reverse("admin:support_scheduledtask_change", args=[task.id]) for task in tasks],
                base_url + reverse("contact_detail", args=[contact.id]),
            ]
        )
        recipients = getattr(settings, "SCHEDULED_TASK_NOTIFY_RECIPIENTS", None)
        if recipients:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True)
        else:
            mail_managers(subject, body, fail_silently=True)
    except Exception:
        logger.exception("Could not notify about address changes left without an address (tasks %s)", task_ids)
