from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("support", "0040_absencereason_attendancerecord_shift_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sellerconsoleaction",
            name="campaign_resolution",
            field=models.CharField(
                blank=True,
                choices=[
                    ("SP", "Started promotion"),
                    ("AS", "Already a subscriber"),
                    ("DN", "Do not call anymore"),
                    ("EP", "Error in promotion"),
                    ("LO", "Logistics"),
                    ("NI", "Not interested"),
                    ("S1", "Success with promotion"),
                    ("S2", "Success with direct sale"),
                    ("SC", "Scheduled"),
                    ("CL", "Call later"),
                    ("NF", "Not found"),
                    ("UN", "Cannot find contact"),
                    ("CW", "Close without contact"),
                    ("LS", "Closed due to lost schedule"),
                ],
                help_text="Campaign resolution to set when this action is performed",
                max_length=2,
                null=True,
            ),
        ),
    ]
