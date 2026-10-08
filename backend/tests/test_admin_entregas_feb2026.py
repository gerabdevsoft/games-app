"""Pruebas backend para módulo de administración de entregas presenciales."""

import uuid
from pathlib import Path

import pytest
import requests


# Módulo de configuración: URL pública tomada desde frontend/.env
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
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# Módulo auth: login administrador
def iniciar_sesion(api_client: requests.Session, correo: str, contrasena: str) -> str:
    respuesta = api_client.post(
        f"{API_URL}/autenticacion/inicio-sesion",
        json={"correo": correo, "contrasena": contrasena},
        timeout=20,
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert isinstance(datos["token"], str)
    return datos["token"]


def headers_auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def registrar_estudiante(api_client: requests.Session) -> dict:
    correo = f"qa.entregas.{uuid.uuid4().hex[:8]}@usfx.bo"
    contrasena = "Password123"
    respuesta = api_client.post(
        f"{API_URL}/autenticacion/registro",
        json={"correo": correo, "contrasena": contrasena},
        timeout=20,
    )
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["usuario"]["rol"] == "estudiante"
    assert datos["usuario"]["saldo"] == 100
    return {
        "id": datos["usuario"]["id"],
        "correo": correo,
        "contrasena": contrasena,
        "token": datos["token"],
    }


# Módulo permisos: estudiante no accede a endpoints administrativos
def test_estudiante_no_puede_buscar_usuarios_admin(api_client):
    estudiante = registrar_estudiante(api_client)
    respuesta = api_client.get(
        f"{API_URL}/administracion/usuarios",
        params={"buscar": "qa.entregas"},
        headers=headers_auth(estudiante["token"]),
        timeout=20,
    )
    assert respuesta.status_code == 403
    assert "administradora" in respuesta.json()["detail"].lower()


def test_post_entregas_rechaza_sin_autorizacion(api_client):
    respuesta = api_client.post(
        f"{API_URL}/administracion/entregas",
        json={"id_usuario": "u-no-auth", "id_premio": "p-no-auth"},
        timeout=20,
    )
    assert respuesta.status_code == 401
    assert "detail" in respuesta.json()


def test_post_entregas_rechaza_token_estudiante(api_client):
    estudiante = registrar_estudiante(api_client)
    respuesta = api_client.post(
        f"{API_URL}/administracion/entregas",
        json={"id_usuario": estudiante["id"], "id_premio": "premio-inexistente"},
        headers=headers_auth(estudiante["token"]),
        timeout=20,
    )
    assert respuesta.status_code == 403
    assert "administradora" in respuesta.json()["detail"].lower()


# Módulo búsqueda: devuelve estudiantes por correo con saldo
def test_busqueda_admin_por_correo_devuelve_estudiante_con_saldo(api_client):
    admin_token = iniciar_sesion(api_client, ADMIN_CORREO, ADMIN_CONTRASENA)
    estudiante = registrar_estudiante(api_client)

    termino = estudiante["correo"].split("@")[0]
    respuesta = api_client.get(
        f"{API_URL}/administracion/usuarios",
        params={"buscar": termino},
        headers=headers_auth(admin_token),
        timeout=20,
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert isinstance(datos, list)
    assert any(item["correo"] == estudiante["correo"] and isinstance(item["saldo"], int) for item in datos)


# Módulo entrega: premio inexistente/sin stock no descuenta saldo
def test_entrega_rechaza_premio_inexistente_sin_descontar_saldo(api_client):
    admin_token = iniciar_sesion(api_client, ADMIN_CORREO, ADMIN_CONTRASENA)
    estudiante = registrar_estudiante(api_client)

    perfil_antes = api_client.get(
        f"{API_URL}/usuario/perfil",
        headers=headers_auth(estudiante["token"]),
        timeout=20,
    )
    assert perfil_antes.status_code == 200
    saldo_antes = perfil_antes.json()["saldo"]

    respuesta = api_client.post(
        f"{API_URL}/administracion/entregas",
        headers=headers_auth(admin_token),
        json={"id_usuario": estudiante["id"], "id_premio": f"premio-no-existe-{uuid.uuid4().hex[:6]}"},
        timeout=20,
    )
    assert respuesta.status_code == 400
    assert "existencias" in respuesta.json()["detail"].lower()

    perfil_despues = api_client.get(
        f"{API_URL}/usuario/perfil",
        headers=headers_auth(estudiante["token"]),
        timeout=20,
    )
    assert perfil_despues.status_code == 200
    assert perfil_despues.json()["saldo"] == saldo_antes


# Módulo contrato de entrega: se valida cuando existe premio con stock en catálogo real
def test_entrega_exitosa_regresa_mensaje_y_nuevo_saldo_si_hay_premio_disponible(api_client):
    admin_token = iniciar_sesion(api_client, ADMIN_CORREO, ADMIN_CONTRASENA)
    estudiante = registrar_estudiante(api_client)

    catalogo = api_client.get(f"{API_URL}/premios", timeout=20)
    assert catalogo.status_code == 200
    premios = catalogo.json()

    premio_disponible = next(
        (
            item
            for item in premios
            if isinstance(item.get("existencias"), int)
            and item["existencias"] > 0
            and isinstance(item.get("costo_monedas"), int)
            and item["costo_monedas"] <= 100
        ),
        None,
    )

    if not premio_disponible:
        pytest.skip("Catálogo sin premio apto con existencias>0 y costo<=100; se evita crear premio de prueba persistente")

    perfil_antes = api_client.get(
        f"{API_URL}/usuario/perfil",
        headers=headers_auth(estudiante["token"]),
        timeout=20,
    )
    assert perfil_antes.status_code == 200
    saldo_antes = perfil_antes.json()["saldo"]

    entrega = api_client.post(
        f"{API_URL}/administracion/entregas",
        headers=headers_auth(admin_token),
        json={"id_usuario": estudiante["id"], "id_premio": premio_disponible["id"]},
        timeout=20,
    )
    assert entrega.status_code == 200
    datos = entrega.json()
    assert "mensaje" in datos and estudiante["correo"] in datos["mensaje"]
    assert isinstance(datos.get("nuevo_saldo"), int)

    perfil_despues = api_client.get(
        f"{API_URL}/usuario/perfil",
        headers=headers_auth(estudiante["token"]),
        timeout=20,
    )
    assert perfil_despues.status_code == 200
    assert perfil_despues.json()["saldo"] == saldo_antes - premio_disponible["costo_monedas"]
    assert datos["nuevo_saldo"] == perfil_despues.json()["saldo"]
