# Los mails HTML pasan por el backend de mail de Django

- **Fecha:** 2026-11-20
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#162
- **Tipo:** Corrección
- **Componente:** util (mailer)
- **Impacto:** Avisos

## 🎯 Resumen

`util.mailer.send_html_email` armaba el mensaje con `email.mime` y lo mandaba con `smtplib`, directo a `EMAIL_HOST`. Así se salteaba `EMAIL_BACKEND` y todo lo que un deploy configura ahí. En la diaria, el paquete de customización pone un backend que les agrega Reply-To a los mails internos (it/utopia-crm-ladiaria#161), y los tres avisos que usan esta función salían sin él. Los tests tampoco podían leer estos mails en `mail.outbox`. Ahora la función manda por Django, con la misma firma.

## ✨ Cambios

### 1. `send_html_email` usa `EmailMessage`

**Archivo:** `util/mailer.py`

```python
message = EmailMessage(subject, render_to_string(template, context or {}), from_address, list(to_addresses))
message.content_subtype = "html"
return message.send()
```

- Misma firma y la misma plantilla renderizada; el cuerpo va como una sola parte `text/html` (antes, un multipart con una parte HTML).
- Pasa por `EMAIL_BACKEND`, con la configuración SMTP de Django (`EMAIL_HOST`, `EMAIL_PORT`, y TLS y autenticación sólo si están configurados). El código viejo intentaba siempre un login e ignoraba el error cuando el servidor no tenía autenticación.
- Sigue levantando una excepción ante errores de SMTP, como antes. Ahora devuelve la cantidad de mensajes mandados.
- El valor por defecto mutable `context={}` pasó a `context=None`.
- Django agrega los encabezados `Message-ID` y `Date`.

## 📁 Archivos Modificados

- **`util/mailer.py`** — `send_html_email` por el backend de mail de Django
- **`CHANGELOG.md`** — Entrada de este cambio

## 📁 Archivos Creados

- **`tests/test_mailer.py`** — La plantilla renderizada sale como HTML, con su remitente, destinatarios y asunto; el contexto vacío por defecto; acepta una tupla de destinatarios; y el mail pasa por el `EMAIL_BACKEND` configurado

## 🧪 Pruebas Manuales

1. **Caso normal:** en un shell, `send_html_email(settings.DEFAULT_FROM_EMAIL, ["vos@example.com"], "Prueba", "<una plantilla que exista>.html", {})`. **Verificar:** devuelve `1`, el mail llega renderizado como HTML y trae los encabezados que agrega `EMAIL_BACKEND` (en la diaria, el Reply-To a informática).
2. **Caso borde:** con un `EMAIL_HOST` al que no se llega. **Verificar:** levanta una excepción, como antes, así que los que capturan el error siguen funcionando.

## 📝 Notas de Despliegue

- Sin migraciones. Sin settings: usa la configuración de mail que ya existe.

---

- **Fecha:** 2026-11-20
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl162-send-html-email-django
- **Tipo:** Corrección
- **Módulos afectados:** util
