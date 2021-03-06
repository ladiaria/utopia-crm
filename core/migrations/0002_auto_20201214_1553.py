# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-12-14 15:53
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import taggit.managers


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('support', '0001_initial'),
        ('taggit', '0002_auto_20150616_2121'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('logistics', '0001_initial'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscriptionproduct',
            name='route',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='route', to='logistics.Route', verbose_name='Route'),
        ),
        migrations.AddField(
            model_name='subscriptionproduct',
            name='subscription',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.Subscription'),
        ),
        migrations.AddField(
            model_name='subscriptionnewsletter',
            name='contact',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.Contact'),
        ),
        migrations.AddField(
            model_name='subscriptionnewsletter',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.Product'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='billing_address',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='billing_contacts', to='core.Address', verbose_name='Billing address'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='campaign',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.Campaign', verbose_name='Campaign'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='contact',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subscriptions', to='core.Contact', verbose_name='Contact'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='pickup_point',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='logistics.PickupPoint', verbose_name='Pickup point'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='products',
            field=models.ManyToManyField(through='core.SubscriptionProduct', to='core.Product'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='seller',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='support.Seller', verbose_name='Seller'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='unsubscription_manager',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Unsubscription manager'),
        ),
        migrations.AddField(
            model_name='pricerule',
            name='choose_one_product',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='chosen_product', to='core.Product'),
        ),
        migrations.AddField(
            model_name='pricerule',
            name='products_not_pool',
            field=models.ManyToManyField(blank=True, related_name='not_pool', to='core.Product'),
        ),
        migrations.AddField(
            model_name='pricerule',
            name='products_pool',
            field=models.ManyToManyField(related_name='pool', to='core.Product'),
        ),
        migrations.AddField(
            model_name='pricerule',
            name='resulting_product',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='resulting_product', to='core.Product'),
        ),
        migrations.AddField(
            model_name='dynamiccontactfilter',
            name='newsletters',
            field=models.ManyToManyField(blank=True, related_name='newsletters', to='core.Product'),
        ),
        migrations.AddField(
            model_name='dynamiccontactfilter',
            name='products',
            field=models.ManyToManyField(blank=True, related_name='products', to='core.Product'),
        ),
        migrations.AddField(
            model_name='contactproducthistory',
            name='campaign',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.Campaign'),
        ),
        migrations.AddField(
            model_name='contactproducthistory',
            name='contact',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.Contact'),
        ),
        migrations.AddField(
            model_name='contactproducthistory',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.Product'),
        ),
        migrations.AddField(
            model_name='contactproducthistory',
            name='subscription',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.Subscription'),
        ),
        migrations.AddField(
            model_name='contactcampaignstatus',
            name='campaign',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.Campaign'),
        ),
        migrations.AddField(
            model_name='contactcampaignstatus',
            name='contact',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.Contact'),
        ),
        migrations.AddField(
            model_name='contactcampaignstatus',
            name='seller_resolution',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='support.Seller'),
        ),
        migrations.AddField(
            model_name='contact',
            name='institution',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.Institution', verbose_name='Institution'),
        ),
        migrations.AddField(
            model_name='contact',
            name='ocupation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.Ocupation', verbose_name='Ocupation'),
        ),
        migrations.AddField(
            model_name='contact',
            name='referrer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referred', to='core.Contact', verbose_name='Referrer'),
        ),
        migrations.AddField(
            model_name='contact',
            name='seller',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='support.Seller'),
        ),
        migrations.AddField(
            model_name='contact',
            name='subtype',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.Subtype', verbose_name='Subtype'),
        ),
        migrations.AddField(
            model_name='contact',
            name='tags',
            field=taggit.managers.TaggableManager(blank=True, help_text='A comma-separated list of tags.', through='taggit.TaggedItem', to='taggit.Tag', verbose_name='Tags'),
        ),
        migrations.AddField(
            model_name='campaign',
            name='product',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.Product'),
        ),
        migrations.AddField(
            model_name='address',
            name='contact',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='addresses', to='core.Contact', verbose_name='Contact'),
        ),
        migrations.AddField(
            model_name='address',
            name='geo_ref_address',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='logistics.GeorefAddress', verbose_name='GeorefAddress'),
        ),
        migrations.AddField(
            model_name='activity',
            name='campaign',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.Campaign'),
        ),
        migrations.AddField(
            model_name='activity',
            name='contact',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.Contact'),
        ),
        migrations.AddField(
            model_name='activity',
            name='issue',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='support.Issue', verbose_name='Issue'),
        ),
        migrations.AddField(
            model_name='activity',
            name='product',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.Product'),
        ),
        migrations.AddField(
            model_name='activity',
            name='seller',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='support.Seller', verbose_name='Seller'),
        ),
    ]
