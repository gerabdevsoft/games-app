"""Pruebas de expansión: Caja Sorpresas, Tragamonedas, Trivia Flash y no regresión de juegos existentes."""

import time
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
    return {"token": datos["token"], "usuario": datos["usuario"]}


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# Módulo Caja de Sorpresas
def test_caja_sorpresas_valida_rango_cofres_y_saldo_seguro():
    api_client = requests.Session()
    creado = crear_usuario_prueba(api_client)
    token = creado["token"]

    jugada = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=auth_headers(token),
        json={"nombre_juego": "caja_sorpresas", "monto_apuesta": 10, "numero_cofre": 2},
        timeout=20,
    )
    assert jugada.status_code == 200
    datos = jugada.json()
    assert datos["cofre_ganador"] in [1, 2, 3]
    assert datos["resultado"] in ["ganaste", "perdiste"]

    if datos["resultado"] == "ganaste":
        assert datos["premio"] == 22
        assert datos["nuevo_saldo"] == 122
    else:
        assert datos["premio"] == 0
        assert datos["nuevo_saldo"] == 90


def test_caja_sorpresas_rechaza_cofre_fuera_de_rango_y_apuesta_fuera_de_rango():
    api_client = requests.Session()
    creado = crear_usuario_prueba(api_client)
    token = creado["token"]

    cofre_fuera_rango = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=auth_headers(token),
        json={"nombre_juego": "caja_sorpresas", "monto_apuesta": 5, "numero_cofre": 4},
        timeout=20,
    )
    assert cofre_fuera_rango.status_code == 422

    apuesta_fuera_rango = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=auth_headers(token),
        json={"nombre_juego": "caja_sorpresas", "monto_apuesta": 1, "numero_cofre": 1},
        timeout=20,
    )
    assert apuesta_fuera_rango.status_code == 422


# Módulo Tragamonedas
def test_tragamonedas_contrato_iconos_premio_y_saldo():
    api_client = requests.Session()
    creado = crear_usuario_prueba(api_client)
    token = creado["token"]

    jugada = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=auth_headers(token),
        json={"nombre_juego": "tragamonedas", "monto_apuesta": 10},
        timeout=20,
    )
    assert jugada.status_code == 200
    datos = jugada.json()
    assert isinstance(datos["iconos"], list)
    assert len(datos["iconos"]) == 3

    todos_iguales = len(set(datos["iconos"])) == 1
    if datos["resultado"] == "ganaste":
        assert todos_iguales is True
        assert datos["premio"] == 30
        assert datos["nuevo_saldo"] == 130
    else:
        assert todos_iguales is False
        assert datos["premio"] == 0
        assert datos["nuevo_saldo"] == 90


# Módulo Trivia Flash
def test_trivia_flash_iniciar_no_expone_respuesta_correcta():
    api_client = requests.Session()
    creado = crear_usuario_prueba(api_client)
    token = creado["token"]

    inicio = api_client.post(
        f"{API_URL}/juegos/trivia-flash/iniciar",
        headers=auth_headers(token),
        json={"monto_apuesta": 5},
        timeout=20,
    )
    assert inicio.status_code == 200
    datos = inicio.json()
    assert "id_desafio" in datos
    assert "enunciado" in datos
    assert isinstance(datos["opciones"], list)
    assert len(datos["opciones"]) == 4
    assert "correcta" not in datos


def test_trivia_flash_usa_id_una_sola_vez_y_paga_si_correcta_en_tiempo():
    api_client = requests.Session()
    creado = crear_usuario_prueba(api_client)
    token = creado["token"]

    inicio = api_client.post(
        f"{API_URL}/juegos/trivia-flash/iniciar",
        headers=auth_headers(token),
        json={"monto_apuesta": 10},
        timeout=20,
    )
    assert inicio.status_code == 200
    desafio = inicio.json()["id_desafio"]

    primera_respuesta = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=auth_headers(token),
        json={"nombre_juego": "trivia_flash", "monto_apuesta": 10, "id_desafio": desafio, "id_opcion": "a"},
        timeout=20,
    )
    assert primera_respuesta.status_code == 200
    datos = primera_respuesta.json()
    assert datos["resultado"] in ["ganaste", "perdiste"]
    if datos["resultado"] == "ganaste":
        assert datos["premio"] == 15
        assert datos["nuevo_saldo"] == 115
    else:
        assert datos["premio"] == 0
        assert datos["nuevo_saldo"] == 90

    segunda_respuesta = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=auth_headers(token),
        json={"nombre_juego": "trivia_flash", "monto_apuesta": 10, "id_desafio": desafio, "id_opcion": "a"},
        timeout=20,
    )
    assert segunda_respuesta.status_code == 400
    assert "ya fue respondido" in segunda_respuesta.json()["detail"].lower()


def test_trivia_flash_pierde_por_tiempo_fuera_de_5_segundos():
    api_client = requests.Session()
    creado = crear_usuario_prueba(api_client)
    token = creado["token"]

    inicio = api_client.post(
        f"{API_URL}/juegos/trivia-flash/iniciar",
        headers=auth_headers(token),
        json={"monto_apuesta": 10},
        timeout=20,
    )
    assert inicio.status_code == 200
    desafio = inicio.json()["id_desafio"]

    time.sleep(6)
    respuesta_tardia = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=auth_headers(token),
        json={"nombre_juego": "trivia_flash", "monto_apuesta": 10, "id_desafio": desafio, "id_opcion": "a"},
        timeout=20,
    )
    assert respuesta_tardia.status_code == 200
    datos = respuesta_tardia.json()
    assert datos["resultado"] == "perdiste"
    assert datos["premio"] == 0
    assert datos["nuevo_saldo"] == 90
    assert "5 segundos" in datos["detalle"].lower()


# Módulo no regresión: Ruleta y Trivia Express
def test_no_regresion_ruleta_y_trivia_express():
    api_client = requests.Session()
    creado = crear_usuario_prueba(api_client)
    token = creado["token"]

    ruleta = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=auth_headers(token),
        json={"nombre_juego": "ruleta", "monto_apuesta": 2, "color": "azul"},
        timeout=20,
    )
    assert ruleta.status_code == 200
    datos_ruleta = ruleta.json()
    assert datos_ruleta["resultado"] in ["ganaste", "perdiste"]
    assert datos_ruleta["color_ganador"] in ["azul", "blanco"]

    preguntas = api_client.get(f"{API_URL}/juegos/preguntas", timeout=20)
    assert preguntas.status_code == 200
    primera = preguntas.json()[0]
    trivia = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=auth_headers(token),
        json={
            "nombre_juego": "trivia",
            "monto_apuesta": 2,
            "id_pregunta": primera["id"],
            "id_opcion": primera["opciones"][0]["id"],
        },
        timeout=20,
    )
    assert trivia.status_code == 200
    datos_trivia = trivia.json()
    assert datos_trivia["resultado"] in ["ganaste", "perdiste"]