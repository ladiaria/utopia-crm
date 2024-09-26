from factory import Faker
from factory.django import DjangoModelFactory

from logistics.models import Route


class RouteFactory(DjangoModelFactory):
    class Meta:
        model = Route

    number = Faker("random_int", min=1, max=50)
    active = True
