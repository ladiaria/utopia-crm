# Cola de takeovers: soltar el login de Google en vez de derivar el caso a informática

- **Fecha:** 2026-11-24
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#173
- **Tipo:** Funcionalidad
- **Componente:** core, support (cola de takeovers de email)
- **Impacto:** Call center, supervisores

## 🎯 Resumen

Cuando un operador le pone a un contacto una dirección que en la web es sólo el login de Google (`UserSocialAuth.uid`) de otra cuenta, registrada con otra dirección, el CMS contestaba `social_auth_conflict`. Ese motivo está en `BLOCKING_PREVIEW_REASONS`, así que el guardado del contacto se cortaba con «avisá a tu supervisor para que lo derive a soporte web» e informática sacaba el login de Google a mano. Casi siempre es la misma persona: el email de la cuenta cambió y el login de Google se quedó con la dirección vieja (contacto 2631, 2026-11-24). Ahora el CMS contesta ese caso con un modo de takeover nuevo, `release_social_auth`: al aprobar se saca ese login de Google y la dirección queda libre, sin borrar ninguna cuenta. Del lado del CRM el pedido va a la cola como cualquier otro, y la cola muestra qué cuentas pierden su login de Google.

## ✨ Cambios

### 1. La cola muestra el modo nuevo

**Archivo:** `support/templates/email_takeovers/queue.html`

- Un `badge-warning` «Saca un login de Google» para los pedidos cuyo preview tiene el modo `release_social_auth`.
- Una fila «Pierde su login de Google» que lista cada cuenta de `released_social_auth`: su email, su subscriber, un link a su contacto si tiene, y una etiqueta «Suscripción activa». Abajo, una explicación corta para quien revisa: casi siempre es la misma persona y no se borra ninguna cuenta.

### 2. `EmailTakeoverRequest.released_social_auth`

**Archivo:** `core/models.py`

Una propiedad que lee `released_social_auth` del preview guardado, igual que `released_contact_id`. El docstring de `takeover_mode` lista el modo nuevo. `deletes_an_account` sigue en `False` para él.

### 3. `social_auth_conflict` sigue trabando

**Archivo:** `core/email_takeover_queue.py`

Sigue en `BLOCKING_PREVIEW_REASONS`, con un comentario: sólo lo manda un CMS sin el cambio. Así el CRM queda seguro si se deploya antes que el CMS.

## 📁 Archivos modificados

- **`support/templates/email_takeovers/queue.html`** — Etiqueta y fila «Pierde su login de Google»
- **`core/models.py`** — `EmailTakeoverRequest.released_social_auth`; docstring de `takeover_mode`
- **`core/email_takeover_queue.py`** — Comentario sobre `social_auth_conflict` en `BLOCKING_PREVIEW_REASONS`
- **`locale/es/LC_MESSAGES/django.po`** — Las cuatro cadenas nuevas, agregadas a mano: `makemessages` trae miles de líneas de otros cambios pendientes
- **`tests/test_email_takeover_views.py`** — La cola muestra la cuenta que pierde el login de Google y linkea su contacto
- **`CHANGELOG.md`** — Entrada de este cambio

## 🧪 Pruebas manuales

1. **Caso normal:** en el CMS, darle a la cuenta A (email `a@…`) un login de Google con uid `b@…`, y verificar que ninguna cuenta tenga `b@…` como email ni como username. En el CRM, cambiarle el email a un contacto a `b@…` desde la edición del contacto. **Verificar:** el pedido llega a la cola con la etiqueta «Saca un login de Google» y lista la cuenta A. Aprobarlo. **Verificar:** el contacto tiene `b@…`, la cuenta A sigue existiendo sin ese login de Google, y la cuenta web del contacto tiene `b@…`.
2. **Caso borde, staff:** lo mismo, con la cuenta A marcada como staff. **Verificar:** el guardado del contacto muestra el mensaje de staff y no llega nada a la cola.
3. **Caso borde, dueña con suscripción:** la cuenta A tiene una suscripción activa. **Verificar:** la cola muestra la etiqueta «Suscripción activa» al lado.

## 📝 Notas de despliegue

- Sin migraciones ni settings.
- Mergear primero el cambio del CMS (`utopia_cms_ladiaria`, rama `gl173-soltar-google-trancado`). Sin él, el CMS sigue contestando `social_auth_conflict` y el CRM sigue trabando, como antes.
- MercadoPago y Witty ejecutan el takeover solos (sin cola), así que con el cambio del CMS también sueltan el login de Google automáticamente.

## 🎓 Decisiones de diseño

- **Soltar el login, no absorber la cuenta.** La cuenta del uid puede ser de otra persona, y absorberla borra una cuenta, lo que no tiene vuelta atrás. Sacar el login sólo le quita el botón de Google: la cuenta, su suscripción y sus datos quedan. Si era la misma persona, el próximo ingreso con Google encuentra la cuenta del contacto por email (`associate_by_email`) y lo ata ahí.
- **Por la cola, no automático.** Un error de tipeo podría liberar para este contacto la dirección de Google de otra persona. Quien revisa ve qué cuenta pierde el login, y si suscribe, antes de aprobar.

---

- **Fecha:** 2026-11-24
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl173-soltar-google-trancado
- **Tipo:** Funcionalidad
- **Módulos afectados:** core, support
