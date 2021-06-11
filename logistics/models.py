# coding=utf-8
from __future__ import unicode_literals
from datetime import date, timedelta

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.contrib.gis.db.models import PointField
from django.utils.translation import ugettext_lazy as _

from logistics.choices import RESORT_STATUS_CHOICES, MESSAGE_PLACES
from core.models import SubscriptionProduct


class Route(models.Model):
    """
    A route is a territory which is used to deliver a product easily, allowing us to organize the delivery of the
    product for the different distributors. There are routes that are parents of other routes in hierarchy.
    """
    number = models.IntegerField(primary_key=True, verbose_name=_('Number'))
    name = models.CharField(max_length=40, verbose_name=_('Name'), blank=True, null=True)
    state = models.CharField(max_length=20, verbose_name=_('State'), blank=True, null=True)
    description = models.TextField(blank=True, verbose_name=_('Description'))
    distributor = models.CharField(max_length=40, blank=True, verbose_name=_('Distributor'))
    phone = models.CharField(max_length=20, blank=True, verbose_name=_('Phone'))
    mobile = models.CharField(max_length=20, blank=True, verbose_name=_('Mobile'))
    email = models.CharField(max_length=100, blank=True, verbose_name=_('Email'))
    delivery_place = models.CharField(max_length=40, blank=True, verbose_name=_('Delivery place'))
    arrival_time = models.TimeField(blank=True, null=True, verbose_name=_('Arrival time'))
    additional_copies = models.PositiveSmallIntegerField(default=3, verbose_name=_('Additional copies'))
    directions = models.TextField(blank=True, verbose_name=_('Directions'))
    distributor_directions = models.TextField(null=True, blank=True, verbose_name=_('Distributor directions'))
    notes = models.TextField(blank=True, verbose_name=_('Notes'))
    beach = models.BooleanField(default=False, verbose_name=_('Beach'))
    active = models.BooleanField(default=True, verbose_name=_('Active'))
    print_labels = models.BooleanField(default=True, verbose_name=_('Print labels from this route'))

    price_per_copy = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name=_('Price per copy'))
    parent_route = models.ForeignKey(
        'self', related_name='child_route', blank=True, null=True, verbose_name=_('Parent route'))

    def __unicode__(self):
        return _('Route %d') % self.number

    class Meta:
        verbose_name = _('Route')
        verbose_name_plural = _('Routes')
        ordering = ('number',)

    def sum_copies_per_product(self, product=None, new=False):
        """
        Returns a dictionary with the total sum of products per route.

        If a product is passed, then it only shows a sum of the selected product.

        If "new" is passed as True, then only the people who are new subscribers (subscription date between today
        and a week ago) are going to be shown.
        """
        if product is None:
            subprods = SubscriptionProduct.objects.filter(route=self, subscription__active=True)
        else:
            subprods = SubscriptionProduct.objects.filter(route=self, product=product, subscription__active=True)
        if new:
            subprods = subprods.filter(subscription__start_date__gte=date.today() - timedelta(7))
        subprods = subprods.aggregate(Sum('copies'))
        return subprods['copies__sum']

    def sum_promos_per_product(self, product=None):
        """
        Returns a dictionary with the total sum of products per route, except it ONLY shows promotion type
        subscriptions.

        If a product is passed, then it only shows a sum of the selected product.

        If "new" is passed as True, then only the people who are new subscribers (subscription date between today
        and a week ago) are going to be shown.
        """
        if product is None:
            subprods = SubscriptionProduct.objects.filter(
                route=self, subscription__active=True, subscription__type='P').aggregate(Sum('copies'))
        else:
            subprods = SubscriptionProduct.objects.filter(
                route=self, product=product, subscription__active=True, subscription__type='P').aggregate(Sum('copies'))
        return subprods['copies__sum']

    def contacts_in_route_count(self):
        """
        Returns a count of how many distinct contacts there are in this route.
        """
        subprods = SubscriptionProduct.objects.filter(route=self).distinct('subscription__contact')
        return subprods.count

    def invoices_in_route(self):
        """
        Returns a count of how many invoices have been printed for this route, in a period between a week ago and
        today.
        """
        from invoicing.models import Invoice
        invoices = Invoice.objects.filter(
            route=self.number, print_date__range=(date.today() - timedelta(6), date.today()),
            canceled=False).count()
        return invoices

    def get_subscriptionproducts(self, product_id=None, isoweekday=None):
        queryset = self.subscriptionproduct_set.filter(subscription__active=True)
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        if isoweekday:
            queryset = queryset.filter(product__weekday=isoweekday)
        return queryset

    def get_subscriptionproducts_count(self):
        return self.get_subscriptionproducts().count()

    def get_subscriptionproducts_today_count(self):
        today_isoweekday = date.today().isoweekday()
        return self.get_subscriptionproducts(isoweekday=today_isoweekday).count()

    def get_subscriptionproducts_tomorrow_count(self):
        tomorrow_isoweekday = (date.today() + timedelta(1)).isoweekday()
        return self.get_subscriptionproducts(isoweekday=tomorrow_isoweekday).count()


class GeorefAddress(models.Model):
    """
    Stores geo ref addresses.
    """
    gid = models.IntegerField(
        primary_key=True, verbose_name=_('gid'))
    street_name = models.CharField(
        max_length=36, verbose_name=_('Street name'))
    street_number = models.IntegerField(
        verbose_name=_('Street number'))
    letter = models.CharField(
        null=True, blank=True, max_length=5, verbose_name=_('Letter'))

    the_geom = PointField(srid=32721)

    def __unicode__(self):
        return '{} {}{}'.format(self.street_name, self.street_number, (' ' + self.letter) if self.letter else '')

    class Meta:
        ordering = ('street_number',)
        verbose_name = _('geo ref address')
        verbose_name_plural = _('geo ref addresses')


class PickupPoint(models.Model):
    """
    A pickup point is a place where people can go and get their product, if we can't deliver it to certain places.
    """
    name = models.CharField(max_length=60, verbose_name=_('Name'))
    address = models.CharField(max_length=255, blank=True, null=True, verbose_name=_('Address'))
    old_pk = models.PositiveIntegerField(blank=True, null=True, db_index=True)

    def __unicode__(self):
        return u"{}{}".format(self.name, (u' ({})'.format(self.address)) if self.address else u'')

    class Meta:
        ordering = ('name',)
        verbose_name = _('pickup point')
        verbose_name_plural = _('pickup points')


class Resort(models.Model):
    """
    Stores data for resorts, usually vacation places where we don't reach or usually deliver to.
    """
    state = models.CharField(
        max_length=20, verbose_name=_('State'))
    if getattr(settings, 'USE_STATES_CHOICE'):
        state.choices = settings.STATES
    name = models.CharField(
        max_length=50, verbose_name=_('Name'))
    status = models.CharField(
        max_length=2, choices=RESORT_STATUS_CHOICES, verbose_name=_('Status'))
    confirmation_date = models.DateField(
        blank=True, null=True, verbose_name=_('Confirmation date'))
    notes = models.TextField(
        blank=True, null=True, verbose_name=_('Notes'))
    arrival_time = models.TimeField(
        blank=True, null=True, verbose_name=_('Arrival time'))
    route = models.ForeignKey(
        Route, blank=True, null=True, verbose_name=_('Route'))
    order = models.PositiveSmallIntegerField(
        default=0, verbose_name=_('Order'))

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = _('resort')
        verbose_name_plural = _('resorts')
        ordering = ('order',)


class PickupPlace(models.Model):
    """
    This is a place in resorts where people can go and get their products.
    """
    resort = models.ForeignKey(Resort, verbose_name=_('Resort'))
    description = models.TextField(verbose_name=_('Description'))
    the_geom = PointField(blank=True, null=True)

    def __unicode__(self):
        return self.description

    class Meta:
        verbose_name = _('pickup place')
        verbose_name_plural = _('pickup places')
        ordering = ('resort',)


class City(models.Model):
    """
    Stores data of cities.
    """
    name = models.CharField(max_length=40, unique=True, verbose_name=_('Name'))
    state = models.CharField(max_length=20, verbose_name=_('City'))
    if getattr(settings, 'USE_STATES_CHOICE'):
        state.choices = settings.STATES

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = _('city')
        verbose_name_plural = _('cities')
        ordering = ('name',)


class Message(models.Model):
    """
    These are messages to be used in labels.

    TODO: Check if this is True.
    """
    place = models.CharField(
        max_length=20, unique=True, choices=MESSAGE_PLACES, verbose_name=_('Place'))
    text = models.TextField(
        blank=True, verbose_name=_('Text'))

    def __unicode__(self):
        return self.place

    class Meta:
        verbose_name = _('message')
        verbose_name_plural = _('messages')


class Delivery(models.Model):
    """
    Stores information of how many copies were delivered by route, each day.
    """
    date = models.DateField(
        verbose_name=_('Date'))
    route = models.IntegerField(
        verbose_name=_('Route'))
    copies = models.IntegerField(
        verbose_name=_('Copies'), null=True, blank=True)

    class Meta:
        verbose_name = _('delivery')
        verbose_name_plural = _('deliveries')


class RouteChange(models.Model):
    """
    A log model for when a contact changes route. It only uses model information.
    """
    dt = models.DateTimeField(
        auto_now_add=True, verbose_name=_('Dt'))
    contact = models.ForeignKey(
        'core.Contact', verbose_name=_('Contact'))
    product = models.ForeignKey(
        'core.Product', verbose_name=_('Product'), null=True, blank=True)
    old_route = models.ForeignKey(
        Route, verbose_name=_('Old route'))
    old_address = models.CharField(
        max_length=255, null=True, blank=True, verbose_name=_('Old address'))
    old_city = models.CharField(
        max_length=64, null=True, blank=True, verbose_name=_('Old city'))

    class Meta:
        verbose_name = _('route change')
        verbose_name_plural = _('route changes')


class Edition(models.Model):
    """
    Stores information on how many products were sent each day.

    TODO: Store information for each product on a many to many or similar.
    """
    product = models.ForeignKey('core.Product', verbose_name=_('Product'))
    number = models.PositiveSmallIntegerField(null=True, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    month = models.PositiveSmallIntegerField(null=True, blank=True)
    date = models.DateField(
        verbose_name=_('Date'))
    start_time = models.TimeField(
        blank=True, null=True, verbose_name=_('Start time'))
    end_time = models.TimeField(
        blank=True, null=True, verbose_name=_('End Time'))
    standard = models.IntegerField(
        blank=True, null=True, verbose_name=_('Standard'))
    digital = models.IntegerField(
        blank=True, null=True, verbose_name=_('Digital'))
    free = models.IntegerField(
        blank=True, null=True, verbose_name=_('Free'))
    promotions = models.IntegerField(
        blank=True, null=True, verbose_name=_('Promotions'))
    total = models.IntegerField(
        blank=True, null=True, verbose_name=_('Total'))
    extras = models.IntegerField(
        blank=True, null=True, verbose_name='Extras')
    rounding = models.IntegerField(
        blank=True, null=True)

    old_pk = models.PositiveIntegerField(blank=True, null=True)

    def get_date(self):
        """
        Returns date in a format for better visualization
        """
        return self.date.strftime("%a %x")

    class Meta:
        verbose_name = _('edition')
        verbose_name_plural = _('editions')
        unique_together = ('product', 'date')

    def __unicode__(self):
        return _('Edition %s %s') % (self.product, self.date)


class EditionRoute(models.Model):
    """
    Stores data for every edition on each route
    """
    edition = models.ForeignKey(Edition, verbose_name=_('Edition'))
    route = models.ForeignKey(Route, verbose_name=_('Route'))
    promotions = models.IntegerField(blank=True, null=True, verbose_name=_('Promotions'))

    class Meta:
        verbose_name = _('edition route')
        verbose_name_plural = _('edition routes')


class EditionProduct(models.Model):
    product = models.ForeignKey('core.Product', verbose_name=_('Product'))
    route = models.ForeignKey(Route, verbose_name=_('Route'))
    additional_copies = models.PositiveSmallIntegerField(default=3, verbose_name=_('Additional copies'))
