# Ocultar el header Authorization en los mails de error

- **Fecha:** 2026-11-26
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#191
- **Tipo:** Seguridad
- **Componente:** Settings
- **Impacto:** Reporte de errores

## 🎯 Resumen

Django manda por mail a `ADMINS` cada excepción no atrapada, con el `META` del request incluido. Su filtro por
defecto, `SafeExceptionReporterFilter`, tapa las claves que coinciden con `API|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE`,
pero no `HTTP_AUTHORIZATION`. Ese header lleva la API key con la que otros sistemas llaman al CRM
(`Authorization: Api-Key …`, de `djangorestframework-api-key`) y, si lo hay, el usuario y la contraseña de HTTP basic
auth, así que cada 500 en una vista de API los mandaba en texto plano a varias casillas. Se detectó en un mail de 500
de utopia-cms, que tiene el mismo problema y recibe el mismo arreglo.

Este cambio apunta `DEFAULT_EXCEPTION_REPORTER_FILTER` a una subclase que además tapa `AUTHORIZATION`.

## ✨ Cambios

### 1. El filtro

**Archivo:** `util/error_reporting.py`

```python
class SafeExceptionReporterFilter(DjangoSafeExceptionReporterFilter):
    hidden_settings = re.compile("API|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE|AUTHORIZATION", flags=re.I)
```

El patrón de Django más `AUTHORIZATION`. Django aplica el mismo patrón a los settings y a `request.META`, así que el
header se reemplaza por `********************` y el resto del request se reporta como antes.

### 2. El setting

**Archivo:** `settings.py`

`DEFAULT_EXCEPTION_REPORTER_FILTER = "util.error_reporting.SafeExceptionReporterFilter"`, junto a `ADMINS`. Va antes
de `from local_settings import *`, así que aplica en cualquier instalación y un `local_settings.py` todavía lo puede
cambiar.

## 📁 Archivos modificados

- **`settings.py`**: `DEFAULT_EXCEPTION_REPORTER_FILTER`
- **`CHANGELOG.md`**: entrada de este cambio

## 📁 Archivos creados

- **`util/error_reporting.py`**: el filtro
- **`tests/test_error_reporting.py`**: el header queda tapado en `META` y en el texto del mail, y el resto del request
  se sigue reportando. Sin el setting, los dos tests fallan

## 🧪 Pruebas manuales

1. **Caso feliz:**
   - Correr `python -W ignore manage.py test --settings=test_settings --keepdb tests.test_error_reporting`
   - **Verificar:** pasan los dos tests
2. **Caso borde:**
   - Comentar `DEFAULT_EXCEPTION_REPORTER_FILTER` en `settings.py` y volver a correr los tests
   - **Verificar:** fallan los dos, porque el filtro propio de Django deja `HTTP_AUTHORIZATION` en texto plano
3. **En un entorno que manda mails de error:**
   - Llamar a una vista de API con una API key y hacerla fallar
   - **Verificar:** el mail muestra `HTTP_AUTHORIZATION` como `********************`

## 📝 Notas de despliegue

- Sin migraciones
- Sin cambios en `local_settings.py`
- Reiniciar el servidor de la aplicación, como con cualquier cambio de settings. El filtro aplica desde ese momento:
  los mails ya enviados conservan la key

## 🎓 Decisiones de diseño

- **En el `settings.py` del base y no en el `local_settings.py` de cada instalación:** la filtración pasa en
  cualquier instalación que tenga API keys y `ADMINS`, así que el arreglo es del base.
- **El setting y no `@sensitive_variables` o `@sensitive_post_parameters`:** esos protegen variables locales y
  parámetros POST de una vista. El header está en `META` y llega a todas las vistas.

---

- **Fecha:** 2026-11-26
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl191-ocultar-authorization-en-errores
- **Tipo:** Seguridad
- **Módulos afectados:** settings, util
