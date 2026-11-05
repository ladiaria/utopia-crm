# Las suscripciones ya no se pueden crear desde el admin

- **Fecha:** 2026-11-04
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl96-cerrar-alta-suscripcion-admin (it/utopia-crm-ladiaria#96)
- **Tipo:** Corrección
- **Componente:** Core (admin de suscripciones)
- **Impacto:** Rendimiento, Integridad de datos

## 🎯 Resumen

Las suscripciones se crean desde el contacto, pero el admin seguía ofreciendo su propia pantalla de alta. Nadie debería usarla: se saltea ese flujo y arma un desplegable con todas las direcciones de la base, el mismo tipo de pantalla que dejó sin memoria al servidor de producción en gl96. La pantalla de alta queda cerrada para todos, superusuarios incluidos, y el formulario del admin ya no puede listar todas las direcciones.

## ✨ Cambios

### 1. La pantalla de alta queda cerrada

**Archivo:** `core/admin.py`

`SubscriptionAdmin.has_add_permission` devuelve `False`. El admin evalúa este método antes de mirar los permisos del usuario, así que un superusuario también recibe un 403, y el botón de agregar desaparece del listado. Los paquetes de customización que heredan de `SubscriptionAdmin` lo heredan también.

### 2. El desplegable nunca lista toda la tabla

**Archivo:** `core/forms.py`

`SubscriptionAdminForm` sólo filtraba `billing_address` cuando tenía una instancia. Sin instancia, ahora no lista ninguna dirección:

```python
self.fields['billing_address'].queryset = (
    Address.objects.filter(contact=instance.contact) if instance else Address.objects.none()
)
```

Editar una suscripción funciona como antes, con las direcciones de su contacto.

### 3. Tests

**Archivo:** `tests/test_subscription_admin.py`

Un superusuario recibe un 403 con GET y con POST y no se crea nada, el listado no tiene botón de agregar, la pantalla de edición sólo lista las direcciones del contacto, y el formulario sin suscripción no lista ninguna.

## 📁 Archivos Modificados

- **`core/admin.py`** — `has_add_permission` en `SubscriptionAdmin`.
- **`core/forms.py`** — `SubscriptionAdminForm` nunca lista todas las direcciones.
- **`CHANGELOG.md`** — Entrada.

## 📁 Archivos Creados

- **`tests/test_subscription_admin.py`** — Tests de la pantalla de alta cerrada y del desplegable.
- **`docs/en/devnotes/2026-11-04-gl96-close-subscription-add-in-admin.md`** — Versión en inglés.
- **`docs/es/devnotes/2026-11-04-gl96-cerrar-alta-de-suscripciones-en-admin.md`** — Esta nota.

## 🧪 Pruebas Manuales

1. **Editar sigue funcionando (caso feliz):**
   - Como superusuario, abrir una suscripción en el admin (`/admin/core/subscription/<id>/change/`).
   - **Verificar:** la pantalla carga rápido, y el desplegable de dirección de facturación sólo tiene las direcciones de su contacto.

2. **La pantalla de alta está cerrada, incluso para un superusuario (caso borde):**
   - Como superusuario, abrir el listado de suscripciones en el admin y después ir a `/admin/core/subscription/add/`.
   - **Verificar:** el listado no tiene botón de agregar, y la URL responde 403.

3. **El flujo de siempre:**
   - Crear una suscripción desde el detalle del contacto.
   - **Verificar:** funciona como antes.

## 📝 Notas de Despliegue

- No se requieren migraciones.
- No hay traducciones nuevas.

---

- **Fecha:** 2026-11-04
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl96-cerrar-alta-suscripcion-admin
- **Tipo de cambio:** Corrección
- **Módulos afectados:** Core
