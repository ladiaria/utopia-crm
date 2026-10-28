"""
Management command para detectar y opcionalmente borrar direcciones (Address) completamente
vacias: sin calle, sin ciudad, sin notas ni georreferenciacion. No confundir con direcciones
huerfanas (sin suscripcion asociada) pero con datos cargados -- esas son validas y no se tocan.

Los Issue y ScheduledTask que apuntan a una direccion borrada quedan, sin la direccion
(on_delete=SET_NULL). Se excluyen solo las direcciones de un cambio de direccion pendiente: borrarlas
deja la tarea sin ejecutar. Esas se reportan aparte para revision manual.

Usage:
    # Dry run - reporta las direcciones vacias encontradas
    python manage.py cleanup_empty_addresses

    # Las borra de verdad
    python manage.py cleanup_empty_addresses --fix
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
from tqdm import tqdm

from core.models import Address
from support.models import Issue, ScheduledTask


def _empty_addresses_queryset():
    blank = lambda field: Q(**{f"{field}__isnull": True}) | Q(**{f"{field}__exact": ""})  # noqa: E731
    return Address.objects.filter(
        blank("address_1"),
        blank("address_2"),
        blank("city"),
        blank("notes"),
        blank("google_maps_url"),
        blank("picture"),
        georef_point__isnull=True,
    )


class Command(BaseCommand):
    help = "Detecta y opcionalmente borra direcciones completamente vacias (default: dry run)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Borra las direcciones vacias encontradas (default: dry run, solo reporta)",
        )

    def handle(self, *args, **options):
        fix_mode = options["fix"]

        self.stdout.write(self.style.WARNING("=" * 80))
        self.stdout.write(self.style.WARNING("LIMPIEZA DE DIRECCIONES VACIAS"))
        self.stdout.write(
            self.style.WARNING(
                "FIX MODE: se van a borrar las direcciones vacias" if fix_mode else "DRY RUN: no se borra nada"
            )
        )
        self.stdout.write(self.style.WARNING("=" * 80))
        self.stdout.write("")

        empty_qs = _empty_addresses_queryset().select_related("contact")
        total = empty_qs.count()
        self.stdout.write(self.style.SUCCESS(f"Direcciones vacias encontradas: {total}"))

        if total == 0:
            self.stdout.write(self.style.SUCCESS("No hay direcciones vacias. Todo bien."))
            return

        empty_ids = list(empty_qs.values_list("id", flat=True))
        blocked_ids = set(
            ScheduledTask.objects.filter(address_id__in=empty_ids, category="AC", completed=False).values_list(
                "address_id", flat=True
            )
        )
        unblocked_ids = [address_id for address_id in empty_ids if address_id not in blocked_ids]
        issues_left = Issue.objects.filter(address_id__in=unblocked_ids).count()
        tasks_left = ScheduledTask.objects.filter(address_id__in=unblocked_ids).count()

        deleted_count = 0
        action_desc = "Borrando direcciones vacias" if fix_mode else "Procesando direcciones vacias"
        for address in tqdm(empty_qs, total=total, desc=action_desc, unit="address"):
            if address.id in blocked_ids:
                tqdm.write(
                    f"  [OMITIDA] Address #{address.id} (contact_id={address.contact_id}) es la de un "
                    "cambio de direccion pendiente; revisar manualmente."
                )
                continue

            action = "BORRADA" if fix_mode else "SE BORRARIA"
            tqdm.write(f"  [{action}] Address #{address.id} (contact_id={address.contact_id})")
            if fix_mode:
                address.delete()
                deleted_count += 1

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("=" * 80))
        self.stdout.write(self.style.WARNING("RESUMEN"))
        self.stdout.write(self.style.WARNING("=" * 80))
        self.stdout.write(f"Total vacias encontradas: {total}")
        self.stdout.write(f"Omitidas por un cambio de direccion pendiente: {len(blocked_ids)}")
        self.stdout.write(f"Issues que quedan sin direccion: {issues_left}")
        self.stdout.write(f"ScheduledTasks que quedan sin direccion: {tasks_left}")

        if fix_mode:
            self.stdout.write(self.style.SUCCESS(f"Borradas: {deleted_count}"))
        else:
            self.stdout.write(self.style.WARNING(f"Se borrarian: {total - len(blocked_ids)}"))
            self.stdout.write("")
            self.stdout.write("Correr con --fix para borrarlas de verdad:")
            self.stdout.write(self.style.SUCCESS("  python manage.py cleanup_empty_addresses --fix"))
