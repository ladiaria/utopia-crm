from django.core.management.base import BaseCommand
from django.utils.text import slugify
from support.models import SellerConsoleAction
from core.choices import CAMPAIGN_STATUS


class Command(BaseCommand):
    """
    Management command to populate SellerConsoleAction models based on predefined action types and names.

    This command:
    1. Creates or updates SellerConsoleAction records based on the action_types_and_names tuple
    2. Automatically generates slugs using Django's slugify function
    3. Sets appropriate action_type for each action
    4. Marks all actions as active (is_active=True)
    5. Deletes obsolete actions that are not in the current tuple

    Usage:
        python manage.py populate_seller_console_actions [--lang=ES|EN]
    """

    help = "Populate SellerConsoleAction models with predefined actions"

    # Tuple of (action_type, action_name, campaign_status) tuples
    # Based on the existing mapping in the original command
    action_types_and_names = (
        (SellerConsoleAction.ACTION_TYPES.PENDING, "Agendar", CAMPAIGN_STATUS.CONTACTED),
        (SellerConsoleAction.ACTION_TYPES.PENDING, "Llamar más tarde", CAMPAIGN_STATUS.CALLED_COULD_NOT_CONTACT),
        (SellerConsoleAction.ACTION_TYPES.PENDING, "Mover a la mañana", CAMPAIGN_STATUS.SWITCH_TO_MORNING),
        (SellerConsoleAction.ACTION_TYPES.PENDING, "Mover a la tarde", CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON),
        (SellerConsoleAction.ACTION_TYPES.DECLINED, "No interesado", CAMPAIGN_STATUS.ENDED_WITH_CONTACT),
        (SellerConsoleAction.ACTION_TYPES.DECLINED, "No llamar", CAMPAIGN_STATUS.ENDED_WITH_CONTACT),
        (SellerConsoleAction.ACTION_TYPES.DECLINED, "Logística", CAMPAIGN_STATUS.ENDED_WITH_CONTACT),
        (SellerConsoleAction.ACTION_TYPES.DECLINED, "Ya suscrito", CAMPAIGN_STATUS.ENDED_WITH_CONTACT),
        (SellerConsoleAction.ACTION_TYPES.DECLINED, "Error en promoción", CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT),
        (SellerConsoleAction.ACTION_TYPES.NO_CONTACT, "No contactable", CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT),
        (SellerConsoleAction.ACTION_TYPES.NO_CONTACT, "Cerrar sin contacto", CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT),
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--lang', type=str, default='ES', choices=['ES', 'EN'], help='Language for action names (ES or EN)'
        )

    def handle(self, *args, **options):
        lang = options.get('lang', 'ES')

        # Get the appropriate action names based on language
        action_names = self._get_action_names_by_language(lang)

        # Track current slugs to identify obsolete records
        current_slugs = set()

        # Create or update actions
        for action_type, action_name, campaign_status in action_names:
            slug = slugify(action_name)
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
                # Update existing action
                action.name = action_name
                action.action_type = action_type
                action.campaign_status = campaign_status
                action.is_active = True
                action.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"{'Created' if created else 'Updated'} SellerConsoleAction: "
                    f"{action.slug} - {action.name} ({action.get_action_type_display()})"
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

    def _get_action_names_by_language(self, lang):
        """
        Get action names based on the specified language.

        Args:
            lang (str): Language code ('ES' or 'EN')

        Returns:
            tuple: Tuple of (action_type, action_name) pairs in the specified language
        """
        if lang == 'EN':
            # English translations
            return (
                (SellerConsoleAction.ACTION_TYPES.PENDING, "Schedule", CAMPAIGN_STATUS.CONTACTED),
                (SellerConsoleAction.ACTION_TYPES.PENDING, "Call later", CAMPAIGN_STATUS.CALLED_COULD_NOT_CONTACT),
                (SellerConsoleAction.ACTION_TYPES.PENDING, "Move to morning", CAMPAIGN_STATUS.SWITCH_TO_MORNING),
                (SellerConsoleAction.ACTION_TYPES.PENDING, "Move to afternoon", CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON),
                (SellerConsoleAction.ACTION_TYPES.DECLINED, "Not interested", CAMPAIGN_STATUS.ENDED_WITH_CONTACT),
                (SellerConsoleAction.ACTION_TYPES.DECLINED, "Do not call", CAMPAIGN_STATUS.ENDED_WITH_CONTACT),
                (SellerConsoleAction.ACTION_TYPES.DECLINED, "Logistics", CAMPAIGN_STATUS.ENDED_WITH_CONTACT),
                (SellerConsoleAction.ACTION_TYPES.DECLINED, "Already subscriber", CAMPAIGN_STATUS.ENDED_WITH_CONTACT),
                (SellerConsoleAction.ACTION_TYPES.DECLINED, "Promotion error", CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT),
                (SellerConsoleAction.ACTION_TYPES.NO_CONTACT, "Uncontactable", CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT),
                (SellerConsoleAction.ACTION_TYPES.NO_CONTACT, "Close without contact", CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT),
            )
        else:
            # Default to Spanish
            return self.action_types_and_names
