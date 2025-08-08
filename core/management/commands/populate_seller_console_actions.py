from django.core.management.base import BaseCommand
from support.models import SellerConsoleAction


class Command(BaseCommand):

    action_slugs = [
        "schedule",
        "call-later",
        "not-interested",
        "do-not-call",
        "logistics",
        "already-subscriber",
        "uncontactable",
        "error-promotion",
        "move-morning",
        "move-afternoon",
        "close-without-contact",
    ]

    action_map_ES = {
        "schedule": "Agendar",
        "call-later": "Llamar más tarde",
        "not-interested": "No interesado",
        "do-not-call": "No llamar",
        "logistics": "Logística",
        "already-subscriber": "Ya suscrito",
        "uncontactable": "No contactable",
        "error-promotion": "Error en promoción",
        "move-morning": "Mover a la mañana",
        "move-afternoon": "Mover a la tarde",
        "close-without-contact": "Cerrar sin contacto",
    }

    action_map_EN = {
        "schedule": "Schedule",
        "call-later": "Call later",
        "not-interested": "Not interested",
        "do-not-call": "Do not call",
        "logistics": "Logistics",
        "already-subscriber": "Already subscriber",
        "uncontactable": "Uncontactable",
        "error-promotion": "Error promotion",
        "move-morning": "Move morning",
        "move-afternoon": "Move afternoon",
        "close-without-contact": "Close without contact",
    }

    def handle(self, *args, **kwargs):
        lang = kwargs.get("lang", "ES")
        action_map = getattr(self, f"action_map_{lang}")
        for slug in self.action_slugs:
            seller_action, created = SellerConsoleAction.objects.get_or_create(
                slug=slug, defaults={"name": action_map.get(slug)}
            )
            if not created:
                seller_action.name = action_map.get(slug)
                seller_action.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"SellerConsoleAction {slug} {'created' if created else 'updated'} with name {seller_action.name}"
                )
            )
