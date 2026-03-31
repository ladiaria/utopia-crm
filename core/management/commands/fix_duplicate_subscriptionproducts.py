"""
Management command to detect and fix subscriptions with duplicate SubscriptionProducts
(i.e. the same product appearing more than once in a single subscription).

Behaviour
---------
- **Inactive past subscriptions** (active=False AND end_date < today):
  The duplicate is deleted automatically. The SubscriptionProduct with the
  lowest id (the oldest one) is kept; all others are removed.

- **Active or future subscriptions** (everything else):
  No automatic changes. A CSV is written with one row per duplicate group so
  that a human can decide which record to keep.

Usage examples
--------------
    # Dry-run: report what would happen, write CSV, make no DB changes
    python manage.py fix_duplicate_subscriptionproducts --dry-run

    # Run for real, write CSV of active/future cases to current directory
    python manage.py fix_duplicate_subscriptionproducts

    # Specify a custom output path for the CSV
    python manage.py fix_duplicate_subscriptionproducts --csv-path /tmp/duplicates.csv
"""

import csv
from datetime import date

from django.core.management.base import BaseCommand
from django.db.models import Count

from core.models import Subscription, SubscriptionProduct


class Command(BaseCommand):
    help = "Detect and fix duplicate SubscriptionProducts within a single subscription"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be done without making any database changes",
        )
        parser.add_argument(
            "--csv-path",
            default="duplicate_subscriptionproducts.csv",
            help=(
                "Path for the CSV output file with active/future cases that need manual review "
                "(default: duplicate_subscriptionproducts.csv in the current directory)"
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        csv_path = options["csv_path"]
        today = date.today()

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE — no database changes will be made"))

        # --- Find all subscriptions that have at least one product duplicated ---
        duplicated_subscription_ids = (
            SubscriptionProduct.objects.values("subscription_id", "product_id")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
            .values_list("subscription_id", flat=True)
            .distinct()
        )

        subscriptions = (
            Subscription.objects.filter(id__in=duplicated_subscription_ids)
            .select_related("contact")
            .order_by("id")
        )

        total = subscriptions.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("No subscriptions with duplicate SubscriptionProducts found."))
            return

        self.stdout.write(f"Found {total} subscription(s) with duplicate SubscriptionProducts.")

        auto_fixed = 0
        auto_deleted = 0
        manual_review_rows = []

        for subscription in subscriptions:
            # Find which product_ids are duplicated within this subscription
            duplicated_products = (
                SubscriptionProduct.objects.filter(subscription=subscription)
                .values("product_id")
                .annotate(count=Count("id"))
                .filter(count__gt=1)
            )

            is_inactive_past = (
                not subscription.active
                and subscription.end_date is not None
                and subscription.end_date < today
            )

            for dup in duplicated_products:
                product_id = dup["product_id"]
                sps = list(
                    SubscriptionProduct.objects.filter(
                        subscription=subscription,
                        product_id=product_id,
                    ).order_by("id")
                )

                if is_inactive_past:
                    # Keep the oldest (lowest id), delete the rest
                    to_keep = sps[0]
                    to_delete = sps[1:]
                    for sp in to_delete:
                        self.stdout.write(
                            f"  [AUTO] Subscription {subscription.id} "
                            f"(contact {subscription.contact_id}, end_date {subscription.end_date}): "
                            f"deleting SubscriptionProduct {sp.id} (product_id={product_id}, "
                            f"keeping id={to_keep.id})"
                        )
                        if not dry_run:
                            sp.delete()
                        auto_deleted += 1
                    auto_fixed += 1
                else:
                    # Active or future — collect for CSV
                    sp_ids = ", ".join(str(sp.id) for sp in sps)
                    sp_addresses = " | ".join(
                        str(sp.address.address_1) if sp.address else "-" for sp in sps
                    )
                    sp_copies = " | ".join(str(sp.copies) for sp in sps)
                    product_name = sps[0].product.name if sps[0].product else f"product_id={product_id}"
                    manual_review_rows.append(
                        {
                            "subscription_id": subscription.id,
                            "contact_id": subscription.contact_id,
                            "contact_name": subscription.contact.get_full_name(),
                            "subscription_active": subscription.active,
                            "subscription_status": subscription.status,
                            "subscription_start_date": subscription.start_date,
                            "subscription_end_date": subscription.end_date or "",
                            "product_id": product_id,
                            "product_name": product_name,
                            "subscriptionproduct_ids": sp_ids,
                            "addresses": sp_addresses,
                            "copies": sp_copies,
                            "admin_url": f"/admin/core/subscription/{subscription.id}/change/",
                        }
                    )

        # --- Write CSV for manual cases ---
        if manual_review_rows:
            fieldnames = [
                "subscription_id",
                "contact_id",
                "contact_name",
                "subscription_active",
                "subscription_status",
                "subscription_start_date",
                "subscription_end_date",
                "product_id",
                "product_name",
                "subscriptionproduct_ids",
                "addresses",
                "copies",
                "admin_url",
            ]
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(manual_review_rows)
            self.stdout.write(
                self.style.WARNING(
                    f"\n{len(manual_review_rows)} active/future duplicate group(s) require manual review. "
                    f"CSV written to: {csv_path}"
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("\nNo active/future duplicates found — no CSV needed."))

        # --- Summary ---
        self.stdout.write("\n" + "=" * 60)
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN SUMMARY (no changes saved):"))
        else:
            self.stdout.write(self.style.SUCCESS("SUMMARY:"))

        self.stdout.write(f"Total subscriptions with duplicates: {total}")
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"Would auto-delete from inactive/past subscriptions: {auto_deleted} record(s)")
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"Auto-deleted from inactive/past subscriptions: {auto_deleted}"))
        self.stdout.write(f"Active/future groups requiring manual review: {len(manual_review_rows)}")
        self.stdout.write("=" * 60)
