from django.utils.functional import cached_property


class BreadcrumbsMixin:
    """
    Injects a ``breadcrumbs`` list into the template context so that
    ``components/_breadcrumbs.html`` can render the navigation trail.

    Usage
    -----
    Override ``breadcrumbs`` in the subclass as a plain method (no decorator
    needed) returning a list of ``{"label": str, "url": str}`` dicts::

        class MyView(BreadcrumbsMixin, TemplateView):
            def breadcrumbs(self):
                return [
                    {"label": _("Home"), "url": reverse("home")},
                    {"label": _("My view"), "url": reverse("my_view")},
                ]

    How it works
    ------------
    The base definition uses ``@cached_property`` so that ``self.breadcrumbs``
    evaluates to the list directly (not a callable).  When a subclass overrides
    it with a plain method, ``self.breadcrumbs`` becomes a bound method
    (callable).  Both work because:

    * ``get_context_data`` does ``context['breadcrumbs'] = self.breadcrumbs``,
      which stores either the list or the callable.
    * Django's template engine automatically calls any callable it finds in the
      context, so ``{{ breadcrumbs }}`` resolves correctly in both cases.

    Views that override ``get`` or ``post`` and call ``render()`` directly
    bypass ``get_context_data``.  In those cases call ``get_context_data``
    explicitly and merge its result into the render context::

        def get(self, request, *args, **kwargs):
            ctx = self.get_context_data()   # breadcrumbs injected here
            ctx.update({...})               # add view-specific keys
            return render(request, self.template_name, ctx)
    """

    @cached_property
    def breadcrumbs(self):
        """Override this method in child classes to define breadcrumbs."""
        return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['breadcrumbs'] = self.breadcrumbs
        return context
