from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class InvoicingConfig(AppConfig):
    name = "invoicing"
    verbose_name = _("Invoicing")

    def ready(self):
        import invoicing.signals  # noqa
