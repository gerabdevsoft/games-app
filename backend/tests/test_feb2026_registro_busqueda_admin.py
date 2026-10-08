"""Pruebas backend de registro con nombre/CU y búsqueda administrativa por correo, nombre y CU."""

import uuid
from pathlib import Path

import pytest
import requests


# Módulo configuración: URL pública del frontend/.env
def obtener_base_url() -> str:
    ruta_env = Path("/app/frontend/.env")
    if not ruta_env.exists():
        raise RuntimeError("No existe /app/frontend/.env")

    for linea in ruta_env.read_text(encoding="utf-8").splitlines():
        if linea.startswith("REACT_APP_BACKEND_URL="):
            valor = linea.split("=", 1)[1].strip()
            if not valor:
                raise RuntimeError("REACT_APP_BACKEND_URL está vacío")
            return valor.rstrip("/")

    raise RuntimeError("REACT_APP_BACKEND_URL no definido en /app/frontend/.env")


BASE_URL = obtener_base_url()
API_URL = f"{BASE_URL}/api"
ADMIN_CORREO = "gestion@eduardorivero.usfx.bo"
ADMIN_CONTRASENA = "RRB3DuG3RAbYjoy7Lv3BJC4q"


@pytest.fixture
def api_client():
    sesion = requests.Session()
    sesion.headers.update({"Content-Type": "application/json"})
    return sesion


# Módulo auth: login y utilidades de token
def iniciar_sesion(api_client: requests.Session, correo: str, contrasena: str) -> dict:
    respuesta = api_client.post(
        f"{API_URL}/autenticacion/inicio-sesion",
        json={"correo": correo, "contrasena": contrasena},
        timeout=20,
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert isinstance(datos["token"], str)
    assert datos["token"]
    assert datos["usuario"]["correo"] == correo.lower()
    return datos


def headers_auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def payload_registro(correo: str, cu: str, nombre: str = "Andrea Prueba Entregas") -> dict:
    return {
        "correo": correo,
        "contrasena": "Password123",
        "nombre_completo": nombre,
        "cu": cu,
    }


def registrar_estudiante(api_client: requests.Session, nombre: str = "Andrea Prueba Entregas") -> dict:
    sufijo = uuid.uuid4().hex[:8]
    correo = f"qa.registro.{sufijo}@usfx.bo"
    cu = f"CU{uuid.uuid4().hex[:10].upper()}"
    respuesta = api_client.post(
        f"{API_URL}/autenticacion/registro",
        json=payload_registro(correo=correo, cu=cu, nombre=nombre),
        timeout=20,
    )
    assert respuesta.status_code == 201
    datos = respuesta.json()
    usuario = datos["usuario"]
    assert usuario["correo"] == correo.lower()
    assert usuario["nombre_completo"] == nombre
    assert usuario["cu"] == cu
    assert usuario["rol"] == "estudiante"
    assert isinstance(usuario["saldo"], int)
    return {"correo": correo.lower(), "contrasena": "Password123", "cu": cu, "nombre": nombre, "token": datos["token"]}


# Módulo registro: requiere y persiste nombre_completo + CU
def test_registro_guarda_y_devuelve_nombre_completo_y_cu(api_client):
    correo = f"qa.full.{uuid.uuid4().hex[:8]}@usfx.bo"
    cu = f"CU{uuid.uuid4().hex[:10].upper()}"
    nombre = "Andrea Prueba Entregas"

    registro = api_client.post(
        f"{API_URL}/autenticacion/registro",
        json=payload_registro(correo=correo, cu=cu, nombre=nombre),
        timeout=20,
    )
    assert registro.status_code == 201
    datos = registro.json()
    usuario = datos["usuario"]
    assert usuario["correo"] == correo.lower()
    assert usuario["nombre_completo"] == nombre
    assert usuario["cu"] == cu

    perfil = api_client.get(
        f"{API_URL}/usuario/perfil",
        headers=headers_auth(datos["token"]),
        timeout=20,
    )
    assert perfil.status_code == 200
    perfil_data = perfil.json()
    assert perfil_data["nombre_completo"] == nombre
    assert perfil_data["cu"] == cu


def test_registro_repite_cu_devuelve_409(api_client):
    cu = f"CU{uuid.uuid4().hex[:10].upper()}"
    primer_correo = f"qa.dup1.{uuid.uuid4().hex[:8]}@usfx.bo"
    segundo_correo = f"qa.dup2.{uuid.uuid4().hex[:8]}@usfx.bo"

    primero = api_client.post(
        f"{API_URL}/autenticacion/registro",
        json=payload_registro(correo=primer_correo, cu=cu, nombre="Estudiante Uno"),
        timeout=20,
    )
    assert primero.status_code == 201

    segundo = api_client.post(
        f"{API_URL}/autenticacion/registro",
        json=payload_registro(correo=segundo_correo, cu=cu, nombre="Estudiante Dos"),
        timeout=20,
    )
    assert segundo.status_code == 409
    assert "cu" in segundo.json()["detail"].lower()


# Módulo login: mantiene correo+contraseña
def test_login_existente_funciona_con_correo_y_contrasena(api_client):
    creado = registrar_estudiante(api_client)
    login = iniciar_sesion(api_client, creado["correo"], creado["contrasena"])
    assert login["usuario"]["correo"] == creado["correo"]
    assert login["usuario"]["nombre_completo"] == creado["nombre"]
    assert login["usuario"]["cu"] == creado["cu"]


# Módulo administración: búsqueda por correo/nombre/CU y permisos
def test_admin_busca_por_correo_nombre_y_cu(api_client):
    admin = iniciar_sesion(api_client, ADMIN_CORREO, ADMIN_CONTRASENA)
    creado = registrar_estudiante(api_client, nombre="Nombre QA Busqueda")

    fragmento_correo = creado["correo"].split("@")[0][-6:]
    por_correo = api_client.get(
        f"{API_URL}/administracion/usuarios",
        params={"buscar": fragmento_correo},
        headers=headers_auth(admin["token"]),
        timeout=20,
    )
    assert por_correo.status_code == 200
    lista_correo = por_correo.json()
    item_correo = next((item for item in lista_correo if item["correo"] == creado["correo"]), None)
    assert item_correo is not None
    assert item_correo["nombre_completo"] == creado["nombre"]
    assert item_correo["cu"] == creado["cu"]
    assert isinstance(item_correo["saldo"], int)

    por_nombre = api_client.get(
        f"{API_URL}/administracion/usuarios",
        params={"buscar": "QA Busq"},
        headers=headers_auth(admin["token"]),
        timeout=20,
    )
    assert por_nombre.status_code == 200
    lista_nombre = por_nombre.json()
    item_nombre = next((item for item in lista_nombre if item["correo"] == creado["correo"]), None)
    assert item_nombre is not None
    assert item_nombre["nombre_completo"] == creado["nombre"]

    por_cu = api_client.get(
        f"{API_URL}/administracion/usuarios",
        params={"buscar": creado["cu"]},
        headers=headers_auth(admin["token"]),
        timeout=20,
    )
    assert por_cu.status_code == 200
    lista_cu = por_cu.json()
    item_cu = next((item for item in lista_cu if item["correo"] == creado["correo"]), None)
    assert item_cu is not None
    assert item_cu["cu"] == creado["cu"]


def test_no_admin_no_puede_busqueda_administrativa(api_client):
    estudiante = registrar_estudiante(api_client)
    respuesta = api_client.get(
        f"{API_URL}/administracion/usuarios",
        params={"buscar": estudiante["correo"].split("@")[0]},
        headers=headers_auth(estudiante["token"]),
        timeout=20,
    )
    assert respuesta.status_code == 403
    assert "administradora" in respuesta.json()["detail"].lower()
