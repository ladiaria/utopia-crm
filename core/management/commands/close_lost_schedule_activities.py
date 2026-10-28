import csv
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from core.choices import ACTIVITY_STATUS, CAMPAIGN_RESOLUTION_CHOICES, CAMPAIGN_STATUS, SALE_RESOLUTIONS
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

# CSV columns, in order. The header is translated when the file is written (see csv_header), and the values are
# the labels of the choices, not their codes: the CSV is meant to be audited by people who do not know the model.
# "Today" goes before "after closing", so a row does not read as if the contact were already closed.
CSV_COLUMNS = (
    "activity_datetime",
    "seller",
    "seller_internal",
    "campaign_name",
    "campaign_active",
    "contact_id",
    "contact_name",
    "ccs_status_before",
    "ccs_resolution_before",
    "ccs_status_after",
    "ccs_resolution_after",
    "activity_id",
)


class Command(BaseCommand):
    help = (
        "Closes campaign schedules (pending or expired call activities tied to a campaign) older than a given "
        "date, and closes their ContactCampaignStatus with the 'LS' (closed due to lost schedule) resolution. "
        "The campaign status is mapped conditionally: contacts we actually spoke to end as 'Ended with contact', "
        "the rest as 'Ended without contact'. Already terminal statuses and sales are never overwritten. "
        "With --verbosity 0 it only prints anomalies, so a cron only mails when something needs attention."
    )

    def add_arguments(self, parser):
        # No default on purpose: nobody should close schedules by accident.
        cutoff_group = parser.add_mutually_exclusive_group(required=True)
        cutoff_group.add_argument(
            "--date",
            type=str,
            help="Date in YYYY-MM-DD format. Schedules on that date or older will be closed (the date is included).",
        )
        cutoff_group.add_argument(
            "--days",
            type=int,
            help="Close schedules dated N days ago or older. Same as --date with that date, meant for a daily cron.",
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
        self.verbosity = options["verbosity"]
        cutoff = self.get_cutoff(self.get_cutoff_date(options["date"], options["days"]))

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
            if self.verbosity >= 1:
                self.stdout.write(self.style.WARNING("No schedules to close with the given parameters."))
            return

        statuses_by_pair = self.get_statuses_by_pair(activities)

        note = _("Automatically closed due to lost schedule ({}).").format(timezone.now().date().strftime("%Y-%m-%d"))

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
            if self.verbosity >= 1:
                self.stdout.write(self.style.WARNING("DRY RUN: nothing was written."))
            return

        if self.verbosity >= 1:
            self.warn_not_a_dry_run(activities, statuses_to_update, options["csv_path"])

        with transaction.atomic():
            # bulk_update on purpose: ContactCampaignStatus.last_action_date is auto_now, and save()
            # would overwrite the date of the last real action on every row.
            Activity.objects.bulk_update(activities, ["status", "seller_console_action", "notes"], batch_size=500)
            ContactCampaignStatus.objects.bulk_update(
                list(statuses_to_update.values()),
                ["status", "campaign_resolution", "last_console_action"],
                batch_size=500,
            )

        if self.verbosity >= 1:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Closed {len(activities)} schedules and updated {len(statuses_to_update)} campaign statuses."
                )
            )

    def warn_not_a_dry_run(self, activities, statuses_to_update, csv_path):
        """
        Warns, right before writing, that this run is closing schedules for real.

        --csv and --dry-run are independent: asking for the CSV does not turn the run into a
        preview, and that reads like a dry run to anyone who forgets the other flag.
        """
        if csv_path:
            self.stdout.write(self.style.WARNING("The CSV was written, but this is NOT a dry run."))
        self.stdout.write(
            self.style.WARNING(
                f"Closing {len(activities)} schedules and updating {len(statuses_to_update)} campaign statuses "
                "now. Re-run with --dry-run to only preview the changes."
            )
        )

    def get_cutoff_date(self, date_str, days):
        """
        Returns the cutoff day from --date, or from --days counting back from today.
        """
        if days is not None:
            if days < 0:
                raise CommandError("--days cannot be negative.")
            return date.today() - timedelta(days=days)
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise CommandError("Invalid date format. Please use YYYY-MM-DD format.")

    def get_cutoff(self, cutoff_date):
        """
        Returns the end of the given day, so --date 2026-05-31 includes everything scheduled on the 31st.
        """
        cutoff = datetime.combine(cutoff_date, time.max)
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
        seller = activity.seller
        return {
            "activity_datetime": activity.datetime.strftime("%Y-%m-%d %H:%M") if activity.datetime else "",
            "seller": seller.name if seller else "",
            "seller_internal": self.yes_no(seller.internal) if seller else "",
            "campaign_name": activity.campaign.name,
            "campaign_active": self.yes_no(activity.campaign.active),
            "contact_id": activity.contact_id,
            "contact_name": activity.contact.name if activity.contact else "",
            # A schedule without a ContactCampaignStatus has neither status nor resolution: both columns stay empty.
            "ccs_status_before": self.status_label(status_before),
            "ccs_resolution_before": self.resolution_label(resolution_before) if status_before else "",
            "ccs_status_after": self.status_label(status_after),
            "ccs_resolution_after": self.resolution_label(resolution_after) if status_after else "",
            "activity_id": activity.id,
        }

    def status_label(self, status):
        return str(CAMPAIGN_STATUS(status).label) if status else ""

    def resolution_label(self, resolution):
        if not resolution:
            return _("(no resolution)")
        return str(dict(CAMPAIGN_RESOLUTION_CHOICES).get(resolution, resolution))

    def yes_no(self, value):
        return _("Yes") if value else _("No")

    def csv_header(self):
        return {
            "activity_datetime": _("Schedule date"),
            "seller": _("Seller"),
            "seller_internal": _("Internal seller"),
            "campaign_name": _("Campaign"),
            "campaign_active": _("Active campaign"),
            "contact_id": _("Contact ID"),
            "contact_name": _("Contact"),
            "ccs_status_before": _("Status today"),
            "ccs_resolution_before": _("Resolution today"),
            "ccs_status_after": _("Status after closing"),
            "ccs_resolution_after": _("Resolution after closing"),
            "activity_id": _("Activity ID"),
        }

    def print_summary(self, activities, statuses_by_pair, statuses_to_update, rows):
        pairs = {(activity.contact_id, activity.campaign_id) for activity in activities}
        without_ccs = [pair for pair in pairs if pair not in statuses_by_pair]
        already_terminal = len(pairs) - len(statuses_to_update) - len(without_ccs)

        if self.verbosity >= 1:
            self.stdout.write(f"Activities to close: {len(activities)} ({len(pairs)} contact/campaign pairs)")
            self.print_transitions(statuses_to_update)
            self.stdout.write(f"  - Already terminal or with a sale (campaign status untouched): {already_terminal}")
        # Schedules without a campaign status are an anomaly: they are reported even with --verbosity 0.
        if self.verbosity >= 1 or without_ccs:
            self.stdout.write(f"  - Without ContactCampaignStatus (only the activity is closed): {len(without_ccs)}")
        for contact_id, campaign_id in sorted(without_ccs):
            self.stdout.write(self.style.WARNING(f"    contact {contact_id} / campaign {campaign_id}"))

    def print_transitions(self, statuses_to_update):
        """
        One line per terminal status, with the labels of the statuses that end there, built from STATUS_MAP:
        "Not yet contacted, Called, could not contact -> Ended without contact (Closed due to lost schedule): 3"
        """
        sources_by_target = {}
        for source, target in STATUS_MAP.items():
            sources_by_target.setdefault(target, []).append(source)
        resolution = self.resolution_label(LOST_SCHEDULE_RESOLUTION)
        for target in sorted(sources_by_target):
            sources = ", ".join(str(CAMPAIGN_STATUS(source).label) for source in sources_by_target[target])
            count = sum(1 for ccs in statuses_to_update.values() if ccs.status == target)
            self.stdout.write(f"  - {sources} -> {CAMPAIGN_STATUS(target).label} ({resolution}): {count}")

    def write_csv(self, path, rows):
        # utf-8-sig adds the BOM that Excel needs to read the accents right.
        with open(path, "w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
            writer.writerow(self.csv_header())
            writer.writerows(rows)
        if self.verbosity >= 1:
            self.stdout.write(self.style.SUCCESS(f"Wrote {len(rows)} rows to {path}"))
