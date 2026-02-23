from datetime import datetime, time
from django.core.management.base import BaseCommand
from django.db.models import Q
from tqdm import tqdm

from core.models import SubscriptionProduct


class Command(BaseCommand):
    """
    Management command to populate the original_datetime field for SubscriptionProduct instances.

    This command traces back through the subscription chain (via updated_from) to determine
    WHEN EACH SPECIFIC PRODUCT was added to the subscription chain. Since we don't have time
    information, all times are set to 00:00:00 (naive datetime, as USE_TZ=False in settings).

    IMPORTANT: This correctly handles products added at different points in the subscription chain.
    For example:
    - If a product existed in the original subscription, it gets the original subscription's start_date
    - If a product was added in the 2nd subscription of a chain, it gets that 2nd subscription's start_date
    - If a product was added in the Xth subscription, it gets that Xth subscription's start_date

    Logic:
    1. For each SubscriptionProduct, start with its current subscription
    2. Check if the same product exists in the previous subscription (updated_from)
    3. If it does, continue tracing back through the chain
    4. If it doesn't, this is where the product was added - use this subscription's start_date
    5. Set time to 00:00:00 in Uruguay timezone
    6. Only update SubscriptionProducts where original_datetime is currently NULL

    Usage:
        python manage.py populate_subscriptionproduct_original_date [--dry-run] [--contact-id ID] [--limit N]
    """

    help = "Populate original_date field for SubscriptionProduct instances based on subscription chain"

    def _find_product_creation_date(self, subscription_product):
        """
        Find the date when this specific product was added to the subscription chain.

        Logic:
        1. Start with the current subscription
        2. Check if the same product exists in the previous subscription (updated_from)
        3. If it does, continue tracing back
        4. If it doesn't, this is where the product was added - use this subscription's start_date
        5. If we reach the original subscription, use its start_date

        Args:
            subscription_product: SubscriptionProduct instance

        Returns:
            date: The start_date of the subscription where this product was first added
        """
        current_subscription = subscription_product.subscription
        product = subscription_product.product

        # Start with the current subscription's start_date as fallback
        creation_date = current_subscription.start_date

        # Trace back through the subscription chain
        while current_subscription.updated_from:
            previous_subscription = current_subscription.updated_from

            # Check if this product existed in the previous subscription
            product_existed_before = previous_subscription.subscriptionproduct_set.filter(
                product=product
            ).exists()

            if product_existed_before:
                # Product existed before, keep tracing back
                creation_date = previous_subscription.start_date
                current_subscription = previous_subscription
            else:
                # Product didn't exist in previous subscription
                # So it was added in the current subscription
                break

        return creation_date

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run the command without making any changes to the database',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit the number of SubscriptionProducts to process (for testing)',
        )
        parser.add_argument(
            '--contact-id',
            type=int,
            help='Only process SubscriptionProducts for a specific contact ID (for testing)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        limit = options.get('limit')
        contact_id = options.get('contact_id')

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be saved"))

        if contact_id:
            self.stdout.write(self.style.WARNING(f"TESTING MODE - Only processing contact ID: {contact_id}"))

        if limit:
            self.stdout.write(self.style.WARNING(f"LIMIT MODE - Processing maximum {limit} SubscriptionProducts"))

        # Get all SubscriptionProducts without an original_date
        subscription_products = SubscriptionProduct.objects.filter(
            Q(original_datetime__isnull=True)
        ).select_related('subscription')

        # Filter by contact if specified
        if contact_id:
            subscription_products = subscription_products.filter(subscription__contact_id=contact_id)

        # Apply limit if specified
        if limit:
            subscription_products = subscription_products[:limit]

        total_count = subscription_products.count()
        self.stdout.write(f"Found {total_count} SubscriptionProducts without original_datetime")

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("No SubscriptionProducts to update. All done!"))
            return

        updated_count = 0
        error_count = 0
        skipped_count = 0

        # Use tqdm for progress bar
        for sp in tqdm(subscription_products, desc="Processing SubscriptionProducts", unit="product"):
            try:
                # Find when this specific product was added to the subscription chain
                # by checking if it exists in previous subscriptions
                original_start_date = self._find_product_creation_date(sp)

                if not original_start_date:
                    tqdm.write(
                        self.style.WARNING(
                            f"Skipping SubscriptionProduct {sp.id}: No start_date found in subscription chain"
                        )
                    )
                    skipped_count += 1
                    continue

                # Create naive datetime at 00:00:00 (USE_TZ=False in settings)
                # original_start_date is a date object, so we combine it with midnight time
                original_datetime = datetime.combine(original_start_date, time(0, 0, 0))

                if not dry_run:
                    sp.original_datetime = original_datetime
                    sp.save(update_fields=['original_datetime'])

                updated_count += 1

            except Exception as e:
                error_count += 1
                tqdm.write(
                    self.style.ERROR(
                        f"Error processing SubscriptionProduct {sp.id}: {str(e)}"
                    )
                )

        # Summary
        self.stdout.write("\n" + "=" * 60)
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN SUMMARY (no changes saved):"))
        else:
            self.stdout.write(self.style.SUCCESS("SUMMARY:"))

        self.stdout.write(f"Total SubscriptionProducts found: {total_count}")
        self.stdout.write(self.style.SUCCESS(f"Successfully processed: {updated_count}"))

        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f"Skipped (no start_date): {skipped_count}"))

        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"Errors: {error_count}"))

        self.stdout.write("=" * 60)

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nCompleted! Updated {updated_count} SubscriptionProducts with original_datetime."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "\nDry run completed. Run without --dry-run to save changes."
                )
            )
