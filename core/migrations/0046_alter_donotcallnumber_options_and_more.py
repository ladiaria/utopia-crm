# Generated by Django 4.1.4 on 2023-07-28 13:28

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_donotcallnumber'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='donotcallnumber',
            options={'ordering': ['number']},
        ),
        migrations.AlterModelOptions(
            name='historicalactivity',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical activity', 'verbose_name_plural': 'historical activities'},
        ),
        migrations.AlterModelOptions(
            name='historicaladdress',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical address', 'verbose_name_plural': 'historical addresses'},
        ),
        migrations.AlterModelOptions(
            name='historicalcontact',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical contact', 'verbose_name_plural': 'historical contacts'},
        ),
        migrations.AlterModelOptions(
            name='historicalpricerule',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical price rule', 'verbose_name_plural': 'historical price rules'},
        ),
        migrations.AlterModelOptions(
            name='historicalsubscription',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical subscription', 'verbose_name_plural': 'historical subscriptions'},
        ),
        migrations.RemoveField(
            model_name='historicalpricerule',
            name='add_wildcard',
        ),
        migrations.RemoveField(
            model_name='pricerule',
            name='add_wildcard',
        ),
        migrations.AddField(
            model_name='historicalpricerule',
            name='amount_to_pick_condition',
            field=models.CharField(choices=[('eq', 'Equal than'), ('gt', 'Greater than')], default='eq', max_length=2),
        ),
        migrations.AddField(
            model_name='historicalpricerule',
            name='wildcard_mode',
            field=models.CharField(blank=True, choices=[('pool_and_any', 'Pool AND Any'), ('pool_or_any', 'Pool OR Any')], max_length=12, null=True),
        ),
        migrations.AddField(
            model_name='pricerule',
            name='amount_to_pick_condition',
            field=models.CharField(choices=[('eq', 'Equal than'), ('gt', 'Greater than')], default='eq', max_length=2),
        ),
        migrations.AddField(
            model_name='pricerule',
            name='wildcard_mode',
            field=models.CharField(blank=True, choices=[('pool_and_any', 'Pool AND Any'), ('pool_or_any', 'Pool OR Any')], max_length=12, null=True),
        ),
        migrations.AlterField(
            model_name='advanceddiscount',
            name='discount_product',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='discount', to='core.product'),
        ),
        migrations.AlterField(
            model_name='contact',
            name='protected',
            field=models.BooleanField(blank=True, default=False, verbose_name='Protected'),
        ),
        migrations.AlterField(
            model_name='contactcampaignstatus',
            name='resolution_reason',
            field=models.SmallIntegerField(blank=True, choices=[], null=True),
        ),
        migrations.AlterField(
            model_name='dynamiccontactfilter',
            name='newsletters',
            field=models.ManyToManyField(blank=True, limit_choices_to={'type': 'N'}, related_name='newsletters', to='core.product'),
        ),
        migrations.AlterField(
            model_name='dynamiccontactfilter',
            name='products',
            field=models.ManyToManyField(blank=True, limit_choices_to={'offerable': True}, related_name='products', to='core.product'),
        ),
        migrations.AlterField(
            model_name='historicalactivity',
            name='history_date',
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name='historicaladdress',
            name='history_date',
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name='historicalcontact',
            name='history_date',
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name='historicalcontact',
            name='protected',
            field=models.BooleanField(blank=True, default=False, verbose_name='Protected'),
        ),
        migrations.AlterField(
            model_name='historicalpricerule',
            name='choose_one_product',
            field=models.ForeignKey(blank=True, db_constraint=False, limit_choices_to={'offerable': True, 'type': 'S'}, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='core.product'),
        ),
        migrations.AlterField(
            model_name='historicalpricerule',
            name='history_date',
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name='historicalpricerule',
            name='resulting_product',
            field=models.ForeignKey(blank=True, db_constraint=False, limit_choices_to={'offerable': False}, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='core.product'),
        ),
        migrations.AlterField(
            model_name='historicalsubscription',
            name='history_date',
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name='pricerule',
            name='choose_one_product',
            field=models.ForeignKey(blank=True, limit_choices_to={'offerable': True, 'type': 'S'}, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='chosen_product', to='core.product'),
        ),
        migrations.AlterField(
            model_name='pricerule',
            name='products_not_pool',
            field=models.ManyToManyField(blank=True, limit_choices_to={'type__in': 'DSAP'}, related_name='not_pool', to='core.product'),
        ),
        migrations.AlterField(
            model_name='pricerule',
            name='products_pool',
            field=models.ManyToManyField(limit_choices_to={'offerable': True, 'type__in': 'DS'}, related_name='pool', to='core.product'),
        ),
        migrations.AlterField(
            model_name='pricerule',
            name='resulting_product',
            field=models.ForeignKey(blank=True, limit_choices_to={'offerable': False}, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='resulting_product', to='core.product'),
        ),
        migrations.AlterField(
            model_name='subscriptionnewsletter',
            name='product',
            field=models.ForeignKey(limit_choices_to={'type': 'N'}, on_delete=django.db.models.deletion.CASCADE, to='core.product'),
        ),
        migrations.AlterField(
            model_name='subscriptionproduct',
            name='product',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='core.product'),
        ),
    ]
