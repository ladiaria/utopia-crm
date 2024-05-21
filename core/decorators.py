# decorators.py
from functools import wraps
from django.urls import reverse
from django.utils.translation import gettext as _

def add_breadcrumbs(input_breadcrumbs=[]):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view_func(request, *args, **kwargs):
            breadcrumbs = [(reverse('main_menu'), _("Home"))]
            breadcrumbs.extend(input_breadcrumbs)
            request.breadcrumbs = breadcrumbs
            return view_func(request, *args, **kwargs)
        return _wrapped_view_func
    return decorator
