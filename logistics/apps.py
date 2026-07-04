from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class LogisticsConfig(AppConfig):
    name = "logistics"
    verbose_name = _("Logistics")

    def ready(self):
        import logistics.signals  # noqa
