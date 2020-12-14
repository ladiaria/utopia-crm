from django.apps import AppConfig


class SupportConfig(AppConfig):
    name = "support"

    def ready(self):
        import support.signals  # noqa
