from django.conf import settings
from factory import Faker, SubFactory, LazyAttribute, post_generation
from factory.django import DjangoModelFactory
from core.models import Contact, Address, Product, Subscription
from core.choices import PRODUCT_TYPE_CHOICES, SUBSCRIPTION_TYPE_CHOICES, SUBSCRIPTION_STATUS_CHOICES


class ContactFactory(DjangoModelFactory):
    class Meta:
        model = Contact

    name = Faker("name")
    phone = Faker("phone_number")
    email = Faker("email")


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product

    name = Faker("word")
    slug = Faker("slug")
    active = Faker("boolean")
    price = Faker("pydecimal", left_digits=3, right_digits=2, positive=True)
    type = Faker("random_element", elements=[choice[0] for choice in PRODUCT_TYPE_CHOICES])
    weekday = Faker("random_int", min=0, max=6)
    offerable = Faker("boolean")
    digital = Faker("boolean")


class SubscriptionFactory(DjangoModelFactory):
    class Meta:
        model = Subscription

    contact = SubFactory(ContactFactory)
    type = Faker("random_element", elements=[choice[0] for choice in SUBSCRIPTION_TYPE_CHOICES])
    status = Faker("random_element", elements=[choice[0] for choice in SUBSCRIPTION_STATUS_CHOICES])
    active = Faker("boolean")
    start_date = Faker("date_this_year")
    end_date = Faker("date_this_year")
    payment_type = Faker(
        "random_element", elements=[choice[0] for choice in settings.SUBSCRIPTION_PAYMENT_METHODS]
    )


class AddressFactory(DjangoModelFactory):
    class Meta:
        model = Address

    contact = SubFactory(ContactFactory)
    address_1 = Faker("street_address")
    address_2 = Faker("secondary_address")
    city = Faker("city")
    state = Faker("state")
    email = None
    address_type = "physical"
    notes = Faker("text", max_nb_chars=200)
    default = Faker("boolean")
    picture = None  # You can add a file generator if needed
    google_maps_url = Faker("url")
    do_not_show = False
    georef_point = None  # You may need a custom generator for PointField
    latitude = None
    longitude = None
    verified = False
    needs_georef = False
    address_georef_id = None
    state_id = None
    city_id = None
    country = Faker("country")
