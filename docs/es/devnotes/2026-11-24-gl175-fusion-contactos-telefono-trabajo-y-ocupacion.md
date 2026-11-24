# Fusión de contactos: el teléfono del trabajo y la ocupación elegidos se guardan

- **Fecha:** 2026-11-24
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#175
- **Tipo:** Corrección
- **Componente:** core (fusión de contactos)
- **Impacto:** Quien fusiona contactos duplicados

## 🎯 Resumen

`Contact.merge_other_contact_into_this` recibe como argumentos los datos elegidos en la pantalla de fusión y los escribe en el contacto que queda. Dos se escribían mal. Al teléfono del trabajo se le asignaba el valor de `phone`, así que el contacto que queda recibía su teléfono común como teléfono del trabajo, y cuando no se elegía teléfono la fusión daba `AttributeError` a mitad de camino. El id de la ocupación se convertía con `int()`, pero la clave primaria de `Ocupation` es un código de tres caracteres como `"011"`: se perdía el cero inicial y el contacto apuntaba a una ocupación que no existe. Ahora los dos guardan el valor tal como se eligió. El método además asignaba un atributo mal escrito, `not_email`, en lugar de `no_email`; no hacía daño, porque `Contact.save()` recalcula `no_email`, pero también se corrige.

Estos arreglos aparecieron al hacer más segura la pantalla de fusión de la diaria (it/utopia-crm-ladiaria#175), que ahora ofrece el teléfono del trabajo, el apellido y la ocupación que su versión anterior no mandaba.

## ✨ Cambios

### 1. Teléfono del trabajo

**Archivo:** `core/models.py`

```python
if work_phone:
    self.work_phone = work_phone.strip()
```

### 2. Ocupación

**Archivo:** `core/models.py`

```python
if ocupation_id:
    # Ocupation's primary key is a code like "011": as an int it would lose the leading zero.
    self.ocupation_id = ocupation_id.strip()
```

### 3. `no_email`

**Archivo:** `core/models.py`

Cuando el email elegido está vacío, el contacto que queda recibe `no_email = True`, y `False` si no, en lugar de asignar un atributo que el modelo no tiene.

## 📁 Archivos Modificados

- **`core/models.py`** — `merge_other_contact_into_this` escribe `work_phone` y `ocupation_id` tal como se eligieron, y `no_email` con su nombre real
- **`tests/test_contact_merge.py`** — Nueva `TestContactMergeOverrides`: el teléfono del trabajo elegido se guarda, también sin teléfono, y un código de ocupación con cero inicial se guarda. Con el código anterior los tres tests fallan
- **`CHANGELOG.md`** — Entrada de este cambio

## 🧪 Pruebas Manuales

1. **Caso normal:** tomar dos contactos con teléfonos distintos, uno de ellos con teléfono del trabajo. Fusionarlos eligiendo ese teléfono del trabajo. **Verificar:** el contacto que queda tiene ese teléfono del trabajo, no su teléfono común.
2. **Caso borde, sin teléfono:** ninguno de los dos contactos tiene teléfono común y uno tiene teléfono del trabajo. Fusionar eligiéndolo. **Verificar:** la fusión termina sin errores y el contacto que queda tiene el teléfono del trabajo.
3. **Caso borde, ocupación con cero inicial:** ponerle a un contacto la ocupación «011» y fusionar eligiéndola. **Verificar:** el contacto que queda muestra esa ocupación.

## 📝 Notas de Despliegue

- Sin migraciones ni settings.
- Deployarlo antes que la pantalla de fusión de it/utopia-crm-ladiaria#175, o junto con ella: esa pantalla manda la ocupación, y sin este arreglo un código con cero inicial hace fallar la fusión.

---

- **Fecha:** 2026-11-24
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl175-merge-work-phone
- **Tipo de cambio:** Corrección
- **Módulos afectados:** core
