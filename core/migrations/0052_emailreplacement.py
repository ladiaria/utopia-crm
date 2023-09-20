# Generated by Django 4.1.4 on 2023-09-12 11:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0051_address_needs_georef_historicaladdress_needs_georef_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailReplacement',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=252, unique=True)),
                ('replacement', models.CharField(max_length=252)),
                ('status', models.CharField(choices=[('requested', 'Requested'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='requested', max_length=15)),
            ],
            options={
                'ordering': ('status', 'domain'),
            },
        ),
    ]
