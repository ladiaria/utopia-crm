from django.core.management.base import BaseCommand
from support.models import SellerConsoleAction
from core.choices import CAMPAIGN_STATUS


class Command(BaseCommand):
    """
    Management command to populate SellerConsoleAction models based on predefined action types and names.

    This command:
    1. Creates or updates SellerConsoleAction records based on the action_types_and_names tuple
    2. Uses hardcoded English slugs to match production usage and template compatibility
    3. Sets appropriate action_type and campaign_status for each action
    4. Marks all actions as active (is_active=True)
    5. Deletes obsolete actions that are not in the current tuple

    NOTE: Uses hardcoded English slugs with Spanish display names to maintain compatibility
    with existing production databases and template data-result attributes.

    Usage:
        python manage.py populate_seller_console_actions
    """

    help = "Populate SellerConsoleAction models with predefined actions"

    # Tuple of (action_type, slug, action_name, campaign_status) tuples
    # Uses hardcoded English slugs to match production usage and template compatibility
    action_types_and_names = (
        (
            SellerConsoleAction.ACTION_TYPES.CALL_LATER,
            "call-later",
            "Llamar más tarde",
            CAMPAIGN_STATUS.CALLED_COULD_NOT_CONTACT,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.PENDING,
            "move-morning",
            "Mover a la mañana",
            CAMPAIGN_STATUS.SWITCH_TO_MORNING,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.PENDING,
            "move-afternoon",
            "Mover a la tarde",
            CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.DECLINED,
            "not-interested",
            "No interesado",
            CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
        ),
        (SellerConsoleAction.ACTION_TYPES.DECLINED, "do-not-call", "No llamar", CAMPAIGN_STATUS.ENDED_WITH_CONTACT),
        (SellerConsoleAction.ACTION_TYPES.DECLINED, "logistics", "Logística", CAMPAIGN_STATUS.ENDED_WITH_CONTACT),
        (
            SellerConsoleAction.ACTION_TYPES.DECLINED,
            "already-subscriber",
            "Ya suscrito",
            CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.DECLINED,
            "error-promotion",
            "Error en promoción",
            CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.NO_CONTACT,
            "uncontactable",
            "No contactable",
            CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.NO_CONTACT,
            "close-without-contact",
            "Cerrar sin contacto",
            CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT,
        ),
        (SellerConsoleAction.ACTION_TYPES.SCHEDULED, "schedule", "Agendar", CAMPAIGN_STATUS.CONTACTED),
    )

    def handle(self, *args, **options):
        # Use hardcoded English slugs with Spanish display names
        action_data = self.action_types_and_names

        # Track current slugs to identify obsolete records
        current_slugs = set()

        # Create or update actions
        for action_type, slug, action_name, campaign_status in action_data:
            current_slugs.add(slug)

            action, created = SellerConsoleAction.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': action_name,
                    'action_type': action_type,
                    'campaign_status': campaign_status,
                    'is_active': True,
                },
            )

            if not created:
                # Update existing action - preserve relationships
                action.name = action_name
                action.action_type = action_type
                action.campaign_status = campaign_status
                action.is_active = True
                action.save()

            status_display = f" -> {campaign_status}" if campaign_status else " -> No status"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{'Created' if created else 'Updated'} SellerConsoleAction: "
                    f"{action.slug} - {action.name} ({action.get_action_type_display()}){status_display}"
                )
            )

        # Delete obsolete actions that are not in the current tuple
        obsolete_actions = SellerConsoleAction.objects.exclude(slug__in=current_slugs)
        obsolete_count = obsolete_actions.count()

        if obsolete_count > 0:
            for action in obsolete_actions:
                self.stdout.write(
                    self.style.WARNING(f"Deleting obsolete SellerConsoleAction: {action.slug} - {action.name}")
                )
            obsolete_actions.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted! Processed {len(current_slugs)} actions, deleted {obsolete_count} obsolete actions."
            )
        )
