from django.conf import settings
from factory import Faker, SubFactory, LazyAttribute
from factory.django import DjangoModelFactory
from core.models import Contact, Address, Product, Subscription, Campaign, State, Country
from core.choices import SUBSCRIPTION_TYPE_CHOICES, SUBSCRIPTION_STATUS_CHOICES


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

    name = Faker("country")
    code = ""
    active = True


class StateFactory(DjangoModelFactory):
    class Meta:
        model = State

    name = Faker("city")
    code = ""
    active = True
    country = SubFactory(CountryFactory)


class AddressFactory(DjangoModelFactory):
    class Meta:
        model = Address

    contact = SubFactory(ContactFactory)
    address_1 = Faker("street_address")
    address_2 = Faker("secondary_address")
    city = Faker("city")
    state = SubFactory(StateFactory)
    country = LazyAttribute(lambda obj: obj.state.country)
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
    state_georef_id = None
    city_georef_id = None


class CampaignFactory(DjangoModelFactory):
    class Meta:
        model = Campaign

    name = Faker("word")
    description = Faker("text", max_nb_chars=200)
    start_date = Faker("date_this_year")
    end_date = Faker("date_this_year")
