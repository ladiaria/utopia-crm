from django.core.management.base import BaseCommand
from django.utils.text import slugify
from support.models import SellerConsoleAction


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

    # Tuple of (action_type, action_name) pairs
    # Based on the existing mapping in the original command
    action_types_and_names = (
        (SellerConsoleAction.ACTION_TYPES.PENDING, "Agendar"),
        (SellerConsoleAction.ACTION_TYPES.PENDING, "Llamar más tarde"),
        (SellerConsoleAction.ACTION_TYPES.PENDING, "Mover a la mañana"),
        (SellerConsoleAction.ACTION_TYPES.PENDING, "Mover a la tarde"),
        (SellerConsoleAction.ACTION_TYPES.DECLINED, "No interesado"),
        (SellerConsoleAction.ACTION_TYPES.DECLINED, "No llamar"),
        (SellerConsoleAction.ACTION_TYPES.DECLINED, "Logística"),
        (SellerConsoleAction.ACTION_TYPES.DECLINED, "Ya suscrito"),
        (SellerConsoleAction.ACTION_TYPES.DECLINED, "Error en promoción"),
        (SellerConsoleAction.ACTION_TYPES.NO_CONTACT, "No contactable"),
        (SellerConsoleAction.ACTION_TYPES.NO_CONTACT, "Cerrar sin contacto"),
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
        for action_type, action_name in action_names:
            slug = slugify(action_name)
            current_slugs.add(slug)

            action, created = SellerConsoleAction.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': action_name,
                    'action_type': action_type,
                    'is_active': True,
                },
            )

            if not created:
                # Update existing action
                action.name = action_name
                action.action_type = action_type
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
                (SellerConsoleAction.ACTION_TYPES.PENDING, "Schedule"),
                (SellerConsoleAction.ACTION_TYPES.PENDING, "Call later"),
                (SellerConsoleAction.ACTION_TYPES.PENDING, "Move to morning"),
                (SellerConsoleAction.ACTION_TYPES.PENDING, "Move to afternoon"),
                (SellerConsoleAction.ACTION_TYPES.DECLINED, "Not interested"),
                (SellerConsoleAction.ACTION_TYPES.DECLINED, "Do not call"),
                (SellerConsoleAction.ACTION_TYPES.DECLINED, "Logistics"),
                (SellerConsoleAction.ACTION_TYPES.DECLINED, "Already subscriber"),
                (SellerConsoleAction.ACTION_TYPES.DECLINED, "Promotion error"),
                (SellerConsoleAction.ACTION_TYPES.NO_CONTACT, "Uncontactable"),
                (SellerConsoleAction.ACTION_TYPES.NO_CONTACT, "Close without contact"),
            )
        else:
            # Default to Spanish
            return self.action_types_and_names
