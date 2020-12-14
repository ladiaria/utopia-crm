from django.apps import AppConfig


class LogisticsConfig(AppConfig):
    name = "logistics"

    def ready(self):
        import logistics.signals  # noqa
