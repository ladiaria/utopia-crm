# core/fields.py
from django.db import models

class LowercaseEmailField(models.EmailField):
    """
    Overrides EmailField to convert emails to lowercase before saving.
    """
    def to_python(self, value):
        value = super(LowercaseEmailField, self).to_python(value)
        if isinstance(value, str):
            return value.lower()
        return value
