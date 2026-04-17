# coding=utf-8
"""
Management command to detect subscriptions that should have been activated
by `activate_subscriptions_by_start_date` but were missed.

This happens when a subscription is created *after* its start_date (e.g. created
on 2025-04-07 with start_date=2025-04-01): the nightly command only looks forward
up to one day ahead, so it never picks up past-due start dates.

Usage:
    # Report missed activations (dry run, no changes):
    python manage.py check_missed_subscription_activations
    python manage.py check_missed_subscription_activations --output /tmp/missed.csv
    python manage.py check_missed_subscription_activations --since 2025-01-01
    python manage.py check_missed_subscription_activations --months-threshold 6

    # Actually activate them:
    python manage.py check_missed_subscription_activations --activate --months-threshold 3

    # Dry run: show what --fix-invalid would close (status != OK, still open):
    python manage.py check_missed_subscription_activations --fix-invalid --dry-run

    # Actually close them:
    python manage.py check_missed_subscription_activations --fix-invalid

    # Dry run: show orphan subs (status=OK, active=False, no end_date, outside threshold):
    python manage.py check_missed_subscription_activations --fix-orphan --dry-run

    # Actually close orphan subs:
    python manage.py check_missed_subscription_activations --fix-orphan
"""
import csv
import sys
from datetime import date
from dateutil.relativedelta import relativedelta

from django.db import models
from django.db.models import Min
from django.core.management.base import BaseCommand
from tqdm import tqdm

from core.models import Subscription


class Command(BaseCommand):
    help = (
        "Finds inactive subscriptions whose start_date is in the past and status is OK "
        "(i.e. missed by activate_subscriptions_by_start_date). Outputs a CSV report.\n\n"
        "Also detects and optionally closes:\n"
        "  --fix-invalid: subscriptions with status != OK that are still open.\n"
        "  --fix-orphan:  subscriptions with status=OK, active=False, no end_date, "
        "outside the months-threshold (historical open subs that were never activated).\n\n"
        "Use --dry-run with --fix-invalid or --fix-orphan to preview changes without applying them."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            metavar="FILE",
            default=None,
            help="Path to write the missed-activations CSV. Defaults to stdout.",
        )
        parser.add_argument(
            "--since",
            metavar="YYYY-MM-DD",
            default=None,
            help="Only include subscriptions with start_date on or after this date.",
        )
        parser.add_argument(
            "--months-threshold",
            type=int,
            default=3,
            metavar="N",
            help=(
                "Only consider subscriptions whose start_date is within the last N months "
                "(default: 3). Prevents accidentally activating very old subscriptions. "
                "Also used by --fix-orphan to define 'outside threshold'."
            ),
        )
        parser.add_argument(
            "--activate",
            action="store_true",
            default=False,
            help="Also activate the found missed subscriptions (use with care on production).",
        )
        parser.add_argument(
            "--fix-invalid",
            action="store_true",
            default=False,
            help=(
                "Find subscriptions with status != OK that are still open (active=False, "
                "no end_date or end_date in the future) and set their end_date. "
                "end_date is set to next_billing - 1 day if next_billing exists and is not in "
                "the future; otherwise start_date + 1 month. Use --dry-run to preview."
            ),
        )
        parser.add_argument(
            "--fix-orphan",
            action="store_true",
            default=False,
            help=(
                "Find subscriptions with status=OK, active=False, no end_date, whose "
                "start_date is older than --months-threshold months. These are historical "
                "open subscriptions that were never activated and should be closed. "
                "end_date logic is the same as --fix-invalid. Use --dry-run to preview."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help=(
                "When used with --fix-invalid or --fix-orphan, print what would be changed "
                "without actually saving anything to the database."
            ),
        )

    def handle(self, *args, **options):
        today = date.today()
        dry_run = options["dry_run"]

        # --- Missed activations (status=OK, active=False, start_date in past, within threshold) ---
        threshold_date = today - relativedelta(months=options["months_threshold"])

        qs = Subscription.objects.filter(
            active=False,
            start_date__lt=today,
            start_date__gte=threshold_date,
            status="OK",
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=today)
        ).select_related("contact")

        if options["since"]:
            try:
                since = date.fromisoformat(options["since"])
            except ValueError:
                self.stderr.write(f"Invalid --since date: {options['since']}. Use YYYY-MM-DD format.")
                return
            qs = qs.filter(start_date__gte=since)

        qs = qs.order_by("start_date", "id")
        total = qs.count()

        # Fetch creation dates for all matching subscriptions in one query to avoid N+1.
        sub_ids = list(qs.values_list("id", flat=True))
        HistoricalSubscription = Subscription.history.model
        created_dates = dict(
            HistoricalSubscription.objects.filter(id__in=sub_ids, history_type="+")
            .values("id")
            .annotate(first_created=Min("history_date"))
            .values_list("id", "first_created")
        )

        rows = []
        for sub in tqdm(qs.iterator(), total=total, desc="Checking missed activations", file=sys.stderr):
            created_dt = created_dates.get(sub.id)
            created_date = created_dt.date() if created_dt else None

            rows.append(
                {
                    "subscription_id": sub.id,
                    "contact_id": sub.contact_id,
                    "contact_name": sub.contact.name,
                    "contact_last_name": sub.contact.last_name or "",
                    "contact_email": sub.contact.email or "",
                    "start_date": sub.start_date,
                    "end_date": sub.end_date or "",
                    "status": sub.status,
                    "payment_type": sub.payment_type or "",
                    "subscription_created_date": created_date or "",
                    "days_overdue": (today - sub.start_date).days if sub.start_date else "",
                }
            )

        if rows:
            fieldnames = [
                "subscription_id",
                "contact_id",
                "contact_name",
                "contact_last_name",
                "contact_email",
                "start_date",
                "end_date",
                "status",
                "payment_type",
                "subscription_created_date",
                "days_overdue",
            ]
            output_path = options["output"]
            if output_path:
                with open(output_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                self.stdout.write(f"Wrote {len(rows)} missed activation(s) to {output_path}")
            else:
                writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
                self.stderr.write(f"\n{len(rows)} missed activation(s) found.")
        else:
            self.stdout.write("No missed subscription activations found.")

        if options["activate"] and rows:
            ids = [r["subscription_id"] for r in rows]
            activated = Subscription.objects.filter(id__in=ids).update(active=True)
            self.stdout.write(f"Activated {activated} subscription(s).")

        # --- Fix invalid: status != OK, still open, active=False ---
        if options["fix_invalid"]:
            self._fix_subscriptions(
                today=today,
                dry_run=dry_run,
                qs=Subscription.objects.filter(active=False)
                .exclude(status="OK")
                .filter(models.Q(end_date__isnull=True) | models.Q(end_date__gt=today))
                .select_related("contact"),
                label="invalid (status != OK)",
            )

        # --- Fix orphan: status=OK, active=False, no end_date, outside threshold ---
        if options["fix_orphan"]:
            self._fix_subscriptions(
                today=today,
                dry_run=dry_run,
                qs=Subscription.objects.filter(
                    active=False,
                    status="OK",
                    end_date__isnull=True,
                    start_date__lt=threshold_date,
                ).select_related("contact"),
                label="orphan (status=OK, active=False, no end_date, outside threshold)",
            )

    def _fix_subscriptions(self, today, dry_run, qs, label):
        """
        Set end_date on all subscriptions in qs. If dry_run=True, only print what would change.
        """
        total = qs.count()
        if not total:
            self.stdout.write(f"No {label} subscriptions found.")
            return

        if dry_run:
            self.stderr.write(f"[DRY RUN] Would close {total} {label} subscription(s):")
            for sub in tqdm(qs.iterator(), total=total, desc=f"Previewing {label}", file=sys.stderr):
                end_date = self._compute_end_date(sub, today)
                self.stdout.write(
                    f"  sub {sub.id} | contact {sub.contact_id} ({sub.contact.name}) | "
                    f"start={sub.start_date} | status={sub.status} | "
                    f"next_billing={sub.next_billing} → end_date={end_date}"
                )
            self.stdout.write(f"[DRY RUN] {total} {label} subscription(s) would be closed. No changes made.")
        else:
            self.stderr.write(f"Found {total} {label} subscription(s) to close.")
            fixed = 0
            for sub in tqdm(qs.iterator(), total=total, desc=f"Fixing {label}", file=sys.stderr):
                sub.end_date = self._compute_end_date(sub, today)
                sub.save(update_fields=["end_date"])
                fixed += 1
            self.stdout.write(f"Closed {fixed} {label} subscription(s).")

    def _compute_end_date(self, sub, today):
        """
        Determine the end_date to assign:
          - next_billing - 1 day, if that date is not in the future.
          - Otherwise start_date + 1 month.
          - Fallback: today.
        """
        if sub.next_billing:
            candidate = sub.next_billing - relativedelta(days=1)
            if candidate <= today:
                return candidate
        if sub.start_date:
            return sub.start_date + relativedelta(months=1)
        return today
