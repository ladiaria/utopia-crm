from django.http import HttpResponseForbidden
from django.contrib.auth import login
from django.conf import settings


def access_required(view_func, login_url=settings.LOGIN_URL):
    """
    Decorator for views that checks that the user is logged in or it has
    provided and access token in the GET or POST data.
    """
    def _checkaccess(request, *args, **kwargs):
        if not request.user.is_anonymous():
            return view_func(request, *args, **kwargs)

        # user is anonymous
        try:
            access_token = settings.ACCESS_TOKEN

            request_method = request.META['REQUEST_METHOD']
            if request_method in ('GET', 'POST'):
                if request_method == 'GET':
                    payload = request.GET
                elif request_method == 'POST':
                    payload = request.POST

                if payload.get('access_token', None) == access_token:
                    return view_func(request, *args, **kwargs)
                else:
                    return HttpResponseForbidden()
            else:
                return HttpResponseForbidden()
        except:
            return login.redirect_to_login(request.path, login_url)

    _checkaccess.__doc__ = view_func.__doc__
    _checkaccess.__name__ = view_func.__name__

    return _checkaccess
