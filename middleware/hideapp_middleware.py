from django.conf import settings
from django.http import HttpResponseNotFound


class HideAppMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.hidden_apps = getattr(settings, 'DISABLED_APPS', [])

    def __call__(self, request):
        # Check if the URL belongs to any hidden app
        if any(request.path.startswith(f'/{app}/') for app in self.hidden_apps):
            return HttpResponseNotFound()

        response = self.get_response(request)
        return response
