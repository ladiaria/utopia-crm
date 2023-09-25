# Generated by Django 4.1.4 on 2023-09-15 21:54

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0052_emailreplacement'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailBounceActionLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateField(auto_now_add=True)),
                ('email', models.EmailField(editable=False, max_length=254)),
                ('action', models.PositiveSmallIntegerField(choices=[(1, 'invalid email'), (2, 'max bounce reached')])),
                ('contact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.contact')),
            ],
        ),
    ]
