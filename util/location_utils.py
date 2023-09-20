import requests
from django.conf import settings
import requests_cache
from requests_cache import NEVER_EXPIRE, CachedSession
import re
import pandas as pd
from django.contrib.gis.geos import Point

session = CachedSession("location_utils_cache", backend="sqlite", expire_after=NEVER_EXPIRE)

import logging

logger = logging.getLogger(__name__)


def buscar_localidades(state):
    """
    Devuelve localidades a partir del nombre del departamento
    """
    url = settings.SERVICIO_LOCALIDADES
    params = {"departamento": departamento, "alias": True}
    response = session.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        return None


def autocompletar_direccion(texto, obs):
    """
    A partir de un texto, devuelve una lista de posibles direcciones (sin geolocalización)
    """
    url = settings.SERVICIO_DIRECCION_AUTOCOMPLETADO
    params = {"q": texto, "soloLocalidad": False, "limit": 20}
    response = session.get(url, params=params)
    result = []
    if response.status_code == 200:
        sugerencias = response.json()
        df_sug = pd.DataFrame(sugerencias)
        if df_sug.empty:
            return result
        df_sug = df_sug[df_sug["type"] == "CALLEyPORTAL"]
        df_sug.drop_duplicates(subset=["nomVia", "portalNumber", "idDepartamento", "idLocalidad"], inplace=True)
        sugerencias = df_sug.to_dict("records")
        for sugerencia in sugerencias:
            if obs:
                sugerencia[
                    "resumen"
                ] = f"{sugerencia['nomVia']} {sugerencia['portalNumber']}, {obs}, {sugerencia['localidad']}, {sugerencia['departamento']}".title()
                sugerencia["direccion"] = f"{sugerencia['nomVia']} {sugerencia['portalNumber']}, {obs}".title()
            else:
                sugerencia[
                    "resumen"
                ] = f"{sugerencia['nomVia']} {sugerencia['portalNumber']}, {sugerencia['localidad']}, {sugerencia['departamento']}".title()
                sugerencia["direccion"] = f"{sugerencia['nomVia']} {sugerencia['portalNumber']}".title()
            result.append(sugerencia)
    result.sort(key=lambda x: x["idDepartamento"])
    return result


def buscar_direccion(sugerencias, sug_num_calle, sug_num_localidad, sug_num_portal, obs, type="CALLEyPORTAL"):
    """
    A partir del resultado del autocompletar devuelve una dirección exacta con geolocalización
    """
    url = settings.SERVICIO_BUSQUEDA_DIRECCION
    sug_num_calle = int(sug_num_calle)
    sug_num_localidad = int(sug_num_localidad)
    sug_num_portal = int(sug_num_portal)

    params = {"idcalle": sug_num_calle, "portal": sug_num_portal, "type": "CALLEyPORTAL"}
    response = session.get(url, params=params)

    df_sugerencias = pd.DataFrame(sugerencias)[
        ["type", "idCalle", "nomVia", "idLocalidad", "localidad", "idDepartamento", "departamento", "portalNumber"]
    ]

    if response.status_code == 200:
        direcciones = response.json()
        if not direcciones:
            return None
        df_direcciones = pd.DataFrame(direcciones)[
            [
                "type",
                "idCalle",
                "nomVia",
                "idLocalidad",
                "localidad",
                "idDepartamento",
                "departamento",
                "portalNumber",
                "geom",
                "lat",
                "lng",
            ]
        ]
        direccion = None

        df = df_sugerencias.merge(
            df_direcciones,
            on=[
                "type",
                "idCalle",
                "nomVia",
                "idLocalidad",
                "localidad",
                "idDepartamento",
                "departamento",
                "portalNumber",
            ],
            how="left",
        )
        df_exact = df.query(
            "type == 'CALLEyPORTAL' and idCalle == @sug_num_calle and portalNumber == @sug_num_portal and idLocalidad == @sug_num_localidad"
        )
       

        if not df_exact.empty:
            direccion = df.to_dict("records")[0]
            df_exact_but_portal_number = df.query(
                "type == 'CALLEyPORTAL' and idCalle == @sug_num_calle and idLocalidad == @sug_num_localidad"
                )
            if not df_exact_but_portal_number.empty:
                direccion = df_exact_but_portal_number.to_dict("records")[0]

        else:
            direccion = df_direcciones.to_dict("records")[0]

        
        if direccion:
            direccion_str = f"{direccion['nomVia'].strip(' ,')} {direccion['portalNumber']}".title()
            if obs:
                direccion_str = (
                    f"{direccion['nomVia'].strip(' ,')} {direccion['portalNumber']}, {obs.strip(' ,')}".title()
                )
            return {
                "pais": "URUGUAY".title(),
                "direccion": direccion_str,
                "localidad": direccion["localidad"].title(),
                "localidad_id": direccion["idLocalidad"],
                "latitud": direccion["lat"],
                "longitud": direccion["lng"],
                "departamento": direccion["departamento"].upper(),
                "departamento_id": direccion["idDepartamento"],
            }
    return None


def separar_direccion(direccion, state=None, city=None):
    """
    Separa una dirección en sus componentes
    """
    q = direccion
    obs = ""
    parts = [part.strip() for part in re.split(r"(\d+)", direccion) if part.strip()]
    for i, part in enumerate(parts):
        if re.match(r"(\d+)", part) and i == 0:
            continue
        else:
            q = " ".join(parts[: i + 2])
            obs = " ".join(parts[i + 2 :])
            break

    if city:
        q = f"{q}, {city}"
    if state:
        q = f"{q}, {state}"
    return q.strip(" ,"), obs.strip(" ,")


def seleccionar_sugerencia(resumen_direccion, sug_num_calle, sug_num_localidad, sug_num_portal):
    q, obs = separar_direccion(resumen_direccion)
    sugerencias = autocompletar_direccion(q, obs)
    direccion = buscar_direccion(sugerencias, sug_num_calle, sug_num_localidad, sug_num_portal, obs)
    if direccion:
        lat = f"{direccion['latitud']:.6f}"
        if lat:
            lat = float(lat.replace(",", "."))
        lng = f"{direccion['longitud']:.6f}"
        if lng:
            lng = float(lng.replace(",", "."))
        punto_geografico = None
        if lng and lat:
            logger.info(lng, lat)
            punto_geografico = Point(lng, lat, srid=4326)
        return {
            "direccion": direccion["direccion"],
            "localidad": direccion["localidad"],
            "localidad_id": direccion["localidad_id"] if direccion["localidad_id"] else None,
            "latitud": lat if lat else None,
            "longitud": lng if lng else None,
            "departamento": direccion["departamento"],
            "departamento_id": direccion["departamento_id"] if direccion["departamento_id"] else None,
            "punto_geografico": punto_geografico,
        }
    direccion = ""
    if q:
        direccion = f"{q.title()}"
        if obs:
            direccion += f", {obs.title()}"

    return {
        "direccion": direccion,
        "localidad": "",
        "localidad_id": "",
        "latitud": "",
        "longitud": "",
        "departamento": "",
        "departamento_id": "",
    }


def save_address(address):
    if address.latitude and address.longitude:
        if type(address.latitude) == str:
            address.latitude = address.latitude.replace(",", ".")
        address.latitude = float(address.latitude)
        if type(address.longitude) == str:
            address.longitude =addressself.longitude.replace(",", ".")
        address.longitude = float(address.longitude)
        address.punto_geografico = Point(address.longitude, address.latitude)
    if address.punto_geografico and not (address.latitude and address.longitude):
        address.latitude = address.punto_geografico.y
        address.longitude = address.punto_geografico.x
    if address.state_id and address.city_id and address.punto_geografico:
        address.direccion_verificada = True
    address.save()


def separar_direccion_de_obs(address_1, state=None, city=None):
    """
    Necesitamos separar en dos campos la dirección y las observaciones
    """
    if address_1:
        if state == "Montevideo":
            city = "Montevideo"
        return separar_direccion(address_1, state, city)
    else:
        return "", ""


def buscar_alternativas_normalizadas(address_1, state=None, city=None):
    """
    Busca alternativas normalizadas de la dirección
    """
    sugerencias = []
    try:
        if address_1:
            q, obs = separar_direccion_de_obs(address_1, state, city)
            direcciones = autocompletar_direccion(q, obs)
            return direcciones
    except Exception as e:
        raise
    return sugerencias


def aplicar_sugerencia(address, sugerencia):
    """
    Aplica una sugerencia de autocompletado
    """
    if sugerencia:
        address.notes = address.notes + f"Sugerencia aplicada el {timezone.now().strftime('%Y/%m/%d %H:%M:%S')}, dirección anterior: {address.direccion_1}\n\n"
        address.address_1 = sugerencia["direccion"]
        address.state = sugerencia["departamento"]
        address.state_id = sugerencia["departamento_id"]
        address.city = sugerencia["localidad"]
        address.city_id = sugerencia["localidad_id"]
        address.latitude = sugerencia["latitud"]
        address.longitude = sugerencia["longitud"]
        address.save()

"""
Stuff to consider LATER
def aceptar_sugerencias(address, sugerencias, responsabilidad, persona):
    with transaction.atomic():
        for sugerencia in sugerencias:
            address.__setattr__(sugerencia.nombre_campo, sugerencia.valor_sugerido)
            sugerencia.estado_sugerencia = choices.EstadoSugerencia.APROBADA
        address.save()
        persona.update_user(responsabilidad)
        return True


def get_sugerencias_pendientes(self):
    return Sugerencia.objects.filter(nombre_objeto="direccion", id_objeto=self.pk, estado_sugerencia="PENDIENTE").all()


def sugerencias_pendientes_count(self):
    return self.get_sugerencias_pendientes().count()
"""
