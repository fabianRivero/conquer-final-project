# Slice 10.5 - el mostrador y el fiado

**Objetivo**: el mostrador identifica a la persona por su nombre de usuario,
el dueño prepara el fiado, y **ella lo acepta o lo rechaza desde su cuenta**.

**Rama**: `feat/10-5-mostrador-y-fiado`
**Estrategia de entrega**: un PR, `ask-on-risk`
**Test runner**: `pytest` (backend) + `npm run typecheck` + `npm run build` (frontend)

## Specs

### S1 - El mostrador identifica por nombre de usuario

La persona se identifica en el mostrador con su **nombre de usuario**, no
con un codigo. El que atiende le pide el nombre de usuario y lo teclea; el
sistema lo identifica. La persona **teclea su propia contrasena** - el
dueño no debe ver lo que teclea, y esa es una **suposicion de proceso**,
no una garantia tecnica.

La tienda **pregunta**; la persona **responde desde su cuenta**.

### S2 - La persona acepta o rechaza el fiado

El dueno prepara un `FiadoPropuesto`. La persona lo **acepta** o lo
**rechaza** **desde su cuenta**, no desde el mostrador.

**El motivo del rechazo es texto libre** y puede quedar vacio.

La aceptacion escribe el `cargo`; el rechazo deja la propuesta cancelada
y **el saldo no se movio nunca**, porque no se movio al preparar.

### S3 - La cuenta personal de la persona

Su cuenta lleva **los montos**, la **antiguedad** y los **fiados con su
estado** - incluido `parcial`, el pago que retiene parte de un cargo.

### S4 - Los estados del fiado

`pendiente` - el dueno lo preparo y ella no ha respondido.
`aceptado` - ella dijo si, y el cargo existe.
`rechazado` - ella dijo no, con un motivo libre.

## Tasks

- [ ] T1 - **T1** (S4, S2) - Los estados del `FiadoPropuesto`: `aceptado` y
      `rechazado` con su motivo, y el `parcial` del cargo. Modelo + migracion.
- [ ] T2 - **T2** (S2) - La persona acepta y rechaza: servicios, rutas
      `cuenta/fiados/*`, y la escritura del cargo.
- [ ] T3 - **T3** (S3) - La cuenta personal: los montos, la antiguedad y los
      fiados con su estado.
- [ ] T4 - **T4** (S1) - El mostrador identifica por nombre de usuario: la
      busqueda del personal en el mostrador, y la pantalla.
- [ ] T5 - **T5** (S1, S2, S3) - El frontend: la cuenta con los fiados y el
      mostrador con la identificacion.

## Log

- **L1** (2026-11-24) - "continua con el slice 10.5"

### Analisis

El 10.5 tiene tres piezas y una de ellas es una **correccion de contrato**:

1. **El mostrador identifica por nombre de usuario** (S1). Hoy el mostrador
   usa el `codigo` de credencial (`CustomerCodigo`, prefijo de 6 simbolos),
   que es un credencial **bearer** que el mostrador posee. Con la cuenta de
   la persona, el mostrador teclea el **nombre de usuario** y la persona
   teclea su **contrasena**.

2. **La persona decide el fiado** (S2). Hoy el `design.md` dice, en la fila
   288 de la matriz: *"Confirm or cancel a proposal - No - she identifies;
   the shop decides"*, y en la linea 258: *"The client's portal has no
   confirmation action"*. **El 10.5 cambia esa fila.** La persona acepta o
   rechaza desde su cuenta, con un motivo libre.

3. **La cuenta personal con los montos** (S3). Hoy `Vinculos` muestra los
   vinculos y el limite; no muestra los montos, la antiguedad ni los
   fiados con su estado.

**El estado `parcial`**: el `Cargo` ya sabe cuanto se le pago
(`pagado_de` / `saldo_de`, derivado de `ImputacionPago`). Lo que falta es
que el **estado** del cargo sea una palabra - `pendiente`, `parcial`,
`pagado` - y que ese estado aparezca en la cuenta de la persona.

**El motivo del rechazo**: texto libre, puede quedar vacio. Lo escribe
ella, lo lee el dueno.
