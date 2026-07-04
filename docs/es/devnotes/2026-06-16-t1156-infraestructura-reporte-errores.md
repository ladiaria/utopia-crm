# Infraestructura de Reporte de Errores: Logging y Soporte de Sentry

- **Fecha:** 2026-06-16
- **Autor:** Tanya Tree + Claude Opus 4.8
- **Ticket:** t1156
- **Tipo:** Mejora
- **Componente:** Settings, Logging, Reporte de Errores
- **Impacto:** Observabilidad, Operabilidad

## 🎯 Resumen

Cuando una suscripción por MercadoPago fallaba desde la web, la causa real de la excepción se perdía en producción (`DEBUG=False`), obligando al equipo a adivinar qué había salido mal. Este ticket construye la infraestructura en la app base para dejar de andar a ciegas: una configuración de `LOGGING` de Django que conserva el comportamiento por defecto (mail de errores no atrapados a los `ADMINS`, más salida a stderr capturada por uWSGI), la dependencia `sentry-sdk`, y la documentación para inicializar Sentry solo en producción. La lógica específica de captura de MercadoPago vive en `utopia-crm-ladiaria`; este cambio en la app base provee la plomería de la que dependen esos reportes (`ADMINS`, el SDK de Sentry y el default de la setting de destinatarios).

## ✨ Cambios

### 1. Configuración de logging en settings base

**Archivo:** `settings.py`

Se agregó un diccionario `LOGGING` que mantiene el comportamiento por defecto de Django y agrega salida explícita a consola:

- Un handler `mail_admins` (el `AdminEmailHandler` de Django) filtrado por `require_debug_false`, de modo que los errores no atrapados envíen mail a los `ADMINS` solo en producción.
- Un handler `console` (stderr) asociado al logger raíz y a `django`, para que uWSGI capture todo en su log.
- Sin handlers de archivo, por decisión de diseño.

A `ADMINS` y `MANAGERS` también se les dio un default vacío para poder poblarlos por ambiente en `local_settings.py`.

### 2. Dependencia del SDK de Sentry

**Archivo:** `requirements.txt`

Se agregó `sentry-sdk` a los requirements. La inicialización en sí **no** está en settings base: se hace en `local_settings.py` para que solo los ambientes que lo necesitan (producción) activen Sentry.

### 3. Documentación de las nuevas settings

**Archivo:** `local_settings_sample.py`

Se agregó un bloque de referencia comentado que documenta:

- `ADMINS` / `MANAGERS`.
- `SENTRY_ENABLED`, `SENTRY_DSN`, `SENTRY_ENVIRONMENT` y un ejemplo completo de `sentry_sdk.init(...)` condicionado a `SENTRY_ENVIRONMENT == "production"`, con un hook `before_send` que filtra claves sensibles de MercadoPago / autenticación.
- `MERCADOPAGO_ERRORS_RECIPIENTS` (ya usada por los errores de débito) y la nueva `MERCADOPAGO_SUBSCRIPTION_ERRORS_RECIPIENTS`.

El default de `MERCADOPAGO_SUBSCRIPTION_ERRORS_RECIPIENTS` (lista vacía) también se agregó a settings base junto a la configuración de MercadoPago.

## 📁 Archivos Modificados

- **`settings.py`** — Se agregó `LOGGING`, los defaults de `ADMINS`/`MANAGERS` y el default de `MERCADOPAGO_SUBSCRIPTION_ERRORS_RECIPIENTS`
- **`requirements.txt`** — Se agregó `sentry-sdk`
- **`local_settings_sample.py`** — Se documentó la inicialización de Sentry, `ADMINS` y los destinatarios de errores de MercadoPago

## 📚 Detalles Técnicos

Sentry se inicializa en `local_settings.py` en lugar de en settings base de forma intencional: la app base del CRM debe poder desplegarse sin una cuenta de Sentry, y solo producción debe reportar. La inicialización lee `SENTRY_ENABLED`, `SENTRY_DSN` y `SENTRY_ENVIRONMENT`, y solo llama a `sentry_sdk.init` cuando el ambiente es `"production"`. El hook `before_send` elimina claves sensibles (`token`, `security_code`, `mp_card_id`, `card_number`, etc.) de los datos del request antes de enviar los eventos.

## 🧪 Pruebas Manuales

1. **Error no atrapado envía mail a ADMINS en producción:**
   - Poner `DEBUG = False` y poblar `ADMINS` en `local_settings.py`.
   - Disparar un error 500 en cualquier vista.
   - **Verificar:** se envía un mail de error a los `ADMINS` configurados, y el traceback aparece en el log de uWSGI.

2. **Caso borde — sin ADMINS configurados:**
   - Dejar `ADMINS = []` (default base).
   - Disparar un error 500.
   - **Verificar:** no se intenta enviar mail ni el handler de logging levanta excepción; el error igual aparece en stderr / log de uWSGI.

3. **Caso borde — Sentry deshabilitado fuera de producción:**
   - Poner `SENTRY_ENVIRONMENT = "test"` (o dejar `SENTRY_ENABLED` sin definir).
   - Arrancar la app.
   - **Verificar:** `sentry_sdk.init` no se llama y la app arranca normalmente.

## 📝 Notas de Despliegue

- Instalar la nueva dependencia: `pip install -r requirements.txt` (agrega `sentry-sdk`).
- No se requieren migraciones de base de datos.
- Por ambiente, configurar en `local_settings.py`: `ADMINS`, y (solo producción) el bloque de Sentry más `MERCADOPAGO_SUBSCRIPTION_ERRORS_RECIPIENTS`.
- Se debe crear un proyecto/DSN de Sentry dedicado para el CRM; el DSN va en el `local_settings.py` de producción.

## 🚀 Mejoras Futuras

- Considerar una revisión de `LOGGING` para agregar loggers con nombre específicos para los flujos de facturación y MercadoPago.
- Opcionalmente, cablear el seguimiento de `release` en Sentry mediante una variable de entorno `GIT_COMMIT`, como hace el CMS.

---

- **Fecha:** 2026-06-16
- **Autor:** Tanya Tree + Claude Opus 4.8
- **Branch:** t1156
- **Tipo de cambio:** Mejora
- **Módulos afectados:** Settings, Logging, Reporte de Errores
