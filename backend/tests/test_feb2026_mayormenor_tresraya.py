"""Pruebas Feb-2026: Mayor/Menor y 3 en Raya del Rector."""

import uuid
from pathlib import Path

import pytest
import requests


# Módulo configuración: URL pública desde frontend/.env
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


# Módulo autenticación auxiliar para pruebas de juegos
def crear_usuario_prueba(api_client: requests.Session) -> dict:
    correo = f"test_{uuid.uuid4().hex[:12]}@usfx.bo"
    contrasena = "Password123"
    respuesta = api_client.post(
        f"{API_URL}/autenticacion/registro",
        json={"correo": correo, "contrasena": contrasena},
        timeout=20,
    )
    assert respuesta.status_code == 201
    datos = respuesta.json()
    return {"token": datos["token"], "id": datos["usuario"]["id"], "correo": correo}


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def perfil(api_client: requests.Session, token: str) -> dict:
    respuesta = api_client.get(f"{API_URL}/usuario/perfil", headers=auth_headers(token), timeout=20)
    assert respuesta.status_code == 200
    return respuesta.json()


# Módulo Mayor/Menor: contrato de dados, suma y actualización de saldo
@pytest.mark.parametrize("opcion", ["menor", "mayor"])
def test_mayor_menor_devuelve_dados_suma_y_actualiza_saldo(api_client, opcion):
    creado = crear_usuario_prueba(api_client)
    token = creado["token"]
    saldo_antes = perfil(api_client, token)["saldo"]

    apuesta = 5
    jugar = api_client.post(
        f"{API_URL}/juegos/jugar",
        headers=auth_headers(token),
        json={"nombre_juego": "mayor_menor", "monto_apuesta": apuesta, "opcion_dado": opcion},
        timeout=20,
    )
    assert jugar.status_code == 200

    datos = jugar.json()
    assert isinstance(datos["dados"], list)
    assert len(datos["dados"]) == 2
    assert all(isinstance(dado, int) and 1 <= dado <= 6 for dado in datos["dados"])
    assert datos["suma_dados"] == sum(datos["dados"])

    saldo_despues = perfil(api_client, token)["saldo"]
    if datos["resultado"] == "ganaste":
        assert datos["premio"] == apuesta * 2
        assert saldo_despues == saldo_antes + (apuesta * 2)
    else:
        assert datos["premio"] == 0
        assert saldo_despues == saldo_antes - apuesta


# Módulo 3 en Raya: inicio descuenta apuesta de forma atómica y retorna tablero/turno
def test_tres_en_raya_iniciar_descuenta_y_retorna_tablero_turno(api_client):
    creado = crear_usuario_prueba(api_client)
    token = creado["token"]
    saldo_antes = perfil(api_client, token)["saldo"]

    apuesta = 6
    inicio = api_client.post(
        f"{API_URL}/juegos/tres-en-raya/iniciar",
        headers=auth_headers(token),
        json={"monto_apuesta": apuesta},
        timeout=20,
    )
    assert inicio.status_code == 200

    datos = inicio.json()
    assert isinstance(datos["id_partida"], str)
    assert len(datos["tablero"]) == 9
    assert datos["turno"] == "estudiante"
    assert datos["resultado"] == "en_curso"

    saldo_despues = perfil(api_client, token)["saldo"]
    assert saldo_despues == saldo_antes - apuesta
    assert datos["nuevo_saldo"] == saldo_despues


# Módulo 3 en Raya: mover valida casilla ocupada
def test_tres_en_raya_mover_rechaza_casilla_ocupada(api_client):
    creado = crear_usuario_prueba(api_client)
    token = creado["token"]

    inicio = api_client.post(
        f"{API_URL}/juegos/tres-en-raya/iniciar",
        headers=auth_headers(token),
        json={"monto_apuesta": 4},
        timeout=20,
    )
    assert inicio.status_code == 200
    partida = inicio.json()

    posicion_libre = next(i for i, valor in enumerate(partida["tablero"]) if not valor)
    primer_mov = api_client.post(
        f"{API_URL}/juegos/tres-en-raya/mover",
        headers=auth_headers(token),
        json={"id_partida": partida["id_partida"], "posicion": posicion_libre},
        timeout=20,
    )
    assert primer_mov.status_code == 200

    repetido = api_client.post(
        f"{API_URL}/juegos/tres-en-raya/mover",
        headers=auth_headers(token),
        json={"id_partida": partida["id_partida"], "posicion": posicion_libre},
        timeout=20,
    )
    assert repetido.status_code == 400
    assert "ocupada" in repetido.json()["detail"].lower()


# Módulo 3 en Raya: sin saldo no debe iniciar nueva partida
def test_tres_en_raya_iniciar_falla_si_no_hay_saldo_suficiente(api_client):
    creado = crear_usuario_prueba(api_client)
    token = creado["token"]

    preguntas = api_client.get(f"{API_URL}/juegos/preguntas", timeout=20)
    assert preguntas.status_code == 200
    id_pregunta = preguntas.json()[0]["id"]

    # Gasto determinístico hasta agotar saldo (respuesta forzada incorrecta).
    for _ in range(10):
        perdida = api_client.post(
            f"{API_URL}/juegos/jugar",
            headers=auth_headers(token),
            json={"nombre_juego": "trivia", "monto_apuesta": 10, "id_pregunta": id_pregunta, "id_opcion": "forzada_incorrecta"},
            timeout=20,
        )
        assert perdida.status_code == 200
        assert perdida.json()["resultado"] == "perdiste"

    sin_saldo = api_client.post(
        f"{API_URL}/juegos/tres-en-raya/iniciar",
        headers=auth_headers(token),
        json={"monto_apuesta": 2},
        timeout=20,
    )
    assert sin_saldo.status_code == 400
    assert "suficientes" in sin_saldo.json()["detail"].lower()
