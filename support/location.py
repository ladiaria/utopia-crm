from core.models import Address, Contact
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
import pandas as pd

from django.contrib.admin.views.decorators import staff_member_required

from core.models import State
from support.forms import SugerenciaGeorefForm
from util.location_utils import (
    buscar_alternativas_normalizadas,
    seleccionar_sugerencia,
    separar_direccion,
    autocompletar_direccion,
)


@staff_member_required
def normalizar_direccion(request, contact_id, address_id):
    if not getattr(settings, 'GEOREF_SERVICES', False):
        messages.error(request, "Servicio de georeferenciación no configurado.")
        return HttpResponseRedirect(reverse("contact_detail", args=[contact_id]))
    address_obj = get_object_or_404(Address, pk=address_id)
    print(address_obj.state_georef_id, address_obj.city_georef_id, address_obj.georef_point)
    contact_obj = get_object_or_404(Contact, pk=contact_id)
    old_address_1 = address_obj.address_1
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
            else:
                return HttpResponseRedirect(reverse("normalizar_direccion", args=[contact_id, address_id]))
        else:
            messages.error(request, "Dirección no cuenta con los valores correctos de georreferenciación.")
    sugerencias = buscar_alternativas_normalizadas(address_obj.address_1, address_obj.city, address_obj.state_name)
    sugindex = int(request.GET.get('sugerencia', 0))
    try:
        sugerencia = sugerencias[sugindex]
    except IndexError:
        messages.error(request, "No hay sugerencias encontradas para esta dirección")
        if request.GET.get("goback", None) == "mass_georef":
            return HttpResponseRedirect(reverse("mass_georef_address"))
        else:
            return HttpResponseRedirect(reverse("contact_detail", args=[contact_id]))
    direccion, id_calle = sugerencia['direccion'], sugerencia["idCalle"]
    id_localidad, id_portal = sugerencia["idLocalidad"], sugerencia["portalNumber"]
    j = seleccionar_sugerencia(direccion, id_calle, id_localidad, id_portal)
    state_name = j["departamento"].title()
    state_obj = State.objects.get(name=state_name)
    form_nuevo = SugerenciaGeorefForm(
        initial={
            "address_1": j["direccion"],
            "address_2": address_obj.address_2,
            "state": state_obj,
            "city": j["localidad"],
            "latitude": j["latitud"],
            "longitude": j["longitud"],
            "state_georef_id": j["departamento_id"],  # For debug reasons
            "city_georef_id": j["localidad_id"],  # For debug reasons
            "address_type": "physical",
        }
    )
    form_actual = SugerenciaGeorefForm(instance=address_obj)
    lat = j["latitud"] if not pd.isna(j["latitud"]) else None
    lng = j["longitud"] if not pd.isna(j["longitud"]) else None
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
        },
    )


@staff_member_required
def agregar_direccion(request, contact_id):
    georef_activated = getattr(settings, "GEOREF_SERVICES", False)
    contact_obj = get_object_or_404(Contact, pk=contact_id)
    form = SugerenciaGeorefForm(initial={"address_type": "physical"})
    stayhere = "?stayhere=True" if request.GET.get("stayhere", None) else ""
    lat, lng, q_sugerencia = None, None, None
    if request.POST:
        if request.POST.get("save", False):
            form = SugerenciaGeorefForm(request.POST)
            if form.is_valid():
                address = form.save(commit=False)
                address.contact = contact_obj
                address.save()
                messages.success(request, "Dirección georreferenciada guardada con éxito")
                if request.GET.get("stayhere", None):
                    return HttpResponseRedirect(reverse("agregar_direccion", args=[contact_id]))
                else:
                    return HttpResponseRedirect(reverse("contact_detail", args=[contact_id]))
        elif request.POST.get("save_needs_georef", False):
            form = SugerenciaGeorefForm(request.POST)
            if form.is_valid():
                address = form.save(commit=False)
                address.contact = contact_obj
                address.needs_georef = True
                address.save()
                messages.warning(request, "Dirección guardada con éxito sin georeferenciación")
                if stayhere:
                    return HttpResponseRedirect(reverse("agregar_direccion", args=[contact_id]) + stayhere)
                else:
                    return HttpResponseRedirect(reverse("contact_detail", args=[contact_id]))
        elif request.POST.get("no_encuentro_direccion", False):
            form = SugerenciaGeorefForm(request.POST)
            if form.is_valid():
                address = form.save(commit=False)
                address.contact = contact_obj
                address.needs_georef = True
                address.save()
                messages.info(request, "Dirección guardada con éxito, buscando otras alternativas...")
                return HttpResponseRedirect(reverse("normalizar_direccion", args=[contact_id, address.id]) + stayhere)
        direccion, id_calle, id_localidad, id_portal = request.POST.get('sugerencias').split("|")
        j = seleccionar_sugerencia(direccion, id_calle, id_localidad, id_portal)
        state_name = j["departamento"].title()
        state_obj = State.objects.get(name=state_name)
        form = SugerenciaGeorefForm(
            initial={
                "contact": contact_obj,
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
        },
    )


@staff_member_required
def editar_direccion(request, contact_id, address_id):
    georef_activated = getattr(settings, "GEOREF_SERVICES", False)
    address_obj = get_object_or_404(Address, pk=address_id)
    contact_obj = get_object_or_404(Contact, pk=contact_id)
    lat, lng = address_obj.latitude or None, address_obj.longitude or None
    if request.POST.get("editar_direccion", False):
        form = SugerenciaGeorefForm(request.POST, instance=address_obj)
        if form.is_valid():
            address = form.save(commit=False)
            address.contact = contact_obj
            address.reset_georef()  # Ya cuenta con save
            messages.info(request, "Dirección editada con éxito, seleccionar georreferenciación...")
            messages.warning(
                request, "Salir de esta página sin confirmar casuará que la dirección no tenga georreferenciación"
            )
            return HttpResponseRedirect(reverse("normalizar_direccion", args=[contact_id, address.id]))
    elif request.POST.get("save_no_georef", False):
        form = SugerenciaGeorefForm(request.POST, instance=address_obj)
        if form.is_valid():
            address = form.save(commit=False)
            address.contact = contact_obj
            address.reset_georef()
            messages.info(request, "Dirección editada con éxito sin georreferenciar")
            return HttpResponseRedirect(reverse("contact_detail", args=[contact_id]))

    form = SugerenciaGeorefForm(instance=address_obj, initial={"address_type": "physical"})
    return render(
        request,
        "location/editar_direccion.html",
        {
            "georef_activated": georef_activated,
            "contact": contact_obj,
            "form": form,
            "lat": lat,
            "lng": lng,
        },
    )


@csrf_exempt
def sugerir_direccion_autocompletar(request):
    # TODO: Check why this is not being used
    # form_nuevo = SugerenciaGeorefForm()
    q, obs = separar_direccion(request.GET.get("q_direccion"))
    sugerencias = []
    if q:
        sugerencias = autocompletar_direccion(q, obs)
    return render(request, "location/sugerencias_htmx.html", {"sugerencias": sugerencias})
