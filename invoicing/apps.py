from django.apps import AppConfig


class InvoicingConfig(AppConfig):
    name = "invoicing"

    def ready(self):
        import invoicing.signals  # noqa
