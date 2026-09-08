# Actividades huérfanas y links viejos de consola cuando un contacto sale de una campaña

- **Fecha:** 2026-09-08
- **Autor:** Tanya Tree + Claude Opus 5
- **Ticket:** t1176
- **Tipo:** Bug Fix
- **Componente:** Support — Campaign Management, Consola de vendedores, Suscripciones
- **Impacto:** Integridad de datos, colas de la consola de vendedores, experiencia de usuario

## 🎯 Resumen

`Activity` tiene una foreign key a `Campaign`, no a `ContactCampaignStatus`. Sacar un contacto de una
campaña borra la fila de `ContactCampaignStatus` y deja todas sus actividades atrás, apuntando
igual a la campaña. De ese único hecho salen dos síntomas que parecían no tener relación:

1. Una actividad pendiente sobrevivía a su estado de campaña y seguía apareciendo en la cola `act` de
   la consola. Peor: `handle_post_request` marcaba la actividad como completada **antes** de
   verificar el estado de campaña, así que resolverla producía el mensaje de error *"Contact is no
   longer in this campaign"* **y** además cerraba la actividad — una llamada que nunca ocurrió,
   registrada como hecha y sin agenda nueva.
2. `LadiariaSubscriptionCreateView` levantaba un `DoesNotExist` (HTTP 500) cada vez que el link de
   consola `?new=<ccs_id>` apuntaba a un `ContactCampaignStatus` borrado — una pestaña abierta, el
   botón "atrás" del navegador. La rama `act` de `capture_variables()` manejaba ese caso con un
   mensaje y un redirect, pero **ningún `dispatch` usaba el valor de retorno**, así que ese redirect
   era código muerto y la vista seguía adelante sin `self.ccs`.

Los rastros de producción que motivaron el ticket: el contacto 31806 tenía dos actividades en la
campaña 297 (*Mundo 2026*) sin estado de campaña, con la pendiente cerrada el 2026-08-28 por un
request que abortó; y la usuaria `sofia.fernandez` se topó con el 500 el 2026-08-28 con
`new=916086`, un estado borrado un mes antes por el borrado masivo por CSV.

## ✨ Cambios

### 1. El borrado masivo también se lleva las actividades abiertas

**Archivo:** `support/views/campaign_management.py`

`BulkDeleteCampaignStatusView` ahora borra las actividades todavía abiertas de esos mismos contactos
en esa misma campaña, dentro de la misma transacción que los estados de campaña:

```python
with transaction.atomic():
    deleted_activities, _unused = Activity.objects.filter(
        contact_id__in=contact_ids,
        campaign=campaign,
        status__in=[ACTIVITY_STATUS.PENDING, ACTIVITY_STATUS.DELAYED],
    ).delete()
    deleted_count, _unused = ContactCampaignStatus.objects.filter(
        contact_id__in=contact_ids, campaign=campaign
    ).delete()
```

Sólo se borran `PENDING` y `DELAYED`: son llamadas que nunca ocurrieron. Las completadas son historia
y quedan. Es lo mismo que ya hace `Contact.combine()` al fusionar contactos (`core/models.py`). El
mensaje de éxito informa los dos números.

### 2. La consola de vendedores verifica el estado de campaña primero

**Archivo:** `support/views/seller_console.py`

La verificación de existencia se movió antes de cualquier escritura, justo después de resolver la
acción de consola:

```python
if not ContactCampaignStatus.objects.filter(campaign=campaign, contact=contact).exists():
    messages.error(self.request, _("Contact is no longer in this campaign"))
    return HttpResponseRedirect(reverse("seller_console", args=[category, campaign.id]))
```

`process_activity_result()` sigue haciendo su propia búsqueda después — necesita la instancia para
actualizarla —, así que la garantía no es lógica duplicada sino orden: nada se escribe en un request
que va a abortar.

### 3. La cola `act` deja afuera a las huérfanas

**Archivo:** `support/views/seller_console.py`

`get_console_instances()` filtra las actividades pendientes por la existencia del estado de campaña,
de modo que las que quedaron huérfanas antes de este arreglo ya no se ofrecen:

```python
still_in_campaign = ContactCampaignStatus.objects.filter(
    campaign=campaign, contact=OuterRef("contact")
)
return (
    activities.filter(Exists(still_in_campaign))
    .select_related('seller_console_action')
    .order_by("datetime", "id")
)
```

De paso, la bifurcación por `ALLOW_ACCESSING_FUTURE_ACTIVITIES_IN_SELLER_CONSOLE` se aplanó en un
solo queryset, así el filtro se aplica una vez y no en cada return.

### 4. `capture_variables()` deja de confiar en el link, y quien lo llama lo respeta

**Archivos:** `support/views/subscriptions.py`,
`utopia-crm-ladiaria/utopia_crm_ladiaria/views/subscriptions.py`

La rama `new` hacía un `get()` pelado. Ahora se comporta como la rama `act`:

```python
try:
    self.ccs = ContactCampaignStatus.objects.get(pk=self.request.GET["new"])
except ContactCampaignStatus.DoesNotExist:
    messages.error(
        self.request,
        _("The contact is no longer in this campaign, instance number: {}").format(
            self.request.GET["new"]
        ),
    )
    return HttpResponseRedirect(reverse("seller_console_list_campaigns"))
```

La rama `act` recibió el mismo tratamiento para una `Activity` borrada, y las dos ramas ahora leen
`self.ccs.seller_id` en lugar de `self.ccs.seller.id`, que levantaba `AttributeError` cuando el
estado de campaña no tenía vendedor.

La mitad importante es quien llama. Todos los `dispatch()` que invocaban `capture_variables()`
descartaban su valor de retorno, así que los redirects de arriba nunca habrían llegado al navegador:

```python
response = self.capture_variables()
if response:
    return response
return super().dispatch(request, *args, **kwargs)
```

Esto aplica a los dos `dispatch` de `SubscriptionMixin`, al de `CorporateSubscriptionCreateView`, a
los tres de `utopia_crm_ladiaria` y al override ladiaria de `capture_variables()`, que también se
tragaba la respuesta de `super()`.

## 📁 Archivos modificados

- **`support/views/campaign_management.py`** — el borrado masivo también elimina las actividades
  abiertas; el mensaje de éxito informa la cantidad
- **`support/views/seller_console.py`** — se verifica el estado de campaña antes de escribir; la cola
  `act` se filtra con `Exists`
- **`support/views/subscriptions.py`** — las ramas `new` y `act` manejan las filas faltantes;
  `seller_id` en vez de `seller.id`; tres `dispatch` respetan la respuesta devuelta
- **`tests/test_seller_console.py`** — nueva `TestSellerConsoleContactRemovedFromCampaign`

## 📚 Detalles técnicos

**Por qué las huérfanas pasaron desapercibidas tanto tiempo.** `BulkDeleteCampaignStatusView` existe
desde el 2025-11-14, estuvo deshabilitada entre el 2026-03-19 y el 2026-05-25, y sólo registra un
`LogEntry` por fila borrada desde t1147 (2026-05-25). Los borrados anteriores a esa fecha no dejaron
ningún rastro, y por eso la mayoría de los pares huérfanos no se pueden explicar desde
`django_admin_log`. Los que sí se pueden se reconocen por su `change_message`: *"Bulk delete via CSV
by …"*.

**Escala sobre el dump de producción del 2026-09-03.** 13.589 actividades sobre 5.337 contactos y 251
campañas no tenían estado de campaña asociado. Restringido a actividad en 2026: 2.042 contactos, de
los cuales 1.037 quedaron con la gestión por la mitad (última acción de consola de tipo `SCHEDULED`,
`CALL_LATER`, `NOT_FOUND` o `PENDING`) y sin suscripción activa — el listado que se le pasó al área
de distribución para volver a subirlos a una campaña y llamarlos de nuevo. Sólo 8 actividades seguían
pendientes y trabajables; 6 sobrevivieron hasta el día de la limpieza y se borraron en producción.

**Compatibilidad hacia atrás.** No hay cambios de modelo ni de esquema. El filtro `Exists` agrega una
subconsulta `EXISTS` sobre un queryset ya filtrado por campaña y vendedor, apoyada en el índice único
`(contact_id, campaign_id)` de `ContactCampaignStatus`.

## 🧪 Pruebas manuales

1. **El borrado masivo limpia las agendas (camino feliz):**
   - Elegir una campaña y un contacto que esté en ella con una llamada agendada pendiente.
   - Ir a *Campaign Management → Bulk Delete Campaign Status*, subir un CSV con ese `contact_id` y
     seleccionar la campaña.
   - **Verificar:** el mensaje de éxito informa 1 estado de campaña y 1 actividad borrados; la cola
     `act` del vendedor para esa campaña ya no ofrece el contacto.

2. **Contacto sacado de la campaña con una agenda abierta (caso borde):**
   - Crear una actividad pendiente para un contacto en una campaña y después borrar el
     `ContactCampaignStatus` directamente desde el admin (simulando los datos viejos).
   - Abrir la cola `act` de la consola para esa campaña.
   - **Verificar:** el contacto no aparece. Si se fuerza la URL del ítem a mano y se envía un
     resultado, aparece el mensaje *"Contact is no longer in this campaign"* **y** la actividad sigue
     pendiente, no completada.

3. **Link viejo de la consola hacia una venta (caso borde):**
   - Abrir la cola `new` de la consola y copiar el link de "vender" de un contacto
     (`…/new_subscription/?new=<id>&…`).
   - Borrar ese `ContactCampaignStatus` y después cargar el link copiado.
   - **Verificar:** no hay 500. La página redirige a la lista de campañas con el mensaje *"The contact
     is no longer in this campaign, instance number: …"*.

## 📝 Notas de despliegue

- No se requieren migraciones.
- No hay cambios de configuración.
- Limpieza posterior opcional, para las actividades pendientes que quedaron huérfanas antes del
  arreglo:

  ```sql
  DELETE FROM core_activity a
  USING (
    SELECT a2.id FROM core_activity a2
    LEFT JOIN core_contactcampaignstatus ccs
           ON ccs.contact_id = a2.contact_id AND ccs.campaign_id = a2.campaign_id
    WHERE a2.campaign_id IS NOT NULL AND a2.status = 'P' AND ccs.id IS NULL
  ) h WHERE a.id = h.id;
  ```

  Correr primero el `SELECT` solo: con el arreglo desplegado debería devolver pocas filas o ninguna.
- El paquete ladiaria tiene que desplegarse junto con la app base: el arreglo de los `dispatch`
  abarca los dos.

## 🚀 Mejoras futuras

- Los contadores del dashboard (`Seller.get_campaigns_with_activities()`, `campaign.pending`,
  `total_pending_activities_count()`) siguen contando actividades huérfanas. No se pueden trabajar,
  así que una campaña puede aparecer en la lista con un número que la cola no muestra. Convendría
  alinearlos con el mismo filtro `Exists`.
- Los links de la consola llevan las claves primarias de `ContactCampaignStatus` y `Activity` en el
  querystring. Cualquiera de las dos puede quedar vieja entre que se renderiza y se hace clic; una
  revalidación periódica, o direccionar por contacto y campaña en lugar de por id, eliminaría toda
  una clase de estos errores.
- `BulkDeleteCampaignStatusView` registra el borrado de los estados de campaña pero no el de las
  actividades. Si la trazabilidad importa también para las actividades, merecen su propio `LogEntry`.

---

- **Fecha:** 2026-09-08
- **Autor:** Tanya Tree + Claude Opus 5
- **Rama:** t1176
- **Tipo:** Bug Fix
- **Módulos afectados:** Support (Campaign Management, Consola de vendedores, Suscripciones), Core
  (Activity, ContactCampaignStatus)
