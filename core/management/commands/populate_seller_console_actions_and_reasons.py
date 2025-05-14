from django.core.management.base import BaseCommand
from support.models import SellerConsoleAction
from django.conf import settings


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
    }

    def handle(self, *args, **kwargs):
        lang = "ES"
        if getattr(settings, "DEFAULT_LANGUAGE", "en") == "en":
            lang = "EN"
        map_ = getattr(self, f"map_{lang}")
        for slug in self.action_slugs:
            seller_action, created = SellerConsoleAction.objects.get_or_create(
                slug=slug, defaults={"name": map_.get(slug)}
            )
            if not created:
                seller_action.name = self.map_ES.get(slug)
                seller_action.save()
            self.stdout.write(self.style.SUCCESS(f"SellerConsoleAction {slug} {'created' if created else 'updated'}"))
