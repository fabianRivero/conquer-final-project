# Slice 10.6 - la persona es la unica que puede deber

**Objetivo**: retirar la tercera audiencia (el `codigo` de credencial) y
cerrar la puerta por la que una persona sin cuenta podía tener deuda.

**Rama**: `feat/10-6-sin-codigo`
**Estrategia de entrega**: un PR, `ask-on-risk`
**Test runner**: `pytest` (backend) + `npm run typecheck` + `npm run build` (frontend)

## Specs

### S1 - Sin cuenta, no hay vinculo aceptado

La ruta `POST /api/v1/clientes/` (la del dueno) crea hoy a una persona
con vinculo `aceptado` **sin que tenga cuenta**. Eso permite que una
persona sin cuenta tenga un cargo, y una deuda que no puede rechazar.

**Sin cuenta, no hay vinculo aceptado.** El dueno registra a la persona
y el vinculo queda `pendiente`: ella lo acepta desde su cuenta.

### S2 - La persona propone el pago desde su cuenta

`cuenta/pagos/proponer/` - la misma capacidad que hoy tiene
`cliente/pagos/proponer/`, pero con la sesion de la persona.

**El cuerpo es `{importe, referencia?}`** y **no nombra ningun cargo**:
la propuesta no elige que deuda paga, y el FIFO decide.

### S3 - El `codigo` se retira entero

El modelo `CustomerCodigo`, el `CodigoIntento`, las tres rutas
`cliente/*`, el modulo de autenticacion, el throttle y la superficie
`/app/cliente` se van.

**No queda una cuarta audiencia**: la persona es la unica que puede
deber, y su cuenta es la unica puerta.

## Tasks

- [ ] T1 - **T1** (S1) - Cerrar la puerta: el vinculo nace `pendiente`,
      y `Customer.user` NOT NULL.
- [ ] T2 - **T2** (S2) - `cuenta/pagos/proponer/` - la persona propone.
- [ ] T3 - **T3** (S3) - La migracion: fuera `CustomerCodigo` y
      `CodigoIntento`.
- [ ] T4 - **T4** (S3) - Fuera el backend: `client_auth.py`,
      `client_authentication.py`, `throttle.py`, `EsCliente`, las tres
      rutas `cliente/*` y los serializers del cliente.
- [ ] T5 - **T5** (S3) - Fuera el frontend: `/app/cliente`, `Acceso.tsx`,
      `Estado.tsx`, `ProponerPago.tsx`.
- [ ] T6 - **T6** (S1, S2, S3) - El seed: Ana tiene cuenta y su
      vinculo nace del camino real.

## Log

- **L1** (2026-11-24) - "si un cliente no tiene cuenta, entonces no
  puede tener un fiado en primer lugar. Asi que no tendria que pagar
  ninguna deuda de fialdos porque no puede tener fiados."

- **L2** (2026-11-24) - "Cerrar la puerta: sin cuenta, no hay vinculo
  aceptado" - la decision sobre el hueco que la verificacion encontro.

### Analisis

**El razonamiento del dueno cierra el caso del `codigo`.** El `codigo`
existia para el caso "quien no tiene cuenta": podia leer su estado y
proponer un pago. Pero **sin cuenta no hay fiado**, y sin fiado no hay
deuda que pagar. La cuarta audiencia no tenia un caso que la justificara.

**Y al verificarlo aparecio un hueco que el `codigo` tapaba.** La ruta
`POST /api/v1/clientes/` - la del dueno - crea a la persona con el
vinculo **`aceptado`**, sin exigir cuenta. Por esa via, una persona sin
cuenta puede tener un cargo. El `seed_demo` hace justo eso con "Ana": la
crea sin `user`, le da el vinculo `aceptado`, le emite una credencial y
le mete un cargo confirmado.

**Ese camino es el que hay que cerrar.** El dueno registra a la
persona y el vinculo nace `pendiente`; ella lo acepta desde su cuenta.
La persona sin cuenta deja de existir como deuda.

**Lo que NO cambia**: el libro. `LedgerEntry`, `CargoLinea` y
`Confirmacion` no se tocan, y el `cargo` sigue naciendo en la
confirmacion.
