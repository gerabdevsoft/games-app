"""Pruebas críticas de autenticación, juegos y premios para campaña USFX."""

import uuid
from pathlib import Path

import requests


# Módulo de configuración: URL pública desde frontend/.env
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


def crear_usuario_prueba(api_client: requests.Session) -> dict:
    correo = f"test_{uuid.uuid4().hex[:10]}@usfx.bo"
    contrasena = "Password123"
    respuesta = api_client.post(
        f"{API_URL}/autenticacion/registro",
        json={"correo": correo, "contrasena": contrasena},
        timeout=20,
    )
    assert respuesta.status_code == 201
    datos = respuesta.json()
    return {
        "correo": correo,
        "contrasena": contrasena,
        "token": datos["token"],
        "usuario": datos["usuario"],
    }


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# Módulo de salud y autenticación
def test_salud_activa():
    respuesta = requests.get(f"{API_URL}/salud", timeout=20)
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "activo"
    assert "campana" in datos


def test_registro_crea_jwt_y_saldo_inicial_100():
    api_client = requests.Session()
    correo = f"registro_{uuid.uuid4().hex[:10]}@usfx.bo"
    contrasena = "Password123"

    respuesta = api_client.post(
        f"{API_URL}/autenticacion/registro",
        json={"correo": correo, "contrasena": contrasena},
        timeout=20,
    )

    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert isinstance(datos["token"], str)
    assert len(datos["token"]) > 20
    assert datos["tipo_token"] == "bearer"
    assert datos["usuario"]["correo"] == correo
    assert datos["usuario"]["saldo"] == 100


def test_inicio_sesion_y_perfil_protegido():
    api_client = requests.Session()
    creado = crear_usuario_prueba(api_client)

    login = api_client.post(
        f"{API_URL}/autenticacion/inicio-sesion",
        json={"correo": creado["correo"], "contrasena": creado["contrasena"]},
        timeout=20,
    )
    assert login.status_code == 200
    datos_login = login.json()
    token = datos_login["token"]
    assert datos_login["usuario"]["correo"] == creado["correo"]

    perfil = api_client.get(
        f"{API_URL}/usuario/perfil",
        headers=auth_headers(token),
        timeout=20,
    )
    assert perfil.status_code == 200
    datos_perfil = perfil.json()
    assert datos_perfil["correo"] == creado["correo"]
    assert datos_perfil["saldo"] == 100


# Módulo de juegos: ruleta y trivia
def test_ruleta_valida_actualiza_saldo_y_rechaza_saldo_insuficiente():
    api_client = requests.Session()
    creado = crear_usuario_prueba(api_client)
    token = creado["token"]

    jugada = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=auth_headers(token),
        json={"nombre_juego": "ruleta", "monto_apuesta": 10, "color": "azul"},
        timeout=20,
    )
    assert jugada.status_code == 200
    datos_jugada = jugada.json()
    assert datos_jugada["resultado"] in ["ganaste", "perdiste"]
    assert isinstance(datos_jugada["nuevo_saldo"], int)
    assert datos_jugada["nuevo_saldo"] >= 0

    saldo_insuficiente = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=auth_headers(token),
        json={"nombre_juego": "ruleta", "monto_apuesta": 101, "color": "blanco"},
        timeout=20,
    )
    assert saldo_insuficiente.status_code == 422


def test_preguntas_y_trivia_con_respuesta_valida():
    api_client = requests.Session()
    creado = crear_usuario_prueba(api_client)
    token = creado["token"]

    preguntas = api_client.get(f"{API_URL}/juegos/preguntas", timeout=20)
    assert preguntas.status_code == 200
    lista = preguntas.json()
    assert isinstance(lista, list)
    assert len(lista) > 0
    assert "id" in lista[0]
    assert "opciones" in lista[0]

    id_pregunta = lista[0]["id"]
    id_opcion = lista[0]["opciones"][0]["id"]

    trivia = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=auth_headers(token),
        json={
            "nombre_juego": "trivia",
            "monto_apuesta": 10,
            "id_pregunta": id_pregunta,
            "id_opcion": id_opcion,
        },
        timeout=20,
    )
    assert trivia.status_code == 200
    datos_trivia = trivia.json()
    assert datos_trivia["resultado"] in ["ganaste", "perdiste"]
    assert isinstance(datos_trivia["nuevo_saldo"], int)


# Módulo de premios y autorización
def test_premios_inicialmente_vacio_o_lista_valida():
    respuesta = requests.get(f"{API_URL}/premios", timeout=20)
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert isinstance(datos, list)


def test_administracion_premios_denegada_para_no_admin():
    api_client = requests.Session()
    creado = crear_usuario_prueba(api_client)
    token = creado["token"]

    respuesta = api_client.post(
        f"{API_URL}/administracion/premios",
        headers=auth_headers(token),
        json={
            "titulo": "Premio no autorizado",
            "descripcion": "No debería crearse",
            "costo_monedas": 10,
            "existencias": 1,
            "imagen_url": "",
        },
        timeout=20,
    )
    assert respuesta.status_code == 403
    assert "administradora" in respuesta.json()["detail"].lower()
