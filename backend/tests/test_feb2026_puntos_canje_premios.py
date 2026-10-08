"""Pruebas de API para puntos de canje y regresión mínima de premios/rutas protegidas."""

import os
import time
import uuid

import pytest
import requests
from dotenv import load_dotenv


load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")


def _api(path: str) -> str:
    if not BASE_URL:
        pytest.fail("REACT_APP_BACKEND_URL no está configurado")
    return f"{BASE_URL.rstrip('/')}/api{path}"


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def test_public_get_puntos_canje_listado_completo(api_client):
    """Módulo puntos-canje público: GET /api/puntos-canje devuelve lista válida."""
    response = api_client.get(_api("/puntos-canje"), timeout=20)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    if data:
        primer = data[0]
        assert isinstance(primer.get("id"), str) and primer["id"]
        assert isinstance(primer.get("facultad_id"), str) and primer["facultad_id"]
        assert isinstance(primer.get("facultad"), str) and primer["facultad"]
        assert isinstance(primer.get("direccion"), str) and primer["direccion"]
        assert isinstance(primer.get("telefono"), str) and primer["telefono"]
        assert isinstance(primer.get("responsable"), str) and primer["responsable"]


def test_registro_con_facultad_y_mi_facultad_filtra_correctamente(api_client):
    """Módulo autenticación+puntos-canje: registro con facultad y filtro por facultad_id."""
    puntos_resp = api_client.get(_api("/puntos-canje"), timeout=20)
    assert puntos_resp.status_code == 200
    puntos = puntos_resp.json()
    if not puntos:
        pytest.skip("No existen puntos de canje para validar filtrado por facultad")

    facultad_id_objetivo = puntos[0]["facultad_id"]
    timestamp = int(time.time())
    correo = f"test_puntos_{timestamp}_{uuid.uuid4().hex[:6]}@usfx.bo"
    cu = f"TESTPC{timestamp}{uuid.uuid4().hex[:3]}".upper()
    registro_payload = {
        "correo": correo,
        "contrasena": "TestPass123!",
        "nombre_completo": "TEST Usuario Puntos",
        "cu": cu,
        "facultad_id": facultad_id_objetivo,
    }

    registro_resp = api_client.post(_api("/autenticacion/registro"), json=registro_payload, timeout=25)
    assert registro_resp.status_code == 201
    reg_data = registro_resp.json()
    assert isinstance(reg_data.get("token"), str) and reg_data["token"]
    assert reg_data["usuario"]["correo"] == correo
    assert reg_data["usuario"]["rol"] == "estudiante"
    assert isinstance(reg_data["usuario"].get("facultad"), str) and reg_data["usuario"]["facultad"]

    auth_headers = {"Authorization": f"Bearer {reg_data['token']}"}
    mi_fac_resp = api_client.get(_api("/puntos-canje/mi-facultad"), headers=auth_headers, timeout=20)
    assert mi_fac_resp.status_code == 200
    mi_fac_data = mi_fac_resp.json()
    assert isinstance(mi_fac_data, list)
    assert len(mi_fac_data) >= 1
    for item in mi_fac_data:
        assert item["facultad_id"] == facultad_id_objetivo


def test_usuario_sin_facultad_recibe_lista_vacia_sin_error(api_client):
    """Módulo puntos-canje autenticado: usuario sin facultad recibe [] sin errores."""
    correo_admin = os.environ.get("CORREO_ADMIN_INICIAL")
    contrasena_admin = os.environ.get("CONTRASENA_ADMIN_INICIAL")
    if not correo_admin or not contrasena_admin:
        pytest.skip("Credenciales admin no disponibles en entorno")

    login_resp = api_client.post(
        _api("/autenticacion/inicio-sesion"),
        json={"correo": correo_admin, "contrasena": contrasena_admin},
        timeout=20,
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert login_data["usuario"]["rol"] == "administrador"

    auth_headers = {"Authorization": f"Bearer {login_data['token']}"}
    mi_fac_resp = api_client.get(_api("/puntos-canje/mi-facultad"), headers=auth_headers, timeout=20)
    assert mi_fac_resp.status_code == 200
    mi_fac_data = mi_fac_resp.json()
    assert mi_fac_data == []


def test_no_regresion_catalogo_premios_publico(api_client):
    """Módulo premios: el catálogo público responde estructura correcta."""
    response = api_client.get(_api("/premios"), timeout=20)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        premio = data[0]
        assert isinstance(premio.get("id"), str) and premio["id"]
        assert isinstance(premio.get("titulo"), str) and premio["titulo"]
        assert isinstance(premio.get("descripcion"), str) and premio["descripcion"]
        assert isinstance(premio.get("costo_monedas"), int)
        assert isinstance(premio.get("existencias"), int)


def test_no_regresion_proteccion_ruta_admin_sin_token(api_client):
    """Módulo protección de rutas API: endpoint admin exige autenticación."""
    response = api_client.get(_api("/administracion/puntos-canje"), timeout=20)
    assert response.status_code in (401, 403)
    data = response.json()
    assert "detail" in data
