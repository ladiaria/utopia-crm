from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AdvertisementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "advertisement"
    verbose_name = _("Advertisement")
