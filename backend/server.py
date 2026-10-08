"""API de la campaña Eduardo Rivero Rector — todos los contratos públicos están en español."""
import os
import random
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional

import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field, field_validator
from pymongo import ReturnDocument, UpdateOne
from starlette.middleware.cors import CORSMiddleware

RAIZ = Path(__file__).parent
load_dotenv(RAIZ / ".env")

URL_MONGO = os.environ["MONGO_URL"]
NOMBRE_BD = os.environ["DB_NAME"]
CLAVE_JWT = os.environ["CLAVE_JWT"]
ALGORITMO_JWT = "HS256"
EXPIRACION_TOKEN_MINUTOS = 60 * 24 * 7

cliente = AsyncIOMotorClient(URL_MONGO)
base_datos = cliente[NOMBRE_BD]
encriptador = CryptContext(schemes=["bcrypt"], deprecated="auto")
esquema_oauth = OAuth2PasswordBearer(tokenUrl="/api/autenticacion/inicio-sesion")

app = FastAPI(title="Nuestra Visión API")
enrutador = APIRouter(prefix="/api")


class RegistroEntrada(BaseModel):
    correo: EmailStr
    contrasena: str = Field(min_length=8, max_length=128)
    nombre_completo: str = Field(min_length=3, max_length=120)
    cu: str = Field(min_length=3, max_length=32)
    facultad_id: str = Field(min_length=1, max_length=80)

    @field_validator("nombre_completo", "cu")
    @classmethod
    def texto_requerido(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("Este campo no puede estar vacío")
        return limpio


class InicioSesionEntrada(BaseModel):
    correo: EmailStr
    contrasena: str = Field(min_length=8, max_length=128)


class UsuarioSalida(BaseModel):
    id: str
    correo: EmailStr
    nombre_completo: Optional[str] = None
    cu: Optional[str] = None
    facultad: Optional[str] = None
    saldo: int
    rol: Literal["estudiante", "administrador"]
    creado_en: str


class RespuestaAutenticacion(BaseModel):
    token: str
    tipo_token: str = "bearer"
    usuario: UsuarioSalida


class JuegoEntrada(BaseModel):
    nombre_juego: Literal["ruleta", "trivia", "caja_sorpresas", "tragamonedas", "trivia_flash", "rasca_gana", "mayor_menor"]
    monto_apuesta: int = Field(ge=2, le=10)
    color: Optional[Literal["azul", "verde"]] = None
    id_pregunta: Optional[str] = None
    id_opcion: Optional[str] = None
    numero_cofre: Optional[int] = Field(default=None, ge=1, le=3)
    id_desafio: Optional[str] = None
    opcion_dado: Optional[Literal["menor", "mayor"]] = None


class InicioTriviaFlashEntrada(BaseModel):
    monto_apuesta: int = Field(ge=2, le=10)


class RespuestaJuego(BaseModel):
    resultado: Literal["ganaste", "perdiste"]
    premio: int
    nuevo_saldo: int
    detalle: str
    color_ganador: Optional[str] = None
    cofre_ganador: Optional[int] = None
    iconos: Optional[list[str]] = None
    tablero_rasca: Optional[list[str]] = None
    dados: Optional[list[int]] = None
    suma_dados: Optional[int] = None


class PreguntaSalida(BaseModel):
    id: str
    enunciado: str
    opciones: list[dict]


class DesafioFlashSalida(PreguntaSalida):
    id_desafio: str


class PremioEntrada(BaseModel):
    titulo: str = Field(min_length=3, max_length=80)
    descripcion: str = Field(min_length=3, max_length=240)
    costo_monedas: int = Field(gt=0)
    existencias: int = Field(ge=0)
    imagen_url: Optional[str] = None
    imagen_base64: Optional[str] = Field(default=None, max_length=3_000_000)


class TresEnRayaInicioEntrada(BaseModel):
    monto_apuesta: int = Field(ge=2, le=10)


class TresEnRayaMoverEntrada(BaseModel):
    id_partida: str
    posicion: int = Field(ge=0, le=8)


class TresEnRayaSalida(BaseModel):
    id_partida: str
    tablero: list[str]
    turno: Literal["estudiante", "rector", "finalizado"]
    resultado: Literal["en_curso", "victoria", "derrota", "empate"]
    nuevo_saldo: Optional[int] = None


class PremioSalida(PremioEntrada):
    id: str


class UsuarioBusquedaSalida(BaseModel):
    id: str
    correo: EmailStr
    nombre_completo: Optional[str] = None
    cu: Optional[str] = None
    facultad: Optional[str] = None
    saldo: int


class EntregaPremioEntrada(BaseModel):
    id_usuario: str
    id_premio: str


class FacultadSalida(BaseModel):
    id: str
    nombre: str


class PuntoCanjeEntrada(BaseModel):
    facultad_id: str
    direccion: str = Field(min_length=5, max_length=180)
    telefono: str = Field(min_length=5, max_length=40)
    responsable: str = Field(min_length=3, max_length=120)


class PuntoCanjeSalida(PuntoCanjeEntrada):
    id: str
    facultad: str


PREGUNTAS = [
    {"id": "matricula-cero", "enunciado": "¿Cuál es la propuesta bandera de Eduardo Rivero?", "opciones": [{"id": "a", "texto": "Matrícula Cero"}, {"id": "b", "texto": "Media matrícula"}], "correcta": "a"},
    {"id": "universidad-libre", "enunciado": "¿Qué principio guía la campaña?", "opciones": [{"id": "a", "texto": "Universidad libre para todos"}, {"id": "b", "texto": "Acceso restringido"}], "correcta": "a"},
    {"id": "vision", "enunciado": "#NuestraVisión conecta a la universidad con…", "opciones": [{"id": "a", "texto": "Innovación científica y nexo productivo"}, {"id": "b", "texto": "Menos investigación"}], "correcta": "a"},
    {"id": "oso", "enunciado": "¿Cuál es el identificador de nuestra mascota digital?", "opciones": [{"id": "a", "texto": "El Oso"}, {"id": "b", "texto": "El Cóndor"}], "correcta": "a"},
    {"id": "periodo", "enunciado": "¿Para qué gestión se postula Eduardo Rivero?", "opciones": [{"id": "a", "texto": "2026–2030"}, {"id": "b", "texto": "2031–2035"}], "correcta": "a"},
]

PREGUNTAS_FLASH = [
    {"id": "sucre", "enunciado": "¿En qué ciudad tiene su sede histórica la Universidad San Francisco Xavier?", "opciones": [{"id": "a", "texto": "Sucre"}, {"id": "b", "texto": "Cochabamba"}, {"id": "c", "texto": "Potosí"}, {"id": "d", "texto": "Tarija"}], "correcta": "a"},
    {"id": "autonomia", "enunciado": "¿Qué principio protege las decisiones académicas de una universidad pública?", "opciones": [{"id": "a", "texto": "Autonomía universitaria"}, {"id": "b", "texto": "Dependencia financiera"}, {"id": "c", "texto": "Rotación obligatoria"}, {"id": "d", "texto": "Centralización externa"}], "correcta": "a"},
    {"id": "investigacion", "enunciado": "¿Cuál es el vínculo que plantea #NuestraVisión para la ciencia universitaria?", "opciones": [{"id": "a", "texto": "Nexo productivo"}, {"id": "b", "texto": "Aislamiento de facultades"}, {"id": "c", "texto": "Reducción de laboratorios"}, {"id": "d", "texto": "Suspensión de proyectos"}], "correcta": "a"},
    {"id": "acceso", "enunciado": "¿Qué propuesta busca remover una barrera económica para el acceso universitario?", "opciones": [{"id": "a", "texto": "Matrícula Cero"}, {"id": "b", "texto": "Pago por materia"}, {"id": "c", "texto": "Aumento de aranceles"}, {"id": "d", "texto": "Cupos con recargo"}], "correcta": "a"},
    {"id": "innovacion", "enunciado": "¿Qué resultado fortalece una universidad conectada con su entorno?", "opciones": [{"id": "a", "texto": "Innovación aplicada"}, {"id": "b", "texto": "Menos investigación"}, {"id": "c", "texto": "Menos colaboración"}, {"id": "d", "texto": "Menos acceso"}], "correcta": "a"},
]

FACULTADES_INICIALES = [
    "Arquitectura y Ciencias del Hábitat", "Ciencias Agrarias", "Ciencias de Enfermería y Obstetricia", "Ciencias Económicas y Empresariales", "Ciencias Químico - Farmacéuticas y Bioquímicas", "Ciencias y Tecnología", "Ciencias y Tecnologías de la Salud", "Contaduría Pública y Ciencias Financieras", "Derecho, Ciencias Políticas y Sociales", "Humanidades y Ciencias de la Educación", "Ingeniería Civil", "Ingeniería y Ciencias Aplicadas Meca - Electrónicas", "Integral Defensores del Chaco (Sede Muyupampa)", "Medicina", "Odontología", "Técnica"
]

LINEAS_TRES_RAYA = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def crear_token(usuario: dict) -> str:
    datos = {"sub": usuario["id"], "rol": usuario["rol"], "exp": datetime.now(timezone.utc) + timedelta(minutes=EXPIRACION_TOKEN_MINUTOS)}
    return jwt.encode(datos, CLAVE_JWT, algorithm=ALGORITMO_JWT)


def salida_usuario(documento: dict) -> UsuarioSalida:
    return UsuarioSalida(id=documento["id"], correo=documento["correo"], nombre_completo=documento.get("nombre_completo"), cu=documento.get("cu"), facultad=documento.get("facultad"), saldo=documento["saldo"], rol=documento["rol"], creado_en=documento["creado_en"])


def hay_ganador(tablero: list[str], ficha: str) -> bool:
    return any(all(tablero[posicion] == ficha for posicion in linea) for linea in LINEAS_TRES_RAYA)


def movimiento_para_ganar(tablero: list[str], ficha: str) -> Optional[int]:
    for posicion, valor in enumerate(tablero):
        if valor:
            continue
        prueba = tablero.copy()
        prueba[posicion] = ficha
        if hay_ganador(prueba, ficha):
            return posicion
    return None


def seleccionar_movimiento_rector(tablero: list[str], modo_casa: bool) -> int:
    libres = [posicion for posicion, valor in enumerate(tablero) if not valor]
    victoria = movimiento_para_ganar(tablero, "O")
    if victoria is not None:
        return victoria
    bloqueo = movimiento_para_ganar(tablero, "X")
    if modo_casa and bloqueo is not None:
        return bloqueo
    if modo_casa and 4 in libres:
        return 4
    esquinas = [posicion for posicion in [0, 2, 6, 8] if posicion in libres]
    return random.choice(esquinas or libres)


async def obtener_usuario_actual(token: str = Depends(esquema_oauth)) -> dict:
    try:
        datos = jwt.decode(token, CLAVE_JWT, algorithms=[ALGORITMO_JWT])
        id_usuario = datos.get("sub")
    except jwt.PyJWTError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o vencido") from error
    usuario = await base_datos.usuarios.find_one({"id": id_usuario}, {"_id": 0})
    if not usuario:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
    return usuario


async def exigir_administrador(usuario: dict = Depends(obtener_usuario_actual)) -> dict:
    if usuario["rol"] != "administrador":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requiere una cuenta administradora")
    return usuario


@enrutador.get("/salud")
async def salud():
    return {"estado": "activo", "campana": "Eduardo Rivero Rector"}


@enrutador.get("/facultades", response_model=list[FacultadSalida])
async def listar_facultades():
    return await base_datos.facultades.find({}, {"_id": 0}).sort("nombre", 1).to_list(50)


@enrutador.post("/autenticacion/registro", response_model=RespuestaAutenticacion, status_code=status.HTTP_201_CREATED)
async def registrar(datos: RegistroEntrada):
    correo = datos.correo.lower()
    cu = datos.cu.strip().upper()
    repetido = await base_datos.usuarios.find_one({"$or": [{"correo": correo}, {"cu": cu}]}, {"_id": 0, "correo": 1, "cu": 1})
    if repetido:
        detalle = "Este CU ya está registrado" if repetido.get("cu") == cu else "Este correo ya está registrado"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detalle)
    facultad = await base_datos.facultades.find_one({"id": datos.facultad_id}, {"_id": 0})
    if not facultad:
        raise HTTPException(status_code=422, detail="Selecciona una facultad válida")
    usuario = {"id": str(uuid.uuid4()), "correo": correo, "nombre_completo": datos.nombre_completo.strip(), "cu": cu, "facultad_id": facultad["id"], "facultad": facultad["nombre"], "contrasena_cifrada": encriptador.hash(datos.contrasena), "saldo": 100, "rol": "estudiante", "creado_en": ahora()}
    await base_datos.usuarios.insert_one(usuario.copy())
    limpio = {clave: valor for clave, valor in usuario.items() if clave != "contrasena_cifrada"}
    await base_datos.transacciones.insert_one({"id": str(uuid.uuid4()), "id_usuario": usuario["id"], "monto": 100, "descripcion": "Bono de bienvenida: +100 Monedas del Oso", "fecha": ahora()})
    return RespuestaAutenticacion(token=crear_token(limpio), usuario=salida_usuario(limpio))


@enrutador.post("/autenticacion/inicio-sesion", response_model=RespuestaAutenticacion)
async def iniciar_sesion(datos: InicioSesionEntrada):
    usuario = await base_datos.usuarios.find_one({"correo": datos.correo.lower()}, {"_id": 0})
    if not usuario or not encriptador.verify(datos.contrasena, usuario["contrasena_cifrada"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Correo o contraseña incorrectos")
    return RespuestaAutenticacion(token=crear_token(usuario), usuario=salida_usuario(usuario))


@enrutador.get("/usuario/perfil", response_model=UsuarioSalida)
async def perfil(usuario: dict = Depends(obtener_usuario_actual)):
    return salida_usuario(usuario)


@enrutador.get("/juegos/preguntas", response_model=list[PreguntaSalida])
async def listar_preguntas():
    return [{"id": pregunta["id"], "enunciado": pregunta["enunciado"], "opciones": pregunta["opciones"]} for pregunta in PREGUNTAS]


@enrutador.post("/juegos/trivia-flash/iniciar", response_model=DesafioFlashSalida)
async def iniciar_trivia_flash(datos: InicioTriviaFlashEntrada, usuario: dict = Depends(obtener_usuario_actual)):
    if usuario["saldo"] < datos.monto_apuesta:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tienes suficientes Monedas del Oso")
    pregunta = random.choice(PREGUNTAS_FLASH)
    id_desafio = str(uuid.uuid4())
    await base_datos.desafios_flash.insert_one({"id": id_desafio, "id_usuario": usuario["id"], "id_pregunta": pregunta["id"], "monto_apuesta": datos.monto_apuesta, "iniciado_en": ahora(), "usado": False})
    return DesafioFlashSalida(id_desafio=id_desafio, id=pregunta["id"], enunciado=pregunta["enunciado"], opciones=pregunta["opciones"])


@enrutador.post("/juegos/tres-en-raya/iniciar", response_model=TresEnRayaSalida)
async def iniciar_tres_en_raya(datos: TresEnRayaInicioEntrada, usuario: dict = Depends(obtener_usuario_actual)):
    usuario_actualizado = await base_datos.usuarios.find_one_and_update({"id": usuario["id"], "saldo": {"$gte": datos.monto_apuesta}}, {"$inc": {"saldo": -datos.monto_apuesta}}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not usuario_actualizado:
        raise HTTPException(status_code=400, detail="No tienes Garras suficientes para iniciar la partida")
    ia_inicia = random.random() < 0.70
    tablero = [""] * 9
    if ia_inicia:
        tablero[4] = "O"
    partida = {"id": str(uuid.uuid4()), "id_usuario": usuario["id"], "tablero": tablero, "monto_apuesta": datos.monto_apuesta, "modo_favorable": random.random() < 0.33, "ia_inicia": ia_inicia, "estado": "en_curso", "creado_en": ahora()}
    await base_datos.partidas_tres_raya.insert_one(partida.copy())
    await base_datos.transacciones.insert_one({"id": str(uuid.uuid4()), "id_usuario": usuario["id"], "monto": -datos.monto_apuesta, "descripcion": "Apuesta: 3 en Raya del Rector", "fecha": ahora()})
    return TresEnRayaSalida(id_partida=partida["id"], tablero=tablero, turno="estudiante", resultado="en_curso", nuevo_saldo=usuario_actualizado["saldo"])


@enrutador.post("/juegos/tres-en-raya/mover", response_model=TresEnRayaSalida)
async def mover_tres_en_raya(datos: TresEnRayaMoverEntrada, usuario: dict = Depends(obtener_usuario_actual)):
    partida = await base_datos.partidas_tres_raya.find_one_and_update({"id": datos.id_partida, "id_usuario": usuario["id"], "estado": "en_curso"}, {"$set": {"actualizado_en": ahora()}}, projection={"_id": 0}, return_document=ReturnDocument.BEFORE)
    if not partida:
        raise HTTPException(status_code=400, detail="La partida no está disponible")
    tablero = partida["tablero"]
    if tablero[datos.posicion]:
        raise HTTPException(status_code=400, detail="Esta casilla ya está ocupada")
    tablero[datos.posicion] = "X"
    if hay_ganador(tablero, "X") and partida["modo_favorable"]:
        saldo = await base_datos.usuarios.find_one_and_update({"id": usuario["id"]}, {"$inc": {"saldo": partida["monto_apuesta"] * 2}}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
        await base_datos.partidas_tres_raya.update_one({"id": partida["id"]}, {"$set": {"tablero": tablero, "estado": "victoria"}})
        await base_datos.transacciones.insert_one({"id": str(uuid.uuid4()), "id_usuario": usuario["id"], "monto": partida["monto_apuesta"] * 2, "descripcion": "Victoria: 3 en Raya del Rector", "fecha": ahora()})
        return TresEnRayaSalida(id_partida=partida["id"], tablero=tablero, turno="finalizado", resultado="victoria", nuevo_saldo=saldo["saldo"])
    if not any(not valor for valor in tablero):
        await base_datos.partidas_tres_raya.update_one({"id": partida["id"]}, {"$set": {"tablero": tablero, "estado": "empate"}})
        return TresEnRayaSalida(id_partida=partida["id"], tablero=tablero, turno="finalizado", resultado="empate")
    movimiento_ia = seleccionar_movimiento_rector(tablero, not partida["modo_favorable"])
    tablero[movimiento_ia] = "O"
    if hay_ganador(tablero, "O"):
        estado = "derrota"
    elif not any(not valor for valor in tablero):
        estado = "empate"
    else:
        estado = "en_curso"
    await base_datos.partidas_tres_raya.update_one({"id": partida["id"]}, {"$set": {"tablero": tablero, "estado": estado}})
    return TresEnRayaSalida(id_partida=partida["id"], tablero=tablero, turno="finalizado" if estado != "en_curso" else "estudiante", resultado=estado)


@enrutador.post("/juegos/jugar", response_model=RespuestaJuego)
async def jugar(datos: JuegoEntrada, usuario: dict = Depends(obtener_usuario_actual)):
    color_ganador = None
    cofre_ganador = None
    iconos = None
    if datos.nombre_juego == "ruleta":
        if not datos.color:
            raise HTTPException(status_code=422, detail="Selecciona azul o verde para la ruleta")
        color_ganador = random.choice(["azul", "verde"])
        gano = datos.color == color_ganador
        detalle = f"La ruleta eligió {color_ganador}."
    elif datos.nombre_juego == "caja_sorpresas":
        if not datos.numero_cofre:
            raise HTTPException(status_code=422, detail="Selecciona uno de los tres cofres")
        cofre_ganador = random.randint(1, 3)
        gano = datos.numero_cofre == cofre_ganador
        detalle = "¡Encontraste monedas extra en el cofre!" if gano else "Clase Cancelada: este cofre estaba vacío."
    elif datos.nombre_juego == "tragamonedas":
        simbolos = ["oso", "escudo", "birrete"]
        gano = random.random() < 0.30
        if gano:
            simbolo = random.choice(simbolos)
            iconos = [simbolo, simbolo, simbolo]
        else:
            iconos = [random.choice(simbolos) for _ in range(3)]
            while len(set(iconos)) == 1:
                iconos = [random.choice(simbolos) for _ in range(3)]
        detalle = "¡Tres símbolos iguales! La visión avanza." if gano else "Los rodillos no coincidieron. Vuelve a intentarlo."
    elif datos.nombre_juego == "rasca_gana":
        simbolos_rasca = ["toga", "libro", "medalla"]
        gano = random.random() < 0.32
        if gano:
            premio_simbolo = random.choice(simbolos_rasca)
            restantes = [simbolo for simbolo in simbolos_rasca if simbolo != premio_simbolo]
            tablero_rasca = [premio_simbolo, premio_simbolo, premio_simbolo, restantes[0], restantes[1], restantes[0], restantes[1], restantes[0], restantes[1]]
        else:
            tablero_rasca = ["toga", "libro", "medalla", "libro", "medalla", "toga", "medalla", "toga", "libro"]
            random.shuffle(tablero_rasca)
        detalle = "¡Tres símbolos iguales! Ganaste en Rasca y Gana." if gano else "Encontraste coincidencias, pero no una línea ganadora."
    elif datos.nombre_juego == "mayor_menor":
        if not datos.opcion_dado:
            raise HTTPException(status_code=422, detail="Selecciona Mayor o Menor antes de lanzar")
        combinaciones_menor = [(a, b) for a in range(1, 7) for b in range(1, 7) if 2 <= a + b <= 6]
        combinaciones_mayor = [(a, b) for a in range(1, 7) for b in range(1, 7) if 8 <= a + b <= 12]
        combinaciones_siete = [(a, b) for a in range(1, 7) for b in range(1, 7) if a + b == 7]
        gano = random.random() < 0.35
        elegidas = combinaciones_menor if datos.opcion_dado == "menor" else combinaciones_mayor
        contrarias = combinaciones_mayor if datos.opcion_dado == "menor" else combinaciones_menor
        dados = random.choice(elegidas if gano else (contrarias if random.random() < 0.75 else combinaciones_siete))
        detalle = "¡Tu elección fue correcta!" if gano else ("Salió 7: Suerte de la Casa / Aplazado." if sum(dados) == 7 else "Esta vez ganó la otra opción.")
    elif datos.nombre_juego == "trivia_flash":
        if not datos.id_desafio or not datos.id_opcion:
            raise HTTPException(status_code=422, detail="Envía el desafío y una respuesta para Trivia Flash")
        desafio = await base_datos.desafios_flash.find_one_and_update({"id": datos.id_desafio, "id_usuario": usuario["id"], "usado": False}, {"$set": {"usado": True, "respondido_en": ahora()}}, projection={"_id": 0}, return_document=ReturnDocument.BEFORE)
        if not desafio:
            raise HTTPException(status_code=400, detail="Este desafío ya fue respondido o no existe")
        pregunta = next((item for item in PREGUNTAS_FLASH if item["id"] == desafio["id_pregunta"]), None)
        segundos = (datetime.now(timezone.utc) - datetime.fromisoformat(desafio["iniciado_en"])).total_seconds()
        # El contador visible cierra a los 10 segundos. Se reserva un segundo técnico para el viaje
        # de la respuesta desde el teléfono al servidor, sin ampliar el tiempo disponible en la UI.
        gano = bool(pregunta) and segundos <= 11 and pregunta["correcta"] == datos.id_opcion
        datos.monto_apuesta = desafio["monto_apuesta"]
        detalle = "¡Respuesta correcta a tiempo!" if gano else ("Se agotaron los 10 segundos." if segundos > 11 else "Respuesta incorrecta.")
    else:
        pregunta = next((item for item in PREGUNTAS if item["id"] == datos.id_pregunta), None)
        if not pregunta or not datos.id_opcion:
            raise HTTPException(status_code=422, detail="Envía una pregunta y una respuesta válidas")
        gano = pregunta["correcta"] == datos.id_opcion
        detalle = "Respuesta correcta: El Oso celebra contigo." if gano else "Esta vez no acertaste. Sigue participando."

    multiplicadores = {"ruleta": 2, "trivia": 1.5, "caja_sorpresas": 2.2, "tragamonedas": 3, "trivia_flash": 1.5, "rasca_gana": 2, "mayor_menor": 2}
    premio = int(datos.monto_apuesta * multiplicadores[datos.nombre_juego]) if gano else 0
    cambio = premio if gano else -datos.monto_apuesta
    filtro = {"id": usuario["id"], "saldo": {"$gte": datos.monto_apuesta}}
    usuario_actualizado = await base_datos.usuarios.find_one_and_update(filtro, {"$inc": {"saldo": cambio}}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not usuario_actualizado:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tienes suficientes Monedas del Oso")
    await base_datos.transacciones.insert_one({"id": str(uuid.uuid4()), "id_usuario": usuario["id"], "monto": cambio, "descripcion": f"{datos.nombre_juego.title()}: {detalle}", "fecha": ahora()})
    return RespuestaJuego(resultado="ganaste" if gano else "perdiste", premio=premio, nuevo_saldo=usuario_actualizado["saldo"], detalle=detalle, color_ganador=color_ganador, cofre_ganador=cofre_ganador, iconos=iconos, tablero_rasca=tablero_rasca if datos.nombre_juego == "rasca_gana" else None, dados=list(dados) if datos.nombre_juego == "mayor_menor" else None, suma_dados=sum(dados) if datos.nombre_juego == "mayor_menor" else None)


@enrutador.get("/premios", response_model=list[PremioSalida])
async def listar_premios():
    return await base_datos.premios.find({}, {"_id": 0}).sort("creado_en", -1).to_list(100)


@enrutador.get("/puntos-canje", response_model=list[PuntoCanjeSalida])
async def listar_puntos_canje_publicos():
    return await base_datos.puntos_canje.find({}, {"_id": 0}).sort("facultad", 1).to_list(200)


@enrutador.get("/puntos-canje/mi-facultad", response_model=list[PuntoCanjeSalida])
async def listar_puntos_mi_facultad(usuario: dict = Depends(obtener_usuario_actual)):
    facultad_id = usuario.get("facultad_id")
    if not facultad_id:
        return []
    return await base_datos.puntos_canje.find({"facultad_id": facultad_id}, {"_id": 0}).sort("creado_en", -1).to_list(50)


@enrutador.post("/administracion/premios", response_model=PremioSalida, status_code=status.HTTP_201_CREATED)
async def crear_premio(datos: PremioEntrada, _: dict = Depends(exigir_administrador)):
    premio = {"id": str(uuid.uuid4()), **datos.model_dump(), "creado_en": ahora()}
    await base_datos.premios.insert_one(premio.copy())
    return PremioSalida(**{clave: valor for clave, valor in premio.items() if clave != "creado_en"})


@enrutador.get("/administracion/usuarios", response_model=list[UsuarioBusquedaSalida])
async def buscar_usuarios(buscar: str, _: dict = Depends(exigir_administrador)):
    termino = buscar.strip()
    if len(termino) < 2:
        return []
    patron = re.escape(termino)
    usuarios = await base_datos.usuarios.find({"rol": "estudiante", "$or": [{"correo": {"$regex": patron, "$options": "i"}}, {"nombre_completo": {"$regex": patron, "$options": "i"}}, {"cu": {"$regex": patron, "$options": "i"}}]}, {"_id": 0, "id": 1, "correo": 1, "nombre_completo": 1, "cu": 1, "facultad": 1, "saldo": 1}).limit(12).to_list(12)
    return usuarios


@enrutador.get("/administracion/usuarios/resumen")
async def resumen_usuarios(_: dict = Depends(exigir_administrador)):
    total = await base_datos.usuarios.count_documents({"rol": "estudiante"})
    return {"total": total}


@enrutador.get("/administracion/usuarios/lista", response_model=list[UsuarioBusquedaSalida])
async def listar_usuarios_administracion(_: dict = Depends(exigir_administrador)):
    return await base_datos.usuarios.find({"rol": "estudiante"}, {"_id": 0, "id": 1, "correo": 1, "nombre_completo": 1, "cu": 1, "facultad": 1, "saldo": 1}).sort("creado_en", -1).to_list(500)


@enrutador.post("/administracion/entregas")
async def entregar_premio(datos: EntregaPremioEntrada, administrador: dict = Depends(exigir_administrador)):
    premio = await base_datos.premios.find_one_and_update({"id": datos.id_premio, "existencias": {"$gt": 0}}, {"$inc": {"existencias": -1}}, projection={"_id": 0}, return_document=ReturnDocument.BEFORE)
    if not premio:
        raise HTTPException(status_code=400, detail="El premio no tiene existencias disponibles")
    usuario = await base_datos.usuarios.find_one_and_update({"id": datos.id_usuario, "rol": "estudiante", "saldo": {"$gte": premio["costo_monedas"]}}, {"$inc": {"saldo": -premio["costo_monedas"]}}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not usuario:
        await base_datos.premios.update_one({"id": datos.id_premio}, {"$inc": {"existencias": 1}})
        raise HTTPException(status_code=400, detail="El estudiante no existe o no tiene Garras suficientes")
    await base_datos.transacciones.insert_one({"id": str(uuid.uuid4()), "id_usuario": datos.id_usuario, "monto": -premio["costo_monedas"], "descripcion": f"Entrega presencial: {premio['titulo']} · gestionado por {administrador['correo']}", "fecha": ahora()})
    return {"mensaje": f"Entrega registrada para {usuario['correo']}", "nuevo_saldo": usuario["saldo"], "premio": premio["titulo"]}


@enrutador.get("/administracion/puntos-canje", response_model=list[PuntoCanjeSalida])
async def listar_puntos_canje(_: dict = Depends(exigir_administrador)):
    return await base_datos.puntos_canje.find({}, {"_id": 0}).sort("facultad", 1).to_list(200)


@enrutador.post("/administracion/puntos-canje", response_model=PuntoCanjeSalida, status_code=status.HTTP_201_CREATED)
async def crear_punto_canje(datos: PuntoCanjeEntrada, _: dict = Depends(exigir_administrador)):
    facultad = await base_datos.facultades.find_one({"id": datos.facultad_id}, {"_id": 0})
    if not facultad:
        raise HTTPException(status_code=422, detail="Selecciona una facultad válida")
    punto = {"id": str(uuid.uuid4()), **datos.model_dump(), "facultad": facultad["nombre"], "creado_en": ahora()}
    await base_datos.puntos_canje.insert_one(punto.copy())
    return PuntoCanjeSalida(**{clave: valor for clave, valor in punto.items() if clave != "creado_en"})


@enrutador.post("/premios/{id_premio}/canjear")
async def canjear_premio(id_premio: str, usuario: dict = Depends(obtener_usuario_actual)):
    premio = await base_datos.premios.find_one_and_update({"id": id_premio, "existencias": {"$gt": 0}}, {"$inc": {"existencias": -1}}, projection={"_id": 0}, return_document=ReturnDocument.BEFORE)
    if not premio:
        raise HTTPException(status_code=400, detail="Este premio ya no tiene existencias")
    usuario_actualizado = await base_datos.usuarios.find_one_and_update({"id": usuario["id"], "saldo": {"$gte": premio["costo_monedas"]}}, {"$inc": {"saldo": -premio["costo_monedas"]}}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not usuario_actualizado:
        await base_datos.premios.update_one({"id": id_premio}, {"$inc": {"existencias": 1}})
        raise HTTPException(status_code=400, detail="No tienes monedas suficientes para este canje")
    await base_datos.transacciones.insert_one({"id": str(uuid.uuid4()), "id_usuario": usuario["id"], "monto": -premio["costo_monedas"], "descripcion": f"Canje: {premio['titulo']}", "fecha": ahora()})
    return {"mensaje": "Canje registrado. Recoge tu premio en los puntos de campaña.", "nuevo_saldo": usuario_actualizado["saldo"]}


app.include_router(enrutador)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","), allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def preparar_administracion_inicial():
    """Crea únicamente la cuenta gestora configurada por entorno, si todavía no existe."""
    correo = os.environ.get("CORREO_ADMIN_INICIAL")
    contrasena = os.environ.get("CONTRASENA_ADMIN_INICIAL")
    if not correo or not contrasena:
        correo = None
    operaciones = [UpdateOne({"id": f"facultad-{indice}"}, {"$setOnInsert": {"id": f"facultad-{indice}", "nombre": nombre}}, upsert=True) for indice, nombre in enumerate(FACULTADES_INICIALES, 1)]
    await base_datos.facultades.bulk_write(operaciones)
    if correo:
        correo = correo.lower()
        if not await base_datos.usuarios.find_one({"correo": correo}, {"_id": 0, "id": 1}):
            administrador = {"id": str(uuid.uuid4()), "correo": correo, "contrasena_cifrada": encriptador.hash(contrasena), "saldo": 0, "rol": "administrador", "creado_en": ahora()}
            await base_datos.usuarios.insert_one(administrador.copy())


@app.on_event("shutdown")
async def cerrar_mongo():
    cliente.close()