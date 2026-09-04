import csv
from datetime import datetime, time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from core.choices import ACTIVITY_STATUS, CAMPAIGN_STATUS, SALE_RESOLUTIONS
from core.models import Activity, ContactCampaignStatus
from support.models import SellerConsoleAction


# Slug of the SellerConsoleAction that marks a forced close. It is registered as inactive in
# populate_seller_console_actions so it cannot be triggered from the seller console.
LOST_SCHEDULE_ACTION_SLUG = "close-lost-schedule"

# Campaign resolution used for every ContactCampaignStatus closed by this command.
LOST_SCHEDULE_RESOLUTION = "LS"

# How the current campaign status maps to its terminal one. Statuses not in this map (4 and 5, which
# are already terminal) are left untouched: we only close the dangling activity.
STATUS_MAP = {
    CAMPAIGN_STATUS.NOT_YET_CONTACTED: CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT,
    CAMPAIGN_STATUS.CALLED_COULD_NOT_CONTACT: CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT,
    CAMPAIGN_STATUS.CONTACTED: CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
    CAMPAIGN_STATUS.SWITCH_TO_MORNING: CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
    CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON: CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
}

CSV_HEADER = (
    "activity_id",
    "contact_id",
    "contact_name",
    "campaign_id",
    "campaign_name",
    "seller",
    "activity_datetime",
    "ccs_status_before",
    "ccs_status_after",
    "ccs_resolution_before",
    "ccs_resolution_after",
)


class Command(BaseCommand):
    help = (
        "Closes campaign schedules (pending or expired call activities tied to a campaign) older than a given "
        "date, and closes their ContactCampaignStatus with the 'LS' (closed due to lost schedule) resolution. "
        "The campaign status is mapped conditionally: contacts we actually spoke to end as 'Ended with contact', "
        "the rest as 'Ended without contact'. Already terminal statuses and sales are never overwritten."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            required=True,
            help="Date in YYYY-MM-DD format. Schedules on that date or older will be closed (the date is included).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without writing anything.",
        )
        parser.add_argument(
            "--csv",
            type=str,
            dest="csv_path",
            help="Dump the affected rows to this path so they can be audited before running for real.",
        )
        parser.add_argument(
            "--campaign",
            type=int,
            dest="campaign_id",
            help="Only close schedules of this campaign id.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Only process the first N activities.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        cutoff = self.get_cutoff(options["date"])

        try:
            seller_action = SellerConsoleAction.objects.get(slug=LOST_SCHEDULE_ACTION_SLUG)
        except SellerConsoleAction.DoesNotExist:
            raise CommandError(
                f"SellerConsoleAction with slug '{LOST_SCHEDULE_ACTION_SLUG}' does not exist. "
                "Please run 'python manage.py populate_seller_console_actions' first."
            )

        activities = (
            Activity.objects.filter(
                status__in=[ACTIVITY_STATUS.PENDING, ACTIVITY_STATUS.EXPIRED],
                activity_type="C",
                campaign__isnull=False,
                datetime__lte=cutoff,
            )
            .select_related("contact", "campaign", "seller")
            .order_by("datetime", "id")
        )
        if options["campaign_id"]:
            activities = activities.filter(campaign_id=options["campaign_id"])
        if options["limit"]:
            activities = activities[: options["limit"]]

        activities = list(activities)
        if not activities:
            self.stdout.write(self.style.WARNING("No schedules to close with the given parameters."))
            return

        statuses_by_pair = self.get_statuses_by_pair(activities)

        note = _("Automatically closed due to lost schedule (t1175, {}).").format(
            timezone.now().date().strftime("%Y-%m-%d")
        )

        rows, statuses_to_update = [], {}
        for activity in activities:
            pair = (activity.contact_id, activity.campaign_id)
            ccs = statuses_by_pair.get(pair)
            status_before = ccs.status if ccs else None
            resolution_before = ccs.campaign_resolution if ccs else None
            status_after, resolution_after = status_before, resolution_before

            # A pair may have more than one dangling schedule: the status is only mapped once.
            if ccs and pair not in statuses_to_update and self.can_be_closed(ccs):
                ccs.status = STATUS_MAP[ccs.status]
                ccs.campaign_resolution = LOST_SCHEDULE_RESOLUTION
                ccs.last_console_action = seller_action
                statuses_to_update[pair] = ccs
            if ccs:
                status_after, resolution_after = ccs.status, ccs.campaign_resolution

            activity.status = ACTIVITY_STATUS.COMPLETED
            activity.seller_console_action = seller_action
            activity.notes = f"{activity.notes}\n{note}" if activity.notes else note

            rows.append(self.build_row(activity, status_before, status_after, resolution_before, resolution_after))

        self.print_summary(activities, statuses_by_pair, statuses_to_update, rows)

        if options["csv_path"]:
            self.write_csv(options["csv_path"], rows)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: nothing was written."))
            return

        with transaction.atomic():
            # bulk_update on purpose: ContactCampaignStatus.last_action_date is auto_now, and save()
            # would overwrite the date of the last real action on every row.
            Activity.objects.bulk_update(activities, ["status", "seller_console_action", "notes"], batch_size=500)
            ContactCampaignStatus.objects.bulk_update(
                list(statuses_to_update.values()),
                ["status", "campaign_resolution", "last_console_action"],
                batch_size=500,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Closed {len(activities)} schedules and updated {len(statuses_to_update)} campaign statuses."
            )
        )

    def get_cutoff(self, date_str):
        """
        Returns the end of the given day, so --date 2026-05-31 includes everything scheduled on the 31st.
        """
        try:
            parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise CommandError("Invalid date format. Please use YYYY-MM-DD format.")
        cutoff = datetime.combine(parsed, time.max)
        return timezone.make_aware(cutoff) if settings.USE_TZ else cutoff

    def get_statuses_by_pair(self, activities):
        """
        Returns a {(contact_id, campaign_id): ContactCampaignStatus} dict for every activity, in a single query.
        """
        contact_ids = {activity.contact_id for activity in activities}
        campaign_ids = {activity.campaign_id for activity in activities}
        pairs = {(activity.contact_id, activity.campaign_id) for activity in activities}
        statuses = ContactCampaignStatus.objects.filter(contact_id__in=contact_ids, campaign_id__in=campaign_ids)
        return {
            (ccs.contact_id, ccs.campaign_id): ccs for ccs in statuses if (ccs.contact_id, ccs.campaign_id) in pairs
        }

    def can_be_closed(self, ccs):
        """
        A campaign status is only closed when it is not terminal yet and does not hold a sale.
        """
        return ccs.status in STATUS_MAP and ccs.campaign_resolution not in SALE_RESOLUTIONS

    def build_row(self, activity, status_before, status_after, resolution_before, resolution_after):
        return {
            "activity_id": activity.id,
            "contact_id": activity.contact_id,
            "contact_name": activity.contact.name if activity.contact else "",
            "campaign_id": activity.campaign_id,
            "campaign_name": activity.campaign.name,
            "seller": activity.seller.name if activity.seller else "",
            "activity_datetime": activity.datetime.strftime("%Y-%m-%d %H:%M") if activity.datetime else "",
            "ccs_status_before": status_before or "",
            "ccs_status_after": status_after or "",
            "ccs_resolution_before": resolution_before or "",
            "ccs_resolution_after": resolution_after or "",
        }

    def print_summary(self, activities, statuses_by_pair, statuses_to_update, rows):
        pairs = {(activity.contact_id, activity.campaign_id) for activity in activities}
        ended_with_contact = sum(
            1 for ccs in statuses_to_update.values() if ccs.status == CAMPAIGN_STATUS.ENDED_WITH_CONTACT
        )
        ended_without_contact = len(statuses_to_update) - ended_with_contact
        without_ccs = [pair for pair in pairs if pair not in statuses_by_pair]
        already_terminal = len(pairs) - len(statuses_to_update) - len(without_ccs)

        self.stdout.write(f"Activities to close: {len(activities)} ({len(pairs)} contact/campaign pairs)")
        self.stdout.write(f"  - Status 2/6/7 -> 4 (ended with contact), resolution LS: {ended_with_contact}")
        self.stdout.write(f"  - Status 1/3 -> 5 (ended without contact), resolution LS: {ended_without_contact}")
        self.stdout.write(f"  - Already terminal or with a sale (campaign status untouched): {already_terminal}")
        self.stdout.write(f"  - Without ContactCampaignStatus (only the activity is closed): {len(without_ccs)}")
        for contact_id, campaign_id in sorted(without_ccs):
            self.stdout.write(self.style.WARNING(f"    contact {contact_id} / campaign {campaign_id}"))

    def write_csv(self, path, rows):
        with open(path, "w", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=CSV_HEADER)
            writer.writeheader()
            writer.writerows(rows)
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(rows)} rows to {path}"))
