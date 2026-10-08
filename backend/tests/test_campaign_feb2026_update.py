"""Pruebas backend para actualización de campaña: ruleta verde, trivia flash 10s y rasca y gana."""

import time
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


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# Módulo auth/no-regresión: registro, login y perfil/saldo
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
    assert datos["usuario"]["saldo"] == 100
    return {"correo": correo, "contrasena": contrasena, "token": datos["token"]}


def headers_auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_no_regresion_registro_login_y_perfil(api_client):
    creado = crear_usuario_prueba(api_client)

    login = api_client.post(
        f"{API_URL}/autenticacion/inicio-sesion",
        json={"correo": creado["correo"], "contrasena": creado["contrasena"]},
        timeout=20,
    )
    assert login.status_code == 200
    datos_login = login.json()
    assert isinstance(datos_login["token"], str)
    assert datos_login["usuario"]["correo"] == creado["correo"]

    perfil = api_client.get(
        f"{API_URL}/usuario/perfil",
        headers=headers_auth(datos_login["token"]),
        timeout=20,
    )
    assert perfil.status_code == 200
    datos_perfil = perfil.json()
    assert datos_perfil["saldo"] == 100
    assert datos_perfil["rol"] == "estudiante"


# Módulo ruleta: soporte azul/verde y apuesta 2-10
def test_ruleta_acepta_color_verde_y_retorna_color_ganador(api_client):
    token = crear_usuario_prueba(api_client)["token"]
    jugada = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=headers_auth(token),
        json={"nombre_juego": "ruleta", "monto_apuesta": 5, "color": "verde"},
        timeout=20,
    )
    assert jugada.status_code == 200
    datos = jugada.json()
    assert datos["color_ganador"] in ["azul", "verde"]
    assert datos["resultado"] in ["ganaste", "perdiste"]
    assert isinstance(datos["nuevo_saldo"], int)


@pytest.mark.parametrize("monto", [1, 11])
def test_ruleta_rechaza_apuestas_fuera_de_rango_2_10(api_client, monto):
    token = crear_usuario_prueba(api_client)["token"]
    jugada = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=headers_auth(token),
        json={"nombre_juego": "ruleta", "monto_apuesta": monto, "color": "verde"},
        timeout=20,
    )
    assert jugada.status_code == 422


# Módulo trivia flash: desafío válido, respuesta inmediata, uso único y timeout
def test_trivia_flash_iniciar_devuelve_pregunta_y_4_opciones(api_client):
    token = crear_usuario_prueba(api_client)["token"]
    inicio = api_client.post(
        f"{API_URL}/juegos/trivia-flash/iniciar",
        headers=headers_auth(token),
        json={"monto_apuesta": 2},
        timeout=20,
    )
    assert inicio.status_code == 200
    datos = inicio.json()
    assert "id_desafio" in datos
    assert isinstance(datos["enunciado"], str)
    assert isinstance(datos["opciones"], list)
    assert len(datos["opciones"]) == 4


def test_trivia_flash_respuesta_inmediata_se_procesa_y_no_reutiliza_desafio(api_client):
    token = crear_usuario_prueba(api_client)["token"]
    inicio = api_client.post(
        f"{API_URL}/juegos/trivia-flash/iniciar",
        headers=headers_auth(token),
        json={"monto_apuesta": 10},
        timeout=20,
    )
    assert inicio.status_code == 200
    desafio = inicio.json()["id_desafio"]

    respuesta = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=headers_auth(token),
        json={
            "nombre_juego": "trivia_flash",
            "monto_apuesta": 10,
            "id_desafio": desafio,
            "id_opcion": "a",
        },
        timeout=20,
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["resultado"] in ["ganaste", "perdiste"]
    assert isinstance(datos["nuevo_saldo"], int)

    segunda = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=headers_auth(token),
        json={
            "nombre_juego": "trivia_flash",
            "monto_apuesta": 10,
            "id_desafio": desafio,
            "id_opcion": "a",
        },
        timeout=20,
    )
    assert segunda.status_code == 400


def test_trivia_flash_fuera_de_tiempo_marca_perdida(api_client):
    token = crear_usuario_prueba(api_client)["token"]
    inicio = api_client.post(
        f"{API_URL}/juegos/trivia-flash/iniciar",
        headers=headers_auth(token),
        json={"monto_apuesta": 10},
        timeout=20,
    )
    assert inicio.status_code == 200
    desafio = inicio.json()["id_desafio"]

    time.sleep(12)
    respuesta_tardia = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=headers_auth(token),
        json={
            "nombre_juego": "trivia_flash",
            "monto_apuesta": 10,
            "id_desafio": desafio,
            "id_opcion": "a",
        },
        timeout=20,
    )
    assert respuesta_tardia.status_code == 200
    datos = respuesta_tardia.json()
    assert datos["resultado"] == "perdiste"
    assert "10 segundos" in datos["detalle"].lower()


# Módulo rasca y gana: contrato 3x3 (9 símbolos), payout x2 y apuesta 2-10
def test_rasca_gana_retorna_tablero_nueve_simbolos_y_saldo_valido(api_client):
    token = crear_usuario_prueba(api_client)["token"]
    jugada = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=headers_auth(token),
        json={"nombre_juego": "rasca_gana", "monto_apuesta": 10},
        timeout=20,
    )
    assert jugada.status_code == 200
    datos = jugada.json()
    assert isinstance(datos["tablero_rasca"], list)
    assert len(datos["tablero_rasca"]) == 9
    assert set(datos["tablero_rasca"]).issubset({"toga", "libro", "medalla"})

    if datos["resultado"] == "ganaste":
        assert datos["premio"] == 20
    else:
        assert datos["premio"] == 0


@pytest.mark.parametrize("monto", [1, 11])
def test_rasca_gana_rechaza_apuesta_fuera_de_rango_2_10(api_client, monto):
    token = crear_usuario_prueba(api_client)["token"]
    jugada = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=headers_auth(token),
        json={"nombre_juego": "rasca_gana", "monto_apuesta": monto},
        timeout=20,
    )
    assert jugada.status_code == 422


def test_rasca_gana_no_permite_saldo_negativo(api_client):
    token = crear_usuario_prueba(api_client)["token"]

    # Consumir saldo de forma determinística con trivia incorrecta (siempre pierde -10).
    preguntas = api_client.get(f"{API_URL}/juegos/preguntas", timeout=20)
    assert preguntas.status_code == 200
    primera = preguntas.json()[0]

    for _ in range(10):
        intento = api_client.post(
            f"{API_URL}/juegos/jugar",
            headers=headers_auth(token),
            json={
                "nombre_juego": "trivia",
                "monto_apuesta": 10,
                "id_pregunta": primera["id"],
                "id_opcion": "opcion_incorrecta_forzada",
            },
            timeout=20,
        )
        assert intento.status_code == 200

    sin_saldo = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=headers_auth(token),
        json={"nombre_juego": "rasca_gana", "monto_apuesta": 10},
        timeout=20,
    )
    assert sin_saldo.status_code == 400
    assert "suficientes" in sin_saldo.json()["detail"].lower()


def test_rasca_gana_probabilidad_sanidad_gana_y_pierde(api_client):
    token = crear_usuario_prueba(api_client)["token"]

    total = 40
    ganadas = 0
    perdidas = 0

    for _ in range(total):
        jugada = api_client.post(
            f"{API_URL}/juegos/jugar",
            headers=headers_auth(token),
            json={"nombre_juego": "rasca_gana", "monto_apuesta": 2},
            timeout=20,
        )
        assert jugada.status_code == 200
        resultado = jugada.json()["resultado"]
        if resultado == "ganaste":
            ganadas += 1
        else:
            perdidas += 1

    tasa_ganada = ganadas / total
    assert ganadas > 0
    assert perdidas > 0
    assert 0.10 <= tasa_ganada <= 0.55
