from django.utils.functional import cached_property


class BreadcrumbsMixin:
    @cached_property
    def breadcrumbs(self):
        """Override this method in child classes to define breadcrumbs"""
        return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['breadcrumbs'] = self.breadcrumbs
        return context
