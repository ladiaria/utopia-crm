# Generated by Django 4.1.13 on 2025-03-03 15:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0021_creditnote_old_pk_historicalcreditnote_old_pk'),
    ]

    operations = [
        migrations.CreateModel(
            name='TransactionType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
                ('code', models.CharField(blank=True, max_length=255, null=True, unique=True)),
                ('description', models.TextField(blank=True)),
            ],
            options={
                'verbose_name': 'Transaction Type',
                'verbose_name_plural': 'Transaction Types',
            },
        ),
    ]
