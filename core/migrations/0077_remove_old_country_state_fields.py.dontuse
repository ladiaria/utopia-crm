from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0076_migrate_country_state_data'),
    ]

    operations = [
        # First remove the old fields
        migrations.RemoveField(
            model_name='address',
            name='country',
        ),
        migrations.RemoveField(
            model_name='address',
            name='state',
        ),

        # Then rename the new fields to the simpler names
        migrations.RenameField(
            model_name='address',
            old_name='country_new',
            new_name='country',
        ),
        migrations.RenameField(
            model_name='address',
            old_name='state_new',
            new_name='state',
        ),
    ]
