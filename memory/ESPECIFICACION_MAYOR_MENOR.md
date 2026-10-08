# Especificación — Mayor o Menor

## Mecánica
- El estudiante apuesta entre 2 y 10 Garras y elige `menor` (suma 2–6) o `mayor` (suma 8–12).
- El 7 es `Suerte de la Casa / Aplazado` y siempre pierde la apuesta.
- La apuesta ganadora paga x2; una pérdida descuenta el total apostado.

## Flujo condicional del backend
```text
IF opcion_dado no es menor ni mayor:
    devolver 422
IF saldo_usuario < monto_apuesta:
    devolver 400
win = random() < 0.35
IF win:
    IF opcion_dado == menor:
        dados = combinación aleatoria cuya suma está entre 2 y 6
    ELSE:
        dados = combinación aleatoria cuya suma está entre 8 y 12
    resultado = ganaste
    cambio_saldo = monto_apuesta * 2
ELSE:
    IF random() < 0.75:
        dados = combinación aleatoria del rango contrario a la elección
    ELSE:
        dados = combinación aleatoria cuya suma es 7
    resultado = perdiste
    cambio_saldo = -monto_apuesta
actualizar usuario de forma atómica con filtro saldo >= monto_apuesta y $inc cambio_saldo
registrar transacción y devolver dados, suma, resultado y nuevo saldo
```

La tasa de éxito está estrictamente limitada a 35% por el rollo inicial, independientemente de la distribución física de los dados.

## Esquema de transacción
```json
{
  "id": "UUID",
  "id_usuario": "UUID",
  "monto": 10,
  "descripcion": "Mayor o Menor: ¡Tu elección fue correcta!",
  "fecha": "ISO-8601 UTC"
}
```

La actualización usa `find_one_and_update` con `saldo >= apuesta`, `$inc` y proyección sin `_id`; así evita saldos negativos y condiciones de carrera.
