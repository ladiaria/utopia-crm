# Vistas basadas en clase que no chequeaban nada

- **Fecha:** 2026-11-25
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#185
- **Tipo:** Corrección de errores
- **Componente:** Support, API de Core
- **Impacto:** Seguridad, Permisos

## 🎯 Resumen

La revisión de accesos de it/utopia-crm-ladiaria#183 cubrió las vistas funcionales enrutadas. Este cambio la termina
con las basadas en clase: se recorrieron todas las vistas enrutadas buscando vistas de clase sin mixin ni decorador de
acceso, y vistas de DRF sin `permission_classes`. El base no define `REST_FRAMEWORK`, así que el default de DRF es
`AllowAny`.

Cuatro vistas y un endpoint de API no chequeaban nada. Ahora piden lo que ya pedían sus botones.

## ✨ Cambios

### 1. Suscripciones gratuitas

**Archivo:** `support/views/subscriptions.py`

`FreeSubscriptionMixin` definía un `test_func` que pedía `core.can_add_free_subscription`, pero ni
`CreateFreeSubscriptionView` ni `UpdateFreeSubscriptionView` heredaban `UserPassesTestMixin`, así que nadie lo llamaba.
Cualquiera con el link podía abrir las dos vistas, con sesión o sin ella. Ahora el mixin hereda `UserPassesTestMixin`
y el `test_func` que ya existía corre.

El botón «Crear suscripción gratuita» ya chequeaba `perms.core.can_add_free_subscription`, así que nadie que lo vea
pierde el acceso. Los botones «Actualizar suscripción gratuita» de la ficha (la tarjeta de la suscripción y la lista
del resumen) chequeaban en cambio el grupo Managers: ahora chequean el mismo permiso, así que un Manager sin él deja
de ver un botón que le daría 403.

### 2. Suscripción corporativa y edición de suscripción

**Archivo:** `support/views/subscriptions.py`

- `CorporateSubscriptionCreateView` pide `core.can_add_corporate_subscription`, el mismo permiso que su botón.
- `SubscriptionUpdateView` pide staff, igual que `SubscriptionCreateView`.

Un paquete de customización puede pisar estas URLs con sus propias vistas (`URLS_CUSTOM_MODULE`), pero las vistas del
base tienen que ser seguras para cualquier instalación que las use tal cual.

### 3. Endpoint de registro de APIs

**Archivo:** `core/serializers.py`

`ApiLogEntryViewSet` aceptaba POST sin API key y escribía una fila de `ApiLogEntry`. Ahora tiene
`permission_classes = [HasAPIKey]`, como las demás APIs del base que llaman otros sistemas.

`document-types` queda abierta a propósito: es un catálogo de sólo lectura de los tipos de documento.

## 📁 Archivos modificados

- **`support/views/subscriptions.py`**: `UserPassesTestMixin` en `FreeSubscriptionMixin`, y `test_func` en las vistas
  de corporativa y edición
- **`core/serializers.py`**: `HasAPIKey` en `ApiLogEntryViewSet`
- **`support/templates/contact_detail/tabs/includes/_subscription_card.html`**,
  **`support/templates/contact_detail/tabs/includes/_overview_subscription_list_item.html`**: el botón «Actualizar
  suscripción gratuita» chequea el permiso
- **`tests/test_access_checks.py`**: tests de las cuatro vistas y del endpoint
- **`CHANGELOG.md`**

## 🧪 Pruebas manuales

1. **Camino feliz:**
   - Con un usuario que tiene «Puede establecer suscripciones gratuitas», abrir un contacto y tocar «Crear suscripción
     gratuita»
   - **Verificar:** el formulario abre y la suscripción se crea como antes
2. **Caso borde:**
   - Con un usuario staff sin el permiso, abrir a mano `/support/contact/<id>/create-free-subscription/`
   - **Verificar:** 403. Sin sesión, la misma URL manda al login
3. **Caso borde:**
   - `POST /api/api-log-entry/` sin el header `Authorization: Api-Key …`
   - **Verificar:** 403, y no se crea ninguna fila de `ApiLogEntry`

## 📝 Notas de despliegue

- **No se requieren migraciones.**
- Antes de mergear, los logs de producción de la diaria (8 días) no mostraron ningún pedido a `/api/api-log-entry/`,
  y las únicas suscripciones gratuitas creadas en ese tiempo las hizo un usuario que tiene el permiso.

## 🎓 Decisiones de diseño

- **Los tests llaman a las vistas directo**, con `RequestFactory`, en vez de por su URL: `test_settings` carga
  `local_settings`, y el `URLS_CUSTOM_MODULE` de una instalación puede mandar las mismas URLs a sus propias vistas.
- **Las vistas conservan su propio `dispatch`**, que carga el contacto o la suscripción antes de que corra
  `UserPassesTestMixin`. Es el patrón que ya seguía `SubscriptionCreateView`, y ese código sólo lee.

---

- **Fecha:** 2026-11-25
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl185-vistas-de-clase-sin-chequeo
- **Tipo:** Corrección de errores
- **Módulos afectados:** support, core
