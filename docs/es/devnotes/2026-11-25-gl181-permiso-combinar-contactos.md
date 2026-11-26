# Permiso para combinar contactos

- **Fecha:** 2026-11-25
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#181
- **Tipo:** Funcionalidad
- **Componente:** Modelos de core
- **Impacto:** Permisos

## 🎯 Resumen

El base tiene la lógica para combinar dos contactos (`Contact.merge_other_contact_into_this`) pero no un permiso para
eso, así que un paquete de customización que ofrece una pantalla de fusión sólo podía controlarla por grupo (en la
diaria, Admins o superusuarios). Este cambio agrega `core.can_merge_contacts` al modelo `Contact`, igual que ya existe
`core.can_merge_addresses` en `Address`, para poder darle la fusión a un grupo sin hacerlo Admin.

## ✨ Cambios

### 1. El permiso en `Contact`

**Archivos:** `core/models.py`, `core/migrations/0129_contact_can_merge_contacts.py`

```python
class Meta:
    ...
    permissions = [
        ("can_merge_contacts", _("Can merge contacts")),
    ]
```

La migración es un `AlterModelOptions`. Django crea el permiso en el `post_migrate`, y ningún grupo lo recibe.

### 2. Traducción

**Archivo:** `locale/es/LC_MESSAGES/django.po`

«Puede combinar contactos», al lado de «Puede combinar direcciones». La entrada se agregó a mano: `makemessages`
renumera todas las referencias del archivo y convierte un cambio chico en miles de líneas.

## 📁 Archivos Modificados

- **`core/models.py`**: `permissions` en el `Meta` de `Contact`
- **`locale/es/LC_MESSAGES/django.po`**: traducción del permiso
- **`tests/test_contact_merge.py`**: el permiso existe sobre `core.contact`
- **`CHANGELOG.md`**: entrada de este cambio

## 📁 Archivos Creados

- **`core/migrations/0129_contact_can_merge_contacts.py`**: agrega el permiso al `Meta`

## 🧪 Pruebas Manuales

1. **Caso normal:**
   - Correr `python manage.py migrate`
   - En el admin, abrir un grupo
   - **Verificar:** «core | contacto | Puede combinar contactos» está en la lista de permisos disponibles
2. **Caso borde:**
   - Revisar que ningún grupo tenga el permiso apenas se migra
   - **Verificar:** el base no lo usa solo, así que nada cambia para nadie hasta que un paquete lo chequee

## 📝 Notas de Despliegue

- **Se requieren migraciones:** `python manage.py migrate`
- Sin settings
- En el paquete de la diaria, la pantalla de fusión lo chequea (it/utopia-crm-ladiaria#181, rama
  `gl181-permiso-fusionar-contactos`). Mergear antes este PR. En el otro orden no se rompe nada: `has_perm` da
  `False` y fusionan sólo Admins y superusuarios, como hasta ahora.

## 🎓 Decisiones de Diseño

- **En el base y no en el paquete:** la lógica de la fusión vive en el base, al lado del permiso de combinar
  direcciones. Un permiso creado por una migración del paquete sobre el ContentType de `core.contact` también
  funciona, pero no lo declararía ningún modelo.

---

- **Fecha:** 2026-11-25
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl181-permiso-fusionar-contactos
- **Tipo:** Funcionalidad
- **Módulos afectados:** core
