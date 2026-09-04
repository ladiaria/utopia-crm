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
    4. Sets is_active according to the tuple (all the console buttons are active; close-lost-schedule
       is registered inactive because it is only set by the close_lost_schedule_activities command)
    5. Deletes obsolete actions that are not in the current tuple

    NOTE: Uses hardcoded English slugs with Spanish display names to maintain compatibility
    with existing production databases and template data-result attributes.

    Usage:
        python manage.py populate_seller_console_actions
    """

    help = "Populate SellerConsoleAction models with predefined actions"

    # Tuple of (action_type, slug, action_name, campaign_status, campaign_resolution, is_active) tuples
    # Uses hardcoded English slugs to match production usage and template compatibility
    # campaign_resolution values: NI=Not interested, DN=Do not call, LO=Logistics, AS=Already subscriber,
    #                             EP=Error in promotion, UN=Cannot find contact, CW=Close without contact,
    #                             SC=Scheduled, CL=Call later, LS=Closed due to lost schedule
    action_types_and_names = (
        (
            SellerConsoleAction.ACTION_TYPES.CALL_LATER,
            "call-later",
            "Llamar más tarde",
            CAMPAIGN_STATUS.CALLED_COULD_NOT_CONTACT,
            "CL",  # Call later
            True,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.PENDING,
            "move-morning",
            "Mover a la mañana",
            CAMPAIGN_STATUS.SWITCH_TO_MORNING,
            None,  # No resolution - still pending
            True,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.PENDING,
            "move-afternoon",
            "Mover a la tarde",
            CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON,
            None,  # No resolution - still pending
            True,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.DECLINED,
            "not-interested",
            "No interesado",
            CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
            "NI",  # Not interested
            True,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.DECLINED,
            "do-not-call",
            "No llamar",
            CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
            "DN",  # Do not call anymore
            True,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.DECLINED,
            "logistics",
            "Logística",
            CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
            "LO",  # Logistics
            True,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.DECLINED,
            "already-subscriber",
            "Ya suscrito",
            CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
            "AS",  # Already a subscriber
            True,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.DECLINED,
            "error-promotion",
            "Error en promoción",
            CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT,
            "EP",  # Error in promotion
            True,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.NOT_FOUND,
            "not-found",
            "No encontrado",
            CAMPAIGN_STATUS.CALLED_COULD_NOT_CONTACT,
            "NF",  # Not found - keeps contact in campaign
            True,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.NO_CONTACT,
            "uncontactable",
            "No contactable",
            CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT,
            "UN",  # Cannot find contact
            True,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.NO_CONTACT,
            "close-without-contact",
            "Cerrar sin contacto",
            CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT,
            "CW",  # Close without contact
            True,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.SCHEDULED,
            "schedule",
            "Agendar",
            CAMPAIGN_STATUS.CONTACTED,
            "SC",  # Scheduled
            True,
        ),
        (
            SellerConsoleAction.ACTION_TYPES.NO_CONTACT,
            "close-lost-schedule",
            "Cerrado por agenda perdida",
            None,  # The status is decided per contact by close_lost_schedule_activities
            "LS",  # Closed due to lost schedule
            # Inactive on purpose: this action is not a console button, it is only set by the
            # close_lost_schedule_activities command. It lives in this tuple so the populate command
            # does not delete it (the FKs pointing at it are SET_NULL and the mark would be lost).
            False,
        ),
    )

    def handle(self, *args, **options):
        # Use hardcoded English slugs with Spanish display names
        action_data = self.action_types_and_names

        # Track current slugs to identify obsolete records
        current_slugs = set()

        # Create or update actions
        for action_type, slug, action_name, campaign_status, campaign_resolution, is_active in action_data:
            current_slugs.add(slug)

            action, created = SellerConsoleAction.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": action_name,
                    "action_type": action_type,
                    "campaign_status": campaign_status,
                    "campaign_resolution": campaign_resolution,
                    "is_active": is_active,
                },
            )

            if not created:
                # Update existing action - preserve relationships
                action.name = action_name
                action.action_type = action_type
                action.campaign_status = campaign_status
                action.campaign_resolution = campaign_resolution
                action.is_active = is_active
                action.save()

            status_display = f" -> Status: {campaign_status}" if campaign_status else ""
            resolution_display = f", Resolution: {campaign_resolution}" if campaign_resolution else ""
            action_status = "Created" if created else "Updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{action_status} SellerConsoleAction: {action.slug} - {action.name} "
                    f"({action.get_action_type_display()}){status_display}{resolution_display}"
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
