from django.conf import settings
from factory import Faker, SubFactory
from factory.django import DjangoModelFactory
from core.models import Contact, Address, Product, Subscription, Campaign, State, Country
from core.choices import SUBSCRIPTION_TYPE_CHOICES, SUBSCRIPTION_STATUS_CHOICES


class ContactFactory(DjangoModelFactory):
    class Meta:
        model = Contact

    name = Faker("first_name")
    last_name = Faker("last_name")
    phone = Faker("phone_number")
    email = Faker("email")


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product

    name = Faker("word")
    slug = Faker("slug")
    active = Faker("boolean")
    price = Faker("pydecimal", left_digits=3, right_digits=2, positive=True)
    type = Faker("random_element", elements=[choice[0] for choice in Product.ProductTypeChoices.choices])
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


class CountryFactory(DjangoModelFactory):
    class Meta:
        model = Country
        django_get_or_create = ('code',)

    name = Faker("country")
    code = Faker("country_code")
    active = True


class StateFactory(DjangoModelFactory):
    class Meta:
        model = State
        django_get_or_create = ('code', 'country')

    name = Faker("city")
    code = Faker("state_abbr")
    active = True
    country = SubFactory(CountryFactory)


class AddressFactory(DjangoModelFactory):
    class Meta:
        model = Address

    contact = SubFactory(ContactFactory)
    address_1 = Faker("street_address")
    address_2 = Faker("secondary_address")
    city = Faker("city")
    state = None  # Don't auto-create state to avoid complexity
    country = None  # Don't auto-create country to avoid complexity
    email = None
    address_type = "physical"
    notes = Faker("text", max_nb_chars=200)
    default = False
    picture = None
    google_maps_url = None
    do_not_show = False
    georef_point = None
    latitude = None
    longitude = None
    verified = False
    needs_georef = False
    address_georef_id = None
    state_georef_id = None
    city_georef_id = None


class CampaignFactory(DjangoModelFactory):
    class Meta:
        model = Campaign

    name = Faker("word")
    description = Faker("text", max_nb_chars=200)
    start_date = Faker("date_this_year")
    end_date = Faker("date_this_year")
