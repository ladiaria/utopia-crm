import pandas as pd

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.translation import gettext as _
from core.models import Address, Contact, State
from support.forms import SugerenciaGeorefForm
from util.location_utils import (
    buscar_alternativas_normalizadas,
    seleccionar_sugerencia,
    separar_direccion,
    autocompletar_direccion,
    georef_habilitado,
)

# Los botones de "Nueva dirección" que guardan la dirección
ACCIONES_GUARDAR = ("save", "save_needs_georef", "no_encuentro_direccion")


@staff_member_required
def normalizar_direccion(request, contact_id, address_id):
    if not georef_habilitado():
        messages.error(request, "Servicio de georeferenciación no configurado.")
        return HttpResponseRedirect(reverse("contact_detail", args=[contact_id]))
    address_obj = get_object_or_404(Address, pk=address_id)
    contact_obj = get_object_or_404(Contact, pk=contact_id)
    old_address_1 = address_obj.address_1
    form_rechazado = None
    # Venimos de "Nueva dirección" en una venta: la dirección ya existe, así que al terminar acá se avisa a esa
    # pantalla en vez de mandar a la ficha del contacto.
    stayhere = bool(request.GET.get("stayhere", None))
    if request.POST:
        form_nuevo = SugerenciaGeorefForm(request.POST, instance=address_obj)
        if form_nuevo.is_valid():
            new_address = form_nuevo.save(commit=False)
            new_address.needs_georef = False
            new_address.contact = contact_obj
            new_address.save()
            if old_address_1 != new_address.address_1:
                new_address.add_note(
                    f"Sugerencia aplicada el {timezone.now().strftime('%Y/%m/%d %H:%M:%S')}, "
                    f"dirección anterior: {old_address_1}"
                )
            if new_address.verified:
                messages.success(request, f"Dirección {new_address} normalizada con éxito.")
            else:
                messages.error(request, "Dirección no cuenta con los valores correctos de georreferenciación.")
            if request.GET.get("goback", None) == "mass_georef":
                return HttpResponseRedirect(reverse("mass_georef_address"))
            elif stayhere:
                return HttpResponseRedirect(reverse("direccion_guardada", args=[contact_id, address_id]))
            else:
                return HttpResponseRedirect(reverse("normalizar_direccion", args=[contact_id, address_id]))
        else:
            messages.error(request, "Dirección no cuenta con los valores correctos de georreferenciación.")
            form_rechazado = form_nuevo
    sugerencias = buscar_alternativas_normalizadas(address_obj.address_1, address_obj.city, address_obj.state_name)
    sugindex = int(request.GET.get('sugerencia', 0))
    try:
        sugerencia = sugerencias[sugindex]
    except IndexError:
        messages.error(request, "No hay sugerencias encontradas para esta dirección")
        if request.GET.get("goback", None) == "mass_georef":
            return HttpResponseRedirect(reverse("mass_georef_address"))
        elif stayhere:
            # Quedó guardada sin georreferenciar: la venta igual tiene que verla, o se carga de nuevo
            return HttpResponseRedirect(reverse("direccion_guardada", args=[contact_id, address_id]))
        else:
            return HttpResponseRedirect(reverse("contact_detail", args=[contact_id]))
    direccion, id_calle = sugerencia['direccion'], sugerencia["idCalle"]
    id_localidad, id_portal = sugerencia["idLocalidad"], sugerencia["portalNumber"]
    j = seleccionar_sugerencia(direccion, id_calle, id_localidad, id_portal)
    state_obj = address_obj.state
    if j.get("departamento"):
        state_name_slug = slugify(j["departamento"].title())
        state_obj = next(
            (state for state in State.objects.all() if slugify(state.name) == state_name_slug),
            None,
        )
        if state_obj is None:
            messages.error(request, f"No se encontró un departamento coincidente para '{j['departamento']}'.")
    lat = j["latitud"] if not pd.isna(j["latitud"]) else None
    lng = j["longitud"] if not pd.isna(j["longitud"]) else None
    if not lat or not lng or state_obj is None:
        messages.warning(request, "Esta sugerencia no tiene valores de georreferenciación.")
        lat, lng = None, None
    form_nuevo = SugerenciaGeorefForm(
        initial={
            "address_1": j["direccion"] or address_obj.address_1,
            "address_2": address_obj.address_2,
            "state": state_obj,
            "city": j["localidad"] or address_obj.city,
            "latitude": lat,
            "longitude": lng,
            "state_georef_id": j["departamento_id"] or None,  # For debug reasons
            "city_georef_id": j["localidad_id"] or None,  # For debug reasons
            "address_type": "physical",
        }
    )
    if form_rechazado is not None:
        # Lo que se mandó, con sus errores, en vez de la sugerencia otra vez como si nada.
        form_nuevo = form_rechazado
    form_actual = SugerenciaGeorefForm(instance=address_obj)

    breadcrumbs = [
        {"label": _("Contact list"), "url": reverse("contact_list")},
        {"label": contact_obj.get_full_name(), "url": reverse("contact_detail", args=[contact_id])},
        {"label": _("Edit address"), "url": ""},
    ]

    return render(
        request,
        "location/normalizar_direccion.html",
        {
            "contact": contact_obj,
            "sugerencias": sugerencias,
            "form_actual": form_actual,
            "address": address_obj,
            "form_nuevo": form_nuevo,
            "sugindex": sugindex,
            "lat": lat,
            "lng": lng,
            "stayhere": stayhere,
            "breadcrumbs": breadcrumbs,
        },
    )


@staff_member_required
def agregar_direccion(request, contact_id):
    georef_activated = georef_habilitado()
    contact_obj = get_object_or_404(Contact, pk=contact_id)
    form = SugerenciaGeorefForm(initial={"address_type": "physical"})
    stayhere = "?stayhere=True" if request.GET.get("stayhere", None) else ""
    lat, lng, q_sugerencia = None, None, None
    # La dirección del contacto igual a la que se quiere guardar, y el botón que se apretó para guardarla
    repetida, accion = None, None
    if request.POST:
        # "Guardar igual" trae el botón que se había apretado, una vez avisado que el contacto ya tiene la dirección
        guardar_igual = request.POST.get("guardar_igual")
        if guardar_igual not in ACCIONES_GUARDAR:
            guardar_igual = None
        accion = guardar_igual or next((nombre for nombre in ACCIONES_GUARDAR if request.POST.get(nombre)), None)
    if accion:
        form = SugerenciaGeorefForm(request.POST)
        if form.is_valid():
            if not guardar_igual:
                datos = form.cleaned_data
                repetida = Address.find_same(
                    contact_obj, datos.get("address_1"), datos.get("address_2"), datos.get("city"), datos.get("state")
                )
            if repetida is None:
                address = form.save(commit=False)
                address.contact = contact_obj
                if accion == "no_encuentro_direccion":
                    address.needs_georef = True
                    address.save()
                    messages.info(request, "Dirección guardada con éxito, buscando otras alternativas...")
                    return HttpResponseRedirect(
                        reverse("normalizar_direccion", args=[contact_id, address.id]) + stayhere
                    )
                if accion == "save":
                    address.save()
                    messages.success(request, "Dirección georreferenciada guardada con éxito")
                else:
                    address.reset_georef()  # Ya cuenta con save
                    messages.warning(request, "Dirección guardada con éxito sin georeferenciación")
                if stayhere:
                    return HttpResponseRedirect(reverse("direccion_guardada", args=[contact_id, address.id]))
                else:
                    return HttpResponseRedirect(reverse("contact_detail", args=[contact_id]))
            # Vuelve el formulario tal como se mandó, con el mapa si traía coordenadas, y el aviso arriba
            lat, lng = form.cleaned_data.get("latitude"), form.cleaned_data.get("longitude")
            q_sugerencia = form.cleaned_data.get("address_1")
    elif request.POST:
        if request.POST.get("sugerencias"):
            direccion, id_calle, id_localidad, id_portal = request.POST.get('sugerencias').split("|")
            j = seleccionar_sugerencia(direccion, id_calle, id_localidad, id_portal)
            if not j or "departamento" not in j or not j["departamento"]:
                messages.error(request, "El departamento de la dirección sugerida no es válido o está vacío.")
                return HttpResponseRedirect(reverse("agregar_direccion", args=[contact_id]) + stayhere)
            state_name_slug = slugify(j["departamento"].title())
            try:
                state_obj = next(
                    state for state in State.objects.all()
                    if slugify(state.name) == state_name_slug
                )
            except StopIteration:
                messages.error(request, f"No se encontró un departamento coincidente para '{j['departamento']}'.")
                return HttpResponseRedirect(reverse("agregar_direccion", args=[contact_id]) + stayhere)
            form = SugerenciaGeorefForm(
                initial={
                    "address_1": j["direccion"],
                    "address_2": None,
                    "state": state_obj,
                    "city": j["localidad"],
                    "latitude": j["latitud"],
                    "longitude": j["longitud"],
                    "state_georef_id": j["departamento_id"],  # For debug reasons
                    "city_georef_id": j["localidad_id"],  # For debug reasons
                    "address_type": "physical",
                }
            )
            if not pd.isna(j["latitud"]):
                lat, lng = j["latitud"], j["longitud"]
            q_sugerencia = j["direccion"]
    if not georef_activated:
        messages.warning(request, "El servicio de georeferenciación está desactivado. Usar direcciones manuales.")

    breadcrumbs = [
        {"label": _("Home"), "url": reverse("home")},
        {"label": _("Contact list"), "url": reverse("contact_list")},
        {"label": contact_obj.get_full_name(), "url": reverse("contact_detail", args=[contact_id])},
        {"label": _("Add address"), "url": ""},
    ]
    if settings.DEBUG:
        print(f"DEBUG: agregar_direccion: georef_activated={georef_activated}")
    return render(
        request,
        "location/agregar_direccion.html",
        {
            "georef_activated": georef_activated,
            "contact": contact_obj,
            "form": form,
            "lat": lat,
            "lng": lng,
            "q_sugerencia": q_sugerencia,
            "repetida": repetida,
            "accion": accion,
            "stayhere": stayhere,
            "breadcrumbs": breadcrumbs,
        },
    )


@staff_member_required
def direccion_guardada(request, contact_id, address_id):
    """
    Where "Nueva dirección" ends when it was opened from a sale (``?stayhere=True``). The page tells the sale's
    window that the contact has a new address, so it reloads its address selectors on its own, and closes itself.

    Before, the window went back to an empty "Nueva dirección" form and the sale only saw the address after pressing
    "Recargar direcciones". Whoever did not press it took the address for lost and loaded it again.

    With ``?ya_existia=1`` nothing was saved: the agent chose the address the contact already had over loading it
    again, and the sale is told about that one.
    """
    contact_obj = get_object_or_404(Contact, pk=contact_id)
    address_obj = get_object_or_404(Address, pk=address_id, contact=contact_obj)
    breadcrumbs = [
        {"label": _("Contact list"), "url": reverse("contact_list")},
        {"label": contact_obj.get_full_name(), "url": reverse("contact_detail", args=[contact_id])},
        {"label": _("Add address"), "url": ""},
    ]
    return render(
        request,
        "location/direccion_guardada.html",
        {
            "contact": contact_obj,
            "address": address_obj,
            "ya_existia": bool(request.GET.get("ya_existia")),
            "breadcrumbs": breadcrumbs,
        },
    )


@staff_member_required
def editar_direccion(request, contact_id, address_id):
    georef_activated = georef_habilitado()
    address_obj = get_object_or_404(Address, pk=address_id)
    contact_obj = get_object_or_404(Contact, pk=contact_id)
    form = SugerenciaGeorefForm(instance=address_obj)
    lat, lng = address_obj.latitude or None, address_obj.longitude or None
    q_sugerencia = None
    if request.POST:
        if request.POST.get("save", False):
            form = SugerenciaGeorefForm(request.POST, instance=address_obj)
            if form.is_valid():
                address = form.save(commit=False)
                address.contact = contact_obj
                address.save()
                messages.success(request, "Dirección georreferenciada guardada con éxito")
                return HttpResponseRedirect(reverse("contact_detail", args=[contact_id]))
        elif request.POST.get("save_needs_georef", False):
            form = SugerenciaGeorefForm(request.POST, instance=address_obj)
            if form.is_valid():
                address = form.save(commit=False)
                address.contact = contact_obj
                address.reset_georef()  # Ya cuenta con save
                messages.warning(request, "Dirección guardada con éxito sin georeferenciación")
                return HttpResponseRedirect(reverse("contact_detail", args=[contact_id]))
        elif request.POST.get("no_encuentro_direccion", False):
            form = SugerenciaGeorefForm(request.POST, instance=address_obj)
            if form.is_valid():
                address = form.save(commit=False)
                address.contact = contact_obj
                address.reset_georef()  # Ya cuenta con save
                messages.info(request, "Dirección guardada con éxito, buscando otras alternativas...")
                return HttpResponseRedirect(reverse("normalizar_direccion", args=[contact_id, address.id]))
        elif request.POST.get("sugerencias"):
            direccion, id_calle, id_localidad, id_portal = request.POST.get('sugerencias').split("|")
            j = seleccionar_sugerencia(direccion, id_calle, id_localidad, id_portal)
            if not j or "departamento" not in j or not j["departamento"]:
                messages.error(request, "El departamento de la dirección sugerida no es válido o está vacío.")
                return HttpResponseRedirect(reverse("editar_direccion", args=[contact_id, address_id]))
            state_name_slug = slugify(j["departamento"].title())
            try:
                state_obj = next(
                    state for state in State.objects.all()
                    if slugify(state.name) == state_name_slug
                )
            except StopIteration:
                messages.error(request, f"No se encontró un departamento coincidente para '{j['departamento']}'.")
                return HttpResponseRedirect(reverse("editar_direccion", args=[contact_id, address_id]))
            form = SugerenciaGeorefForm(
                instance=address_obj,
                initial={
                    "address_1": j["direccion"],
                    "state": state_obj,
                    "city": j["localidad"],
                    "latitude": j["latitud"],
                    "longitude": j["longitud"],
                    "state_georef_id": j["departamento_id"],  # For debug reasons
                    "city_georef_id": j["localidad_id"],  # For debug reasons
                    "address_type": "physical",
                },
            )
            if not pd.isna(j["latitud"]):
                lat, lng = j["latitud"], j["longitud"]
            else:
                # La nueva búsqueda no encontró coordenadas: no seguir mostrando ni enviando
                # las coordenadas viejas de la dirección como si siguieran siendo válidas.
                lat, lng = None, None
            q_sugerencia = j["direccion"]

    breadcrumbs = [
        {"label": _("Contact list"), "url": reverse("contact_list")},
        {"label": contact_obj.get_full_name(), "url": reverse("contact_detail", args=[contact_id])},
        {"label": _("Edit address"), "url": ""},
    ]

    return render(
        request,
        "location/editar_direccion.html",
        {
            "georef_activated": georef_activated,
            "contact": contact_obj,
            "address": address_obj,
            "form": form,
            "lat": lat,
            "lng": lng,
            "q_sugerencia": q_sugerencia,
            "breadcrumbs": breadcrumbs,
        },
    )


@csrf_exempt
def sugerir_direccion_autocompletar(request):
    # TODO: Check why this is not being used
    # form_nuevo = SugerenciaGeorefForm()
    q, obs = separar_direccion(request.GET.get("q_direccion"))
    sugerencias = []
    if q:
        sugerencias = autocompletar_direccion(q, obs, informar_caida=True)
    return render(
        request,
        "location/sugerencias_htmx.html",
        {"sugerencias": sugerencias or [], "servicio_caido": sugerencias is None},
    )
