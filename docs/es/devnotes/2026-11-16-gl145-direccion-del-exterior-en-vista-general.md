# La vista general muestra la ciudad y el país de una dirección del exterior

- **Fecha:** 2026-11-16
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#145
- **Tipo:** Mejora
- **Componente:** Support (ficha del contacto), Core (Address)
- **Impacto:** Experiencia de Usuario

## 🎯 Resumen

La tarjeta Información de contacto de la vista general del contacto lista cada dirección sólo por su calle (`address_1`). Eso alcanza para una dirección del propio país de la instalación, pero una del exterior, como un alta por PayPal desde Estados Unidos, se leía «131 Lake Shore Dr», sin ninguna pista de dónde quedaba. Ahora una dirección cuyo país no tiene estados cargados se lee con su ciudad y su país: «131 Lake Shore Dr, Newnan, Estados Unidos». Sigue la regla de it/utopia-crm-ladiaria#144: el código no nombra ningún país.

## ✨ Cambios

### 1. `Address.is_abroad` y `Address.abroad_label`

**Archivo:** `core/models.py`

```python
@cached_property
def is_abroad(self):
    return self.country_id is not None and not State.objects.filter(country_id=self.country_id).exists()

@cached_property
def abroad_label(self):
    return ", ".join(filter(None, (self.address_1, self.get_city(), self.country_name)))
```

Una dirección es del exterior cuando tiene país y ese país no tiene estados cargados. Una dirección sin país no lo es: su estado, si lo tiene, dice dónde queda. `needs_state` (#144) ahora reutiliza `is_abroad`, con el mismo resultado que antes.

### 2. La línea de la vista general

**Archivo:** `support/templates/contact_detail/tabs/_overview.html`

```django
{% if address.is_abroad %}
  {{ address.abroad_label }}
{% else %}
  {{ address.address_1|default:"-" }}
{% endif %}
```

## 📁 Archivos Modificados

- **`core/models.py`** — `Address.is_abroad` y `Address.abroad_label`; `needs_state` reutiliza `is_abroad`
- **`support/templates/contact_detail/tabs/_overview.html`** — La línea de la dirección en la tarjeta Información de contacto
- **`tests/test_address_detail_country.py`** — La línea de la vista general para una dirección del exterior y para una de un país con estados, e `is_abroad`. El caso del exterior falla con el template anterior
- **`CHANGELOG.md`** — Entrada de este cambio

## 🧪 Pruebas Manuales

1. **Caso normal, una dirección del exterior:**
   - Abrir la vista general de un contacto con una dirección en un país sin estados cargados (por ejemplo, un alta por PayPal desde Estados Unidos).
   - **Verificar:** La tarjeta Información de contacto muestra calle, ciudad y país.

2. **Caso borde, una dirección de un país con estados:**
   - Abrir la vista general de un contacto con una dirección uruguaya.
   - **Verificar:** La tarjeta muestra sólo la calle, como antes.

3. **Caso borde, una dirección del exterior sin ciudad:**
   - Abrir la vista general de un contacto con una dirección del exterior y la ciudad vacía.
   - **Verificar:** La tarjeta muestra calle y país, sin un hueco vacío entre comas.

## 📝 Notas de Despliegue

- Sin migraciones ni settings.

## 🎓 Decisiones de Diseño

- **Calle, ciudad y país, no `str(address)`:** el texto completo también trae la segunda línea y el nombre de la dirección, que alargan una línea de lista; la ciudad y el país son lo que dice dónde queda la dirección.

---

- **Fecha:** 2026-11-16
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl145-direccion-exterior-vista-general
- **Tipo:** Mejora
- **Módulos afectados:** core, support
