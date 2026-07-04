from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SupportConfig(AppConfig):
    name = "support"
    verbose_name = _("Support")

    def ready(self):
        import support.signals  # noqa
