# La tarjeta de la dirección muestra su país, aunque no tenga estado

- **Fecha:** 2026-11-16
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#144
- **Tipo:** Corrección
- **Componente:** Support (ficha del contacto), Core (Address)
- **Impacto:** Experiencia de Usuario

## 🎯 Resumen

Un suscriptor de Estados Unidos se dio de alta por PayPal. Su dirección se guardó con su país (Estados Unidos) y sin estado, porque los únicos estados cargados son los departamentos de Uruguay. El estado quedó en las notas de la dirección y en la factura. Aun así, la pestaña Información del contacto mostraba «-» y una advertencia roja en la línea País: leía el país a través del estado (`address.state.country`), no de la dirección. Ahora la línea País lee el país de la propia dirección, y la línea Estado advierte sólo donde realmente se puede elegir un estado.

## ✨ Cambios

### 1. La línea País lee `address.country`

**Archivo:** `support/templates/contact_detail/tabs/_information.html`

```django
{% if not address.country %}<i class="fas fa-exclamation-triangle text-danger"></i>{% endif %}
{{ address.country_name|default_if_none:"-" }}
```

La advertencia depende ahora del país, no del estado. Desde it/utopia-crm-ladiaria#122, una dirección que se guarda con estado y sin país toma el país de su estado, así que las direcciones uruguayas se ven igual que antes.

### 2. `Address.needs_state`

**Archivo:** `core/models.py`

```python
@cached_property
def needs_state(self):
    if self.state_id:
        return False
    return self.country_id is None or State.objects.filter(country_id=self.country_id).exists()
```

Que falte el estado es un dato faltante sólo cuando la dirección no tiene país, o cuando su país tiene estados cargados para elegir. La línea Estado de la tarjeta muestra su advertencia con esta propiedad en lugar de `not address.state`. El código no nombra a Uruguay: si algún día se cargan los estados de otro país, sus direcciones también van a advertir cuando falte el estado.

## 📁 Archivos Modificados

- **`core/models.py`** — `Address.needs_state`
- **`support/templates/contact_detail/tabs/_information.html`** — La línea País desde `address.country`; la advertencia de la línea Estado desde `needs_state`
- **`CHANGELOG.md`** — Entrada de este cambio

## 📁 Archivos Creados

- **`tests/test_address_detail_country.py`** — Las líneas País y Estado de la tarjeta, y `needs_state`. Los dos casos del error fallan con el template anterior

## 🧪 Pruebas Manuales

1. **Caso normal, una dirección del exterior sin estado:**
   - Abrir un contacto con una dirección cuyo país no es Uruguay y que no tiene estado (por ejemplo, un alta por PayPal).
   - **Verificar:** País muestra el país sin advertencia; Estado muestra «-» sin advertencia.

2. **Caso borde, una dirección uruguaya sin departamento:**
   - Abrir un contacto con una dirección en Uruguay y sin departamento.
   - **Verificar:** Estado muestra «-» con la advertencia roja; País muestra Uruguay.

3. **Caso borde, una dirección sin país ni estado:**
   - Abrir un contacto con una dirección que no tiene ninguno de los dos.
   - **Verificar:** Las dos líneas muestran «-» con la advertencia roja.

## 📝 Notas de Despliegue

- Sin migraciones ni settings.

## 🎓 Decisiones de Diseño

- **Los estados del exterior no se cargan como filas de `State`.** Varias búsquedas listan todos los estados o buscan uno por nombre sin filtrar por país: los selectores de `support/forms.py`, los filtros, el georreferenciador (`support/location.py`). Florida es a la vez un departamento de Uruguay y un estado de Estados Unidos, así que una búsqueda por nombre podría poner una dirección uruguaya en el equivocado, sin ningún error. El estado del exterior queda en las notas de la dirección y en el `billing_state` de la factura.
- **«Su país tiene estados» en lugar de «es el país por defecto»:** la regla vale para cualquier instalación del base open source, y sigue a los datos.

---

- **Fecha:** 2026-11-16
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl144-pais-direccion-sin-estado
- **Tipo:** Corrección
- **Módulos afectados:** core, support
