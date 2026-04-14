# coding=utf-8
"""
Management command to detect subscriptions that should have been activated
by `activate_subscriptions_by_start_date` but were missed.

This happens when a subscription is created *after* its start_date (e.g. created
on 2025-04-07 with start_date=2025-04-01): the nightly command only looks forward
up to one day ahead, so it never picks up past-due start dates.

Usage:
    python manage.py check_missed_subscription_activations
    python manage.py check_missed_subscription_activations --output /tmp/missed.csv
    python manage.py check_missed_subscription_activations --since 2025-01-01
"""
import csv
import sys
from datetime import date

from django.db import models
from django.core.management.base import BaseCommand

from core.models import Subscription


class Command(BaseCommand):
    help = (
        "Finds inactive subscriptions whose start_date is in the past and status is OK "
        "(i.e. missed by activate_subscriptions_by_start_date). Outputs a CSV report."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            metavar="FILE",
            default=None,
            help="Path to write the CSV file. Defaults to stdout.",
        )
        parser.add_argument(
            "--since",
            metavar="YYYY-MM-DD",
            default=None,
            help="Only include subscriptions with start_date on or after this date.",
        )
        parser.add_argument(
            "--activate",
            action="store_true",
            default=False,
            help="Also activate the found subscriptions (use with care on production).",
        )

    def handle(self, *args, **options):
        today = date.today()

        qs = Subscription.objects.filter(
            active=False,
            start_date__lt=today,
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

        rows = []
        for sub in qs.order_by("start_date", "id"):
            # Try to find the creation date via simple-history
            first_history = sub.history.filter(history_type="+").order_by("history_date").first()
            created_date = first_history.history_date.date() if first_history else None

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

        if not rows:
            self.stdout.write("No missed subscription activations found.")
            return

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
            self.stdout.write(f"Wrote {len(rows)} row(s) to {output_path}")
        else:
            writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            self.stderr.write(f"\n{len(rows)} subscription(s) found.")

        if options["activate"]:
            ids = [r["subscription_id"] for r in rows]
            activated = Subscription.objects.filter(id__in=ids).update(active=True)
            self.stdout.write(f"Activated {activated} subscription(s).")
