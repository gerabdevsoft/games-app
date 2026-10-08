"""Pruebas críticas de facultades, registro, panel admin y puntos de canje."""

import os
import uuid
from pathlib import Path

import pytest
import requests


def obtener_base_url() -> str:
    base_url = os.environ.get("REACT_APP_BACKEND_URL")
    if base_url:
        return base_url.rstrip("/")

    ruta_env = Path("/app/frontend/.env")
    if not ruta_env.exists():
        raise RuntimeError("No existe /app/frontend/.env")

    for linea in ruta_env.read_text(encoding="utf-8").splitlines():
        if linea.startswith("REACT_APP_BACKEND_URL="):
            valor = linea.split("=", 1)[1].strip()
            if not valor:
                raise RuntimeError("REACT_APP_BACKEND_URL está vacío")
            return valor.rstrip("/")

    raise RuntimeError("REACT_APP_BACKEND_URL no definido")


BASE_URL = obtener_base_url()
API_URL = f"{BASE_URL}/api"
ADMIN_CORREO = "gestion@eduardorivero.usfx.bo"
ADMIN_CONTRASENA = os.environ.get("CONTRASENA_ADMIN_INICIAL", "RRB3DuG3RAbYjoy7Lv3BJC4q")

FACULTADES_ESPERADAS = {
    "Arquitectura y Ciencias del Hábitat",
    "Ciencias Agrarias",
    "Ciencias de Enfermería y Obstetricia",
    "Ciencias Económicas y Empresariales",
    "Ciencias Químico - Farmacéuticas y Bioquímicas",
    "Ciencias y Tecnología",
    "Ciencias y Tecnologías de la Salud",
    "Contaduría Pública y Ciencias Financieras",
    "Derecho, Ciencias Políticas y Sociales",
    "Humanidades y Ciencias de la Educación",
    "Ingeniería Civil",
    "Ingeniería y Ciencias Aplicadas Meca - Electrónicas",
    "Integral Defensores del Chaco (Sede Muyupampa)",
    "Medicina",
    "Odontología",
    "Técnica",
}


@pytest.fixture
def api_client():
    sesion = requests.Session()
    sesion.headers.update({"Content-Type": "application/json"})
    return sesion


# Módulo auth/facultades: login y consulta base
def iniciar_sesion(api_client: requests.Session, correo: str, contrasena: str) -> dict:
    respuesta = api_client.post(
        f"{API_URL}/autenticacion/inicio-sesion",
        json={"correo": correo, "contrasena": contrasena},
        timeout=20,
    )
    assert respuesta.status_code == 200
    data = respuesta.json()
    assert isinstance(data.get("token"), str) and data["token"]
    return data


def cabecera_auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def obtener_facultades(api_client: requests.Session) -> list[dict]:
    respuesta = api_client.get(f"{API_URL}/facultades", timeout=20)
    assert respuesta.status_code == 200
    data = respuesta.json()
    assert isinstance(data, list)
    return data


def registrar_estudiante_valido(api_client: requests.Session, facultad_id: str) -> dict:
    sufijo = uuid.uuid4().hex[:8]
    payload = {
        "correo": f"qa.facultad.{sufijo}@usfx.bo",
        "contrasena": "Password123",
        "nombre_completo": f"TEST Usuario {sufijo}",
        "cu": f"TESTCU{sufijo.upper()}",
        "facultad_id": facultad_id,
    }
    respuesta = api_client.post(f"{API_URL}/autenticacion/registro", json=payload, timeout=20)
    assert respuesta.status_code == 201
    return respuesta.json()


# Módulo facultades/registro
def test_facultades_devuelve_exactamente_16_y_nombres_esperados(api_client):
    facultades = obtener_facultades(api_client)
    assert len(facultades) == 16
    nombres = {item["nombre"] for item in facultades}
    assert nombres == FACULTADES_ESPERADAS


def test_registro_rechaza_facultad_invalida(api_client):
    payload = {
        "correo": f"qa.invalida.{uuid.uuid4().hex[:8]}@usfx.bo",
        "contrasena": "Password123",
        "nombre_completo": "TEST Facultad Invalida",
        "cu": f"TESTCU{uuid.uuid4().hex[:8].upper()}",
        "facultad_id": "facultad-inexistente",
    }
    respuesta = api_client.post(f"{API_URL}/autenticacion/registro", json=payload, timeout=20)
    assert respuesta.status_code == 422
    assert "facultad" in respuesta.json().get("detail", "").lower()


def test_registro_valido_guarda_y_retorna_nombre_facultad(api_client):
    facultades = obtener_facultades(api_client)
    seleccionada = facultades[0]
    registro = registrar_estudiante_valido(api_client, facultad_id=seleccionada["id"])

    usuario = registro["usuario"]
    assert usuario["facultad"] == seleccionada["nombre"]
    assert usuario["rol"] == "estudiante"

    perfil = api_client.get(
        f"{API_URL}/usuario/perfil",
        headers=cabecera_auth(registro["token"]),
        timeout=20,
    )
    assert perfil.status_code == 200
    assert perfil.json()["facultad"] == seleccionada["nombre"]


# Módulo admin: resumen/lista/permisos
def test_admin_resumen_usuarios_y_lista(api_client):
    admin = iniciar_sesion(api_client, ADMIN_CORREO, ADMIN_CONTRASENA)

    resumen = api_client.get(
        f"{API_URL}/administracion/usuarios/resumen",
        headers=cabecera_auth(admin["token"]),
        timeout=20,
    )
    assert resumen.status_code == 200
    total = resumen.json().get("total")
    assert isinstance(total, int)
    assert total >= 0

    lista = api_client.get(
        f"{API_URL}/administracion/usuarios/lista",
        headers=cabecera_auth(admin["token"]),
        timeout=20,
    )
    assert lista.status_code == 200
    usuarios = lista.json()
    assert isinstance(usuarios, list)
    if usuarios:
        primero = usuarios[0]
        assert "nombre_completo" in primero
        assert "facultad" in primero
        assert isinstance(primero.get("saldo"), int)


def test_no_admin_no_accede_a_lista_usuarios_ni_puntos_canje(api_client):
    facultades = obtener_facultades(api_client)
    estudiante = registrar_estudiante_valido(api_client, facultad_id=facultades[0]["id"])
    headers = cabecera_auth(estudiante["token"])

    lista_usuarios = api_client.get(f"{API_URL}/administracion/usuarios/lista", headers=headers, timeout=20)
    assert lista_usuarios.status_code == 403

    lista_puntos = api_client.get(f"{API_URL}/administracion/puntos-canje", headers=headers, timeout=20)
    assert lista_puntos.status_code == 403

    crear_punto = api_client.post(
        f"{API_URL}/administracion/puntos-canje",
        headers=headers,
        json={
            "facultad_id": facultades[0]["id"],
            "direccion": "TEST Calle 123",
            "telefono": "1234567",
            "responsable": "TEST Responsable",
        },
        timeout=20,
    )
    assert crear_punto.status_code == 403


# Módulo puntos de canje: endpoint protegido + validaciones de formulario sin persistir éxito
def test_admin_puntos_canje_requiere_campos_y_facultad_valida_sin_insertar(api_client):
    admin = iniciar_sesion(api_client, ADMIN_CORREO, ADMIN_CONTRASENA)
    headers = cabecera_auth(admin["token"])

    incompleto = api_client.post(
        f"{API_URL}/administracion/puntos-canje",
        headers=headers,
        json={"facultad_id": "", "direccion": "", "telefono": "", "responsable": ""},
        timeout=20,
    )
    assert incompleto.status_code == 422

    facultad_invalida = api_client.post(
        f"{API_URL}/administracion/puntos-canje",
        headers=headers,
        json={
            "facultad_id": "facultad-inexistente",
            "direccion": "Av. Siempre Viva 742",
            "telefono": "77777777",
            "responsable": "Responsable QA",
        },
        timeout=20,
    )
    assert facultad_invalida.status_code == 422
    assert "facultad" in facultad_invalida.json().get("detail", "").lower()
