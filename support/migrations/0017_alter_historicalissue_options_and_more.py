# Generated by Django 4.1.4 on 2023-09-24 02:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('support', '0016_auto_20221017_1513'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='historicalissue',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical issue', 'verbose_name_plural': 'historical issues'},
        ),
        migrations.AlterModelOptions(
            name='historicalscheduledtask',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical scheduled task', 'verbose_name_plural': 'historical scheduled tasks'},
        ),
        migrations.AlterField(
            model_name='historicalissue',
            name='history_date',
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name='historicalscheduledtask',
            name='history_date',
            field=models.DateTimeField(db_index=True),
        ),
    ]
