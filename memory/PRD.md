# PRD — Nuestra Visión / Eduardo Rivero Rector

## Problema original
Crear una PWA móvil completa para la campaña universitaria de Ing. Eduardo Rivero Zurita como Rector USFX 2026–2030. Debe utilizar React, FastAPI y MongoDB, autenticación JWT segura, billetera de monedas con operaciones atómicas, juegos de Ruleta de El Oso y Trivia Express #NuestraVisión, premios canjeables y administración mediante cuenta con correo y contraseña. La interfaz debe emplear azul institucional, destacar Matrícula Cero, Universidad libre para todos, #NuestraVisión y la identidad de El Oso. Todos los endpoints y el código funcional se entregan en español.

## Personas usuarias
- Estudiantes USFX: crean su cuenta, reciben 100 Monedas del Oso, consultan propuestas, juegan y canjean premios.
- Equipo de campaña: inicia sesión con rol administrador y publica nuevos premios.

## Decisiones de arquitectura
- Frontend React mobile-first con rutas protegidas, contexto de sesión y token JWT en localStorage.
- Backend FastAPI con endpoints en español, PyJWT, bcrypt/passlib, OAuth2 Bearer y Pydantic.
- MongoDB usa documentos con id UUID público y excluye el identificador interno de las respuestas.
- Los juegos y canjes usan actualizaciones atómicas con filtros de saldo y existencias para evitar saldos negativos y condiciones de carrera.
- La cuenta administradora inicial se crea solo desde variables de entorno al arrancar, sin endpoint público de elevación de privilegios.

## Requisitos estáticos
- Registro con bono +100, inicio de sesión, perfil y cierre de sesión.
- Ruleta 50/50 por colores con x2 o pérdida de apuesta.
- Trivia de campaña de 10 segundos con x1.5 o pérdida de apuesta.
- Catálogo vacío inicialmente, creación de premios por administrador y canje autenticado.
- PWA instalable, navegación inferior y elementos relevantes con data-testid.

## Implementado — 2026-10-05
- Autenticación JWT real, contraseñas cifradas bcrypt y perfiles protegidos.
- Billetera, bitácora de transacciones y lógica atómica de juego/canje.
- Pantallas de acceso, inicio, propuestas, juegos, premios, perfil y administración.
- Ruleta animada y Trivia con carga fiable de preguntas y contador.
- Diseño institucional móvil con El Oso, Matrícula Cero, Universidad libre para todos y #NuestraVisión.
- Manifest y service worker para instalación PWA.
- Cuenta administradora inicial configurada por entorno; catálogo verificado vacío.

## Backlog priorizado
### P0
- Ninguno para el alcance inicial.
### P1
- Edición y desactivación de premios desde administración.
- Historial de movimientos visible para estudiantes.
- Gestión de puntos físicos de canje y estados de entrega.
### P2
- Más juegos universitarios, clasificaciones y desafíos semanales.
- Notificaciones push y panel de métricas de participación.

## Próximas tareas
1. Cargar los primeros premios oficiales desde la cuenta gestora.
2. Definir los puntos y horarios físicos de recojo.
3. Incorporar los próximos juegos solicitados y sus preguntas o contenido de campaña.


## Ampliación de juegos — 2026-10-05
- Caja de Sorpresas USFX: tres cofres, una probabilidad de premio de 1 entre 3 y pago x2.2.
- Tragamonedas #NuestraVisión: 30% de coincidencia de tres símbolos y pago x3.
- Trivia Flash: desafío con cuatro opciones, cinco segundos visibles y validación del desafío en servidor; premio x1.5 por respuesta correcta a tiempo.
- Las cinco dinámicas comparten una apuesta limitada a 2–10 Monedas del Oso.
- Se corrigió la interacción móvil de cofres y la respuesta Flash mediante panel de pregunta accesible.


## Aplicación del manual de marca Rivero Rector — 2026-10-05
- Se aplicó la paleta institucional: azul #002954, verde #57CC02 y azul secundario #0460C3.
- Se adaptó el encabezado a Rivero Rector y el lema Una Universidad Libre y Para Todos.
- La fotografía oficial de la Universidad se emplea en la portada y el hero principal.
- La garra verde se convirtió en identificador visual de saldo y elementos clave, en lugar del símbolo de monedas.
- Se añadieron acentos de garra y contraste azul-verde siguiendo el manual de marca.


## Rasca y Gana e identidad visual ampliada — 2026-10-06
- Se integraron en la misma experiencia web el banner oficial, el logotipo Rivero Rector y la imagen oficial de garra.
- El saldo, premios, apuestas y resultados ahora se presentan como Garras de la Visión.
- La ruleta ofrece Azul o Verde; Trivia Flash tiene diez segundos; Tragamonedas tiene animación de tómbolas.
- Se implementó Rasca y Gana con tablero 3x3, probabilidad de triunfo del 32 por ciento y premio x2.
- Verificación final: 12 de 12 pruebas de backend y flujos móviles completos aprobados.


## Refinamiento visual de banner y juegos — 2026-10-06
- La garra oficial ahora se presenta visualmente sin fondo negro mediante máscara de imagen.
- El banner Participa y Gana ocupa por completo su tarjeta responsiva, sin texto HTML ni cápsula detrás de la flecha.
- Se reforzaron las animaciones de ruleta, cofres, Rasca y Gana y tómbolas.
- Caja de Sorpresas conserva la selección del cofre y abre el resultado correctamente.
- Validación final de interfaz aprobada para banner, cofres, navegación y tómbolas.


## Banner de comunidad simplificado — 2026-10-06
- El banner Activa tu comunidad ahora muestra solamente la imagen oficial clicable.
- Se fijó una proporción responsiva 16:9, imagen ajustada a 100 por ciento y bordes redondeados.
- Se eliminaron los elementos superpuestos, incluyendo flecha, texto y cualquier cápsula u óvalo.
- La imagen no excede su contenedor y conserva la navegación directa hacia Juegos.


## Arquitectura modular y plan de trabajo — 2026-10-06
- Se separaron Inicio, Propuestas, Juegos, Premios, Perfil y Administración en archivos de página independientes.
- Se añadieron componentes compartidos para marco de navegación, marca, modal y contexto de sesión.
- El plan de trabajo completo fue incorporado en Propuestas: mensaje, formación profesional y seis pilares.
- Campus, banner, logotipo y garra PNG se copiaron a frontend/src/assets; no quedan dependencias externas para estos recursos.
- La navegación modular y los assets locales fueron validados en la experiencia web.


## Juegos de estrategia, dados y premios con imagen — 2026-10-06
- Administración permite cargar PNG/JPEG/WEBP, convertir a base64 en cliente y guardar `imagen_base64` en MongoDB.
- Catálogo de premios prioriza la imagen base64 almacenada.
- Trivia Flash muestra 10 segundos y multiplicador x1.5 Garras.
- Se añadieron 3 en Raya del Rector (inicio IA 70%, modo favorable máximo 33%, empate casa) y Mayor o Menor (éxito máximo 35%, pago x2).
- La especificación condicional y esquema de transacciones está en `memory/ESPECIFICACION_MAYOR_MENOR.md`.


## Entrega presencial de premios — 2026-10-06
- El perfil administrador incluye la opción Entregar premios.
- La pantalla busca estudiantes por correo, muestra saldo y permite seleccionar un premio con existencias.
- La entrega descuenta Garras del estudiante, reduce stock y registra una transacción de entrega presencial.
- Permisos de estudiante, consulta administrativa y errores de stock/saldo fueron validados.


## Identidad estudiantil para registro y entregas — 2026-10-07
- El registro requiere nombre completo y CU universitario único, además de correo y contraseña.
- Nombre y CU se limpian y validan para impedir registros vacíos por espacios.
- La entrega administrativa busca estudiantes por correo, nombre completo o CU.
- Los resultados muestran nombre, correo, CU y Garras disponibles para una entrega segura.
- Se validaron registro, unicidad de CU, inicio de sesión y permisos administrativos.


## Facultades, usuarios y puntos de canje — 2026-10-07
- Se almacenaron 16 facultades oficiales en MongoDB y el registro exige seleccionar una.
- El perfil administrador muestra el total de usuarios registrados y abre una lista con nombre, facultad, CU y Garras.
- Se creó la gestión de puntos de canje por facultad: dirección, teléfono y responsable.
- Las rutas administrativas directas esperan la hidratación de sesión, evitando redirecciones prematuras.
- Se validaron selector de facultades, permisos, lista de usuarios y acceso directo a puntos de canje.


## Consulta estudiantil de puntos de canje — 2026-10-07
- Premios muestra primero los puntos de canje asociados a la facultad del estudiante.
- El enlace Ver más puntos de canje abre el listado general de sedes disponibles.
- Se añadieron endpoints público general y autenticado filtrado por facultad.
- La lista pública tiene estados de carga, reintento y error para evitar vacíos transitorios.
- Se validaron filtrado por facultad, listado completo, navegación y protección de rutas.


## Ajuste del selector de facultad — 2026-10-07
- El selector de facultad del registro ocupa una línea completa debajo de su etiqueta.
- Se igualaron ancho y altura a los campos de nombre completo y CU.
- La validación visual confirmó 470x42 para los tres controles y las 16 facultades disponibles.
