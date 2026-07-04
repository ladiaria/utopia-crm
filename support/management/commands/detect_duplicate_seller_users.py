from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from support.models import Seller


class Command(BaseCommand):
    help = "Detect users assigned to multiple sellers"

    def handle(self, *args, **options):
        # Get all users assigned to sellers
        users_with_sellers = Seller.objects.filter(user__isnull=False).values_list("user_id", "user__username")

        # Count occurrences of each user
        user_count = {}
        for user_id, username in users_with_sellers:
            if user_id not in user_count:
                user_count[user_id] = {"username": username, "sellers": []}
            user_count[user_id]["sellers"].append(user_id)

        # Find duplicates
        duplicates = {uid: data for uid, data in user_count.items() if len(Seller.objects.filter(user_id=uid)) > 1}

        if not duplicates:
            self.stdout.write(self.style.SUCCESS("✓ No duplicate user assignments found"))
            return

        self.stdout.write(self.style.WARNING(f"\n⚠ Found {len(duplicates)} users assigned to multiple sellers:\n"))

        for user_id, data in duplicates.items():
            sellers = Seller.objects.filter(user_id=user_id)
            seller_info = "\n  ".join([f"• {s.id} - {s.name} (internal: {s.internal})" for s in sellers])

            self.stdout.write(self.style.WARNING(f"User: {data['username']} (ID: {user_id})"))
            self.stdout.write(f"  Assigned to {len(sellers)} sellers:\n  {seller_info}\n")
