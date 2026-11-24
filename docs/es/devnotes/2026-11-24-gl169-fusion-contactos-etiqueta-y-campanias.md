# Fusión de contactos: la etiqueta de descartado queda en el origen y las campañas trabajadas se pasan

- **Fecha:** 2026-11-24
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#169
- **Tipo:** Corrección
- **Componente:** core (fusión de contactos)
- **Impacto:** Call center, campañas

## 🎯 Resumen

`Contact.merge_other_contact_into_this` no borra el contacto descartado: pasa sus datos al contacto que queda y al origen le pone la etiqueta `eliminar`. Ahí fallaban dos cosas. Copiaba todas las etiquetas del origen, así que un origen que ya había sido descartado en otra fusión le pasaba la marca `eliminar` al contacto que queda. Y sus filas de `ContactCampaignStatus` o se borraban todas, historial incluido, cuando el contacto que queda estaba en alguna campaña, o quedaban todas en el origen vacío, todavía asignadas a un vendedor, cuando no estaba en ninguna. En la diaria, los contactos descartados se cargan a mano en una campaña de prioridad alta, y terminaron ahí 46 contactos con una suscripción activa, escondidos de todas las demás campañas en la consola de vendedor. Ahora la fusión deja la marca en el origen, pasa al contacto que queda las campañas que ya se trabajaron y borra las abiertas.

## ✨ Cambios

### 1. La etiqueta `eliminar` no se copia

**Archivo:** `core/models.py`

El nombre de la etiqueta pasa a ser la constante de módulo `MERGED_AWAY_CONTACT_TAG`, y el bucle que copia las etiquetas del origen la saltea:

```python
for tag in source.tags.exclude(name=MERGED_AWAY_CONTACT_TAG):
    self.tags.add(tag.name)
```

El origen sigue recibiendo la etiqueta al final de la fusión.

### 2. Qué pasa con las campañas del origen

**Archivos:** `core/models.py`, `core/choices.py`

```python
source_statuses = source.contactcampaignstatus_set
source_statuses.filter(status__in=OPEN_CAMPAIGN_STATUSES).delete()
source_statuses.filter(campaign__in=self.contactcampaignstatus_set.values("campaign")).delete()
source_statuses.update(contact=self)
```

- **Los estados abiertos se borran:** «No se contactó aún», «Llamado, no se pudo contactar», «Pasar a la mañana» y «Pasar a la tarde», la nueva lista `OPEN_CAMPAIGN_STATUSES` de `core/choices.py`. La fusión ya borraba las actividades pendientes del origen que tienen campaña; es la misma regla para su estado en la campaña.
- **Donde los dos contactos están en la misma campaña**, gana el estado del contacto que queda: `ContactCampaignStatus` es único por `(contact, campaign)`.
- **El resto pasa al contacto que queda** (Contactado, Finalizado con contacto, Finalizado sin contacto), con su vendedor, resolución y fechas, así se conserva el historial de campañas de la persona.

## 📁 Archivos Modificados

- **`core/models.py`** — `MERGED_AWAY_CONTACT_TAG`; `merge_other_contact_into_this` saltea esa etiqueta al copiar y trata las campañas del origen como se describe arriba
- **`core/choices.py`** — `OPEN_CAMPAIGN_STATUSES`
- **`CHANGELOG.md`** — Entrada de este cambio

## 📁 Archivos Creados

- **`tests/test_contact_merge.py`** — La etiqueta `eliminar` no se copia y el origen la recibe; las campañas trabajadas se pasan, también cuando el contacto que queda está en otra campaña; las abiertas se borran, también cuando el contacto que queda no está en ninguna; donde los dos están en una campaña, gana el estado del contacto que queda. Con el código anterior fallan tres de los cinco tests

## 🧪 Pruebas Manuales

1. **Caso normal:** tomar dos contactos. Darle al origen una etiqueta, una campaña terminada con contacto y una campaña en «No se contactó aún» con vendedor. Fusionarlo en el otro desde la pantalla de fusión. **Verificar:** el contacto que queda tiene la etiqueta y la campaña terminada, no la abierta; el origen no tiene campañas y tiene la etiqueta `eliminar`.
2. **Caso borde, un origen ya descartado:** ponerle a mano la etiqueta `eliminar` al origen antes de fusionar. **Verificar:** el contacto que queda no recibe `eliminar`.
3. **Caso borde, misma campaña:** poner a los dos contactos en una campaña, el que queda en «No se contactó aún» y el origen terminado. **Verificar:** después de fusionar, el contacto que queda sigue en «No se contactó aún» en esa campaña.

## 📝 Notas de Despliegue

- Sin migraciones ni settings.
- Las fusiones ya hechas no cambian. Los contactos que ya recibieron la etiqueta `eliminar`, o que están en una campaña de contactos descartados, se tratan en it/utopia-crm-ladiaria#169.

## 🎓 Decisiones de Diseño

- **Las campañas abiertas se borran, no se pasan.** Pasarlas metería al contacto que queda en todas las campañas en las que el origen estaba esperando. Si una de ellas es la campaña de prioridad alta de los contactos descartados, el contacto que queda quedaría reservado ahí y escondido de todas las demás campañas (`Campaign.get_not_contacted`), que es como se escondieron los 46 contactos.
- **En una campaña compartida gana el estado del contacto que queda**, como antes: es el contacto que el call center sigue trabajando.

---

- **Fecha:** 2026-11-24
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl169-fusion-etiqueta-y-campanias
- **Tipo de cambio:** Corrección
- **Módulos afectados:** core
