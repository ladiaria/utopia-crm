# Generated migration to change MercadoPagoData FK from Contact to Subscription

from django.db import migrations, models
import django.db.models.deletion


def migrate_contact_to_subscription(apps, schema_editor):
    """
    Migrate MercadoPagoData from contact to subscription.
    For each MercadoPagoData, find the active subscription for the contact,
    or the first subscription if no active one exists.
    """
    MercadoPagoData = apps.get_model('invoicing', 'MercadoPagoData')
    Subscription = apps.get_model('core', 'Subscription')
    Invoice = apps.get_model('invoicing', 'Invoice')

    for mp_data in MercadoPagoData.objects.all():
        contact = mp_data.contact

        # Try to find an active subscription first
        active_subscription = Subscription.objects.filter(
            contact=contact,
            active=True
        ).order_by('id').first()

        if active_subscription:
            mp_data.subscription = active_subscription
            mp_data.save()
            continue

        # If no active subscription, try to find via invoices
        invoice = Invoice.objects.filter(
            contact=contact,
            subscription__isnull=False
        ).order_by('-creation_date').first()

        if invoice and invoice.subscription:
            mp_data.subscription = invoice.subscription
            mp_data.save()
            continue

        # Last resort: get the first subscription for the contact
        first_subscription = Subscription.objects.filter(
            contact=contact
        ).order_by('id').first()

        if first_subscription:
            mp_data.subscription = first_subscription
            mp_data.save()
        else:
            # If no subscription found, we'll need to handle this case
            # For now, we'll skip it and it will need manual intervention
            print(f"WARNING: No subscription found for MercadoPagoData id={mp_data.id}, contact_id={contact.id}")
            # We'll delete this record as it can't be migrated
            mp_data.delete()


def reverse_migrate_subscription_to_contact(apps, schema_editor):
    """
    Reverse migration: set contact from subscription.
    """
    MercadoPagoData = apps.get_model('invoicing', 'MercadoPagoData')

    for mp_data in MercadoPagoData.objects.all():
        if mp_data.subscription:
            mp_data.contact = mp_data.subscription.contact
            mp_data.save()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0070_alter_product_billing_days_and_more'),  # Same as 0012_mercadopagodata
        ('invoicing', '0030_historicalinvoice_created_at_and_more'),
    ]

    operations = [
        # Step 1: Add subscription field as nullable
        migrations.AddField(
            model_name='mercadopagodata',
            name='subscription',
            field=models.OneToOneField(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='mercadopago_data',
                to='core.subscription'
            ),
        ),
        # Step 2: Migrate data
        migrations.RunPython(migrate_contact_to_subscription, reverse_migrate_subscription_to_contact),
        # Step 3: Remove contact field
        migrations.RemoveField(
            model_name='mercadopagodata',
            name='contact',
        ),
        # Step 4: Make subscription non-nullable
        migrations.AlterField(
            model_name='mercadopagodata',
            name='subscription',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='mercadopago_data',
                to='core.subscription'
            ),
        ),
    ]
