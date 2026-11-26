# Memoria — `fiado confirmado`: el fiado que ratifica la clienta

> **Estado:** para el equipo docente. **Base del conocimiento:** hipótesis de diseño
> declarada sobre el contexto del `fiado`; **sin evidencia de campo**, y sin ronda de
> validación prevista (cerrada por el propietario el 2026-11-25).
> **Anexo de validación:** `evidence-annex.md` — el instrumento previsto, ejecutado o no,
> **sin datos inventados**.

Esta memoria es el documento de entrega. El diseño completo está en `design.md`, la
propuesta y el alcance en `proposal.md`, y el registro de lo que está decidido y lo que
queda en `state.yaml`.

## 1. El problema

El `fiado` —lo que la clienta se lleva y paga después— vive en la cabeza del dueño y en
un cuaderno. El problema de hoy no es solo que el dueño no sepa cuánto le deben: es que
**nadie sabe si la deuda es real**. Un cuaderno no tiene antigüedad, ni límite, ni
regla, y muere con el dueño. Un Excel puede enumerar saldos, pero no puede *decidir*:
no sabe si a esta clienta hay que fiarle más.

El producto convierte el `fiado` en un registro con reglas:

1. **La tienda pregunta.** Prepara una figura con su desglose.
2. **La clienta contesta**, y contesta **desde su propia cuenta**: acepta o rechaza.
3. **El cargo existe solo después de que ella acepta.** Antes de eso no hay deuda.

Todo lo demás se deriva de ahí: el saldo, la antigüedad, la suspensión, la posición real
de la tienda.

## 2. Las personas y el alcance

| Principal | Qué es | Qué puede |
|---|---|---|
| `dueño` | usuario del personal, miembro de una tienda | todo: clientes, política de crédito, libro, cierre del día, propuestas, pagos |
| `dependiente` | usuario del personal, miembro de una tienda | la `caja`, el cierre, y —desde que la puerta N5 se abrió— el libro de crédito con **esquema reducido**, y las propuestas **que él mismo preparó** |
| la **persona** | **no es un rol**: tiene su propia cuenta | sus vínculos, sus cargos, sus `fiado`s y **su propia respuesta** |

**No hay credencial y no hay tercera audiencia.** Una clienta sin cuenta no puede tener
un `fiado`; y sin `fiado` no hay deuda que pagar. Esa regla es la que justifica todo lo
demás: la persona es dueña de su cuenta y de sus credenciales, y puede deber en
**varias** tiendas a la vez.

**Ocho capacidades**, siete más una condicional, y una sola es condicional: la que
facilita la confirmación en el mostrador. Las ocho son las secciones 3.1 a 3.8 de esta
memoria.

## 3. El diseño

### 3.1 Cuentas, roles y credenciales — la persona tiene su propia cuenta

**El rol vive en la membresía, no en un grupo.** Un `MiembroDeTienda` nombra el
negocio, y el negocio nombra la tienda: los permisos se filtran por **la persona y la
tienda**. Un grupo global no podría decirlo — un grupo no dice a qué tienda pertenece
alguien (`CAC-01`).

**El libro de crédito es del dueño entre el personal.** El `dependiente` lo recibe con
`403` y **sin nada de datos parcial**: ni alias, ni identificador, ni cuenta, ni
recuento (`CAC-02`).

**La credencial se retiró.** Existió una credencial portadora (`codigo`) por la que la
clienta leía su extracto. Se retiró en la reescritura de cuentas: **una clienta sin
cuenta no puede tener un `fiado`**, y la credencial era el modo de tener una cuenta sin
ser nadie (`CAC-09`, histórico).

**La cuenta de la persona es suya.** Se registra con su `username` y su contraseña, y
tiene un perfil de clienta que es lo que dice que compra a crédito. La ficha del dueño
y la fila de la persona son **la misma persona**: el `alias` es lo que las une, y el
dueño llama a la gente por su alias, que no es un `username` (`CAC-03`, `CAC-05`).

**La superficie de la clienta no es una sesión de personal.** Ningún ámbito de clienta
puede existir dentro de una sesión de personal, y al revés. La persona entra por
`/api/v1/cuenta/login/` y su sesión **no lleva `shop_id`**: esa ausencia es lo que la
mantiene lejos de las rutas del personal (`CAC-04`).

**Lo demás que cierra esta capacidad:** las vistas consumen la API propia en la URL
pública (`CAC-06`); la producción está bloqueada y no hay secretos en el repositorio
(`CAC-07`); hay una cuenta por rol sembrada (`CAC-08`); y **el payload de la clienta
no lleva nada que no sea suyo** (`CAC-10`).

### 3.2 Catálogo de productos y precios

El catálogo solo guarda lo **apto para fiado** (`PC-01`): un producto que la tienda no
vende a crédito no tiene por qué estar aquí.

**El `precio` es un precio por defecto, no una restricción** (`PC-02`): la línea del
cargo **congela** el precio del momento en que se preparó, así que cambiar el catálogo
después no reescribe una línea ya guardada (`IC-08`). Es una instantánea, y por eso la
línea guardada y el catálogo vigente pueden discrepar sin que nada esté mal.

El catálogo se lee y viene sembrado (`PC-03`).

### 3.3 Cargos con líneas de producto

**El libro es append-only** (`IC-01`): ni `UPDATE` ni `DELETE` sobre `LedgerEntry`,
`CargoLinea`, `Confirmacion`, `PropuestaLinea` ni `ImputacionPago`. Las correcciones,
si las hay, son **filas nuevas**.

**El desglose es obligatorio** (`IC-02`, `IC-07`): el importe de un `cargo` es
exactamente la suma de sus `CargoLinea`, comprobado **en el servidor, dentro de la
transacción de escritura**. Un cargo sin líneas no se puede escribir.

**Un cargo existe solo después de que la clienta confirme** (`IC-03`, `CC-01`): antes de
su respuesta hay una `FiadoPropuesto`, que no es deuda.

**El estado de confirmación efectivo se deriva** (`IC-04`): no hay columna que diga si
un cargo está confirmado. Se deriva de si tiene `Confirmacion`.

La API de escritura del cargo se valida (`IC-05`), las reglas son **funciones puras sin
ORM** (`IC-06`, `PA-11`, `CP-06`), y las líneas de un cargo son inmutables con él
(`IC-09`).

### 3.4 Pagos, antigüedad y suspensión

**El saldo se deriva, nunca se guarda** (`PA-01`): el `outstanding` se calcula sobre las
líneas del libro cada vez que se pregunta.

**Los pagos se imputan FIFO** (`PA-02`): un pago de 20 € salda primero el cargo más
antiguo. Y **un `pago` nunca excede la deuda que salda** (`ADR-26`): el exceso lo
devuelve el dueño como cambio y **no entra en el libro**. Por eso **un cliente nunca
tiene crédito a favor** — no existe ese estado.

**La antigüedad se deriva por cargo** (`PA-03`): los tramos (`vigente`, `envejecido`,
`viejo`, `cronico`) se calculan con la fecha de cada cargo, y la edad de una deuda
pagada deja de envejecer porque el pago la salda.

**El límite es un estado explícito** (`PA-05`): `NULL` significa «sin límite», y es un
límite que el dueño puede poner. **El límite vive en el vínculo, no en la persona**
(`ADR-27`): es la confianza del dueño **en esa tienda**, y una persona puede tener 100
en una y 30 en otra.

**La suspensión es automática y se evalúa en la lectura** (`PA-06`): una clienta está
suspendida cuando el saldo supera el límite o cuando su deuda más vieja pasa los 30
días. **Una clienta suspendida no puede recibir un cargo nuevo** (`PA-07`), y la
suspensión se lee **dentro de la transacción**: una clienta suspendida un momento
antes lo está ahora.

**El dueño puede levantar una suspensión** (`PA-08`): la ruta
`POST /api/v1/clientes/{cliente_id}/suspension/anular/` **graba el acto**, y el acto
es lo que la levanta — el estado derivado no se escribe nunca. **El libro no se toca**
al levantarla.

**El pago lo registra el dueño** (`PA-09`), y la API de escritura del libro se valida
(`PA-10`).

### 3.5 La propuesta, la pantalla de la tienda y la confirmación

**La propuesta es una figura preparada, no una deuda** (`CC-01`): el libro no cambia
mientras la figura está sobre la mesa.

**La pantalla de la tienda muestra el desglose y sus dos acciones** (`CC-03`):
**Confirmar** y **Cancelar**. La pantalla se construye con un esquema **propio**, que
declara exactamente `total` y `lineas[]`: un campo que no está declarado **no puede
aparecer**, diga lo que diga la consulta.

**La clienta ve sus cargos confirmados, desglosados** (`CC-02`, `CC-06`): lo que ya
pagó de cada uno y lo que le queda.

**La clienta puede cancelar una propuesta** (`CC-04`): lo hace **desde su cuenta**, y
su motivo queda escrito.

**La vista de la clienta consume la API propia** (`CC-05`), y **la clienta puede
proponer un pago** (`CC-07`): es una *petición*, no un escritura — no crea ninguna
fila del libro.

### 3.6 La propuesta de pago de la clienta y el pago que registra el dueño

Un `PagoPropuesto` es la **petición** de la clienta: un `importe`, una `referencia` y
un estado. **No escribe en el libro** — el libro es append-only y la clienta no escribe
en él. El dueño lo **valida** y es el dueño quien registra el `pago` de verdad
(`PA-09`).

**El grano de la imputación es el cargo** (`ADR-27`): una fila de `ImputacionPago` por
cada par (pago, cargo) que el pago toca, y la suma de las imputaciones de un pago
**tiene que ser** su importe (`ADR-27`, regla 21).

**El estado del pago propuesto se deriva y se valida en el servidor**: un pago
propuesto que no cuadra, o que se valida sin estar `pendiente`, se rechaza con un
código fijo.

### 3.7 Posición real, cierre del día y existencias

**La posición real es `caja + fiado pendiente`** (`CP-03`): una suma sobre asientos
inmutables. **Un pago no altera la `posicion_real`** — sube la `caja` y baja el fiado
pendiente, y la suma queda igual. Lo que se mueve es la **composición**: la `caja` es
la caja y el fiado pendiente son las deudas.

**La `caja` son los movimientos registrados** (`CP-01`, `CP-02`), y cada movimiento lleva
**su autor** (`CP-01`): una `caja` sin autor es un número sin Explanation.

**El cierre del día es el ancla de la `caja`** (`CP-04`): guarda el `esperado` —la
`caja` calculada por el servidor en el momento del cierre—, el `contado` y la
`desviación`. Y **el cierre está disponible para los dos roles** (`CP-05`).

**Las existencias registradas son un techo, nunca un conteo** (`CP-07`): la cifra no es
"cuánto hay", sino "cuánto se puede prometer", y por eso es un **techo** y no un
inventario. **Esta capacidad está CORTADA** — mira §7.

### 3.8 Condicional — facilitar la confirmación por el `dependiente`

La puerta N5 está **abierta** (`CF-01`): el `dependiente` prepara una propuesta y
registra su confirmación. **El límite es la propiedad**: confirma **solo** las
propuestas que él preparó, y la de otro es un **404**, no un 403 — un 403 confirmaría
que existe.

**El facilitador queda registrado y no tiene ámbito de clienta** (`CF-02`): su origen
lo infiere el servidor de la sesión que actúa, nunca del cuerpo de la petición.

**Lo que la puerta NO abrió:** la política del dueño — el `credit_limit`, la
antigüedad, la suspensión — sigue siendo suya.

## 4. El enfoque técnico

Una sola aplicación, una sola base de datos, un solo origen: **sin segundo host, sin
CORS, sin worker, sin Redis**.

- **Backend** — Django 5.2 + Django REST Framework.
- **Frontend** — React 18 + TypeScript + Vite, servido por WhiteNoise **desde el mismo
  origen** que la API. La vista consume la API propia en la URL pública.
- **Base de datos** — PostgreSQL 16. En producción, Neon (el PostgreSQL gratis de Render
  caduca a los 30 días).
- **Despliegue** — un servicio web de Render que sirve las páginas y la API, con el
  build installs, compila el bundle, migra y **siembra el demo**.

**El libro es append-only y las reglas son funciones puras.** Las reglas viven en
`backend/tienda/domain/`, sin ORM y sin HTTP, y se prueban **sin base de datos**: las
pruebas de `tests/unit/` no pueden tocar la base, y el propio `pytest-django` lo
impone. La capa de servicio traduce y el dominio decide.

**El dato derivado no se guarda.** Ni saldo, ni antigüedad, ni tramos, ni estado de
confirmación, ni **crédito a favor**. Cada uno de esos números es una pregunta que se
responde leyendo las filas.

## 5. La validación — el anexo previsto, ejecutado o no

**La ronda de validación con dueños de tienda NO se va a realizar**: el propietario la
cerró el 2026-11-25 por no considerarla necesaria. El anexo
(`evidence-annex.md`) se conserva **como el registro del método que estaba disponible**:
el guion de las seis preguntas originales más **N1–N7**, la hoja de captura y la lista
de comprobación, con sus **70 campos en `PENDIENTE`** y **sin ninguna cita, cifra ni
entrevista inventada**.

**Lo que eso deja sin medir, y se dice aquí y no se disimula:** la regla de que **sin
cuenta no hay `fiado`** no está contrastada contra tiendas reales. Si una tienda da
crédito a clientes sin cuenta, esa regla les rompe el día — y con la ronda cerrada,
**nada lo va a decir nunca**. Se registra; no se discute: la decisión es del propietario
y se sostiene.

**Lo que sí está comprobado:** **572 pruebas** —128 unitarias sin base de datos y 444
de integración contra PostgreSQL 16— más 11 *end-to-end* contra la URL pública
desplegada. Y hay tests que **fijan el documento al código**: la tabla de rutas del
§9.1 contra el mapa de la API, y la tabla de entidades del §2 contra los modelos, en
las dos direcciones y con el recuento.

## 6. Los criterios de éxito y las demostraciones en vivo

1. URL pública HTTPS con `DEBUG=False`, datos sembrados y una cuenta por rol.
2. En `/app/posicion`: la ecuación del negocio, la escalera con el estado de
   confirmación de cada cargo, el cierre del día, las propuestas pendientes y los pagos
   propuestos.
3. En `/app/propuesta/{id}`: el `desglose` de la propuesta y sus dos acciones,
   **Confirmar** y **Cancelar**.
4. En `/app/cuenta`: la persona entra con su propia cuenta, ve sus vínculos —y en cada
   uno, su propio límite y su propia antigüedad— y sus cargos **confirmados**
   desglosados, lo que ya pagó de cada uno y lo que le queda, y puede **proponer un
   pago**, sin ninguna acción de escribir sobre el libro.
5. **Cuatro demostraciones en vivo**:
   1. un `cargo` de dos líneas cuyo `desglose` y suma cuadran, y cuyo `precio_unitario`
      es **el del momento**: la línea conserva el precio que tenía entonces,
      aunque el catálogo ya sea otro;
   2. un `dependiente` recibe **403** en la **política** del dueño y **200** en
      `/api/v1/clientes/`, donde lee el libro con el esquema **reducido**;
   3. el dueño prepara una propuesta y **la persona la acepta desde su propia cuenta**,
      y el `cargo` queda escrito con su `Confirmacion` y sus líneas **en la misma
      transacción**;
   4. una clienta que debe 8,00 €, 7,00 € y 15,00 € paga 20,00 €, y sus tres cargos
      quedan en **8/8, 7/7 y 5/15**.

El guion de la defensa, con los pasos exactos de cada demostración, está en
`defensa.md`.

## 7. Lo que no está construido, y por qué

| Lo que no está | Por qué |
|---|---|
| **La ronda de validación con dueños de tienda** | Cerrada por el propietario el 2026-11-25. El anexo queda como el registro del método que estaba disponible |
| **El techo de existencias** (`CP-07`, Regla 6) | **Cortado por el propietario** el 2026-11-26: es un techo opcional y ninguna regla depende de él. La regla **sigue en el dominio** con sus pruebas, documentada como el método que estaba disponible; la tabla de `StockMovement` se queda vacía y no la escribe nadie |
| **La credencial `codigo`** (`CAC-09`) | Retirada en la reescritura de cuentas: una clienta sin cuenta no puede tener un `fiado` |

**Y una deuda que se declara:** las tablas del §2 del diseño describían el modelo
anterior. Se corrigieron, y ahora hay un test que impide que vuelvan a derivar.

**Lo que queda abierto, y de quién es:** la pregunta de si la persona debe ver su
propio `credit_limit` la decidió el propietario — **sí**, y su propio límite y su propia
antigüedad, por tienda. Lo que queda por delante es trabajo, no decisiones: la
**entrega** (README, esta memoria y el guion) y ninguna ruta pendiente.
