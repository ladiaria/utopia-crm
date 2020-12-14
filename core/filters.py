import django_filters

from django.db.models import Q

from .models import Contact


class ContactFilter(django_filters.FilterSet):
    filter_multiple = django_filters.CharFilter(method='filter_by')

    class Meta:
        model = Contact
        fields = ['name', 'filter_multiple']

    def filter_by(self, queryset, name, value):
        return Contact.objects.filter(
            Q(phone__contains=value) | Q(mobile__contains=value) | Q(work_phone__contains=value) |
            Q(name__icontains=value) | Q(email__icontains=value) | Q(id_document__contains=value)
        )
