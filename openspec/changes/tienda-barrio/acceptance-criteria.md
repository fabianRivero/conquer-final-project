# Anexo — Criterios de aceptación, matriz de permisos y preguntas de defensa

**Change:** `tienda-barrio` · **Variante:** `fiado` — «La libreta y la caja»
**Estado:** anexo de la propuesta `proposal.md`. Documento de apoyo interno; la página que se entrega al equipo docente es `proposal.md`.
**Idioma:** español neutro y profesional. Los términos de dominio (`fiado`, `cargo`, `pago`, `nota de crédito`, `caja`, `dependiente`, `libreta`) se mantienen tal cual.

---

## 1. Criterios de aceptación por funcionalidad

Los criterios se expresan en forma **Dado / Cuando / Entonces** y son la base de la fase de especificaciones. Cada criterio lleva un **identificador estable** (`F<n>-AC<m>`) según su posición dentro de su funcionalidad: **ni los identificadores ni su orden se renumeran**, de modo que este anexo y las especificaciones puedan citarse mutuamente. Cada uno debe poder verificarse con una prueba automática (backend) o con una comprobación manual en la URL pública.

> **Regla de negocio que atraviesa todos los criterios:** la `posicion_real` es **aditiva**: `posicion_real = caja + fiado pendiente` (el dinero que hay en el cajón **más** el dinero que la tienda tiene pendiente de cobrar). Un `pago` de un cliente **sube la `caja`** en su importe y **no altera la `posicion_real`**: el dinero se convierte, no se crea ni se pierde.

### F1 — Cuentas y dos roles

- **F1-AC1.** **Dado** la cuenta sembrada `dependiente@tienda.test` (grupo `dependiente`),
  **cuando** solicita `GET /api/v1/clientes/`,
  **entonces** la respuesta es **403** y el cuerpo no contiene ningún alias ni identificador de cliente.
- **F1-AC2.** **Dado** la misma cuenta,
  **cuando** solicita `GET /api/v1/posicion/`,
  **entonces** la respuesta es 200, `clientes` llega como lista vacía y **ninguna ruta del JSON** (incluidos metadatos de paginación, agregados del cierre y la serie de caja) contiene un alias, un identificador de cliente o un nombre.
- **F1-AC3.** **Dado** la cuenta sembrada `dueno@tienda.test` (grupo `dueno`),
  **cuando** solicita `GET /api/v1/clientes/`,
  **entonces** la respuesta es 200 y devuelve la lista de clientes sembrados.
- **F1-AC4.** **Dado** un usuario no autenticado,
  **cuando** solicita cualquier endpoint de `/api/v1/`,
  **entonces** la respuesta es 401 o 403 y no se devuelve ninguna fila.

### F2 — Libro de clientes y línea de crédito

- **F2-AC1.** **Dado** un cliente con `credit_limit = 20,00 €`,
  **cuando** se intenta registrar un cargo de `25,00 €`,
  **entonces** el servidor responde con **HTTP 422** y un error de validación que **nombra el límite**, y **no se crea ninguna fila** en `LedgerEntry`.
- **F2-AC2.** **Dado** un cliente con `credit_limit = null` (estado explícito «sin límite»),
  **cuando** se registra un cargo,
  **entonces** el cargo se acepta y queda registrado.
- **F2-AC3.** **Dado** un cliente existente,
  **cuando** el dueño cambia su `credit_limit`,
  **entonces** el valor se persiste y **no se modifica** ningún asiento previo del libro.
- **F2-AC4.** **Dado** un cliente,
  **cuando** se consulta su saldo,
  **entonces** la API devuelve el saldo **derivado** (suma de cargos − pagos − notas de crédito) y **no** un campo almacenado en la base de datos.
- **F2-AC5.** **Dado** el límite de un cliente ya superado por saldo pendiente,
  **cuando** se consulta su estado,
  **entonces** aparece como `suspendido` con la razón `limite_superado`.

### F3 — Cargos y pagos (la libreta)

- **F3-AC1.** **Dado** un cliente sembrado con un conjunto conocido de asientos,
  **cuando** se consulta su saldo pendiente,
  **entonces** el valor coincide **exactamente** con el total calculado a mano sobre la fixture.
- **F3-AC2.** **Dado** un cliente con un cargo de `10,00 €` del día 1 y otro de `40,00 €` del día 20, y ningún pago,
  **cuando** se registra un pago de `30,00 €` **una sola vez, como asiento del libro**,
  **entonces** el saldo pendiente baja **en exactamente 30,00 €** y el cargo **más antiguo** (el de 10,00 €) queda liquidado, mientras que el de 40,00 € conserva 20,00 € pendientes; la `caja` **sube en exactamente 30,00 €** —el pago **no** se anota además como `CashMovement`, para no duplicarlo— y la `posicion_real` **no cambia**.
- **F3-AC3.** **Dado** un pago **mayor** que la deuda total del cliente,
  **cuando** se aplica la imputación,
  **entonces** el exceso se conserva como **crédito a favor del cliente** y no se pierde ni altera el saldo de los cargos; la `caja` sube **en el importe completo del pago** y la `posicion_real` **no cambia**.
- **F3-AC4.** **Dado** cualquier asiento registrado,
  **cuando** se intenta modificarlo o borrarlo,
  **entonces** la operación no existe: el libro es **de solo apuntación** (append-only).
- **F3-AC5.** **Dado** una fecha de asiento posterior al momento actual,
  **cuando** se valida el formulario,
  **entonces** se rechaza con error de validación.

### F4 — Antigüedad y suspensión automática

- **F4-AC1.** **Dado** un cliente sembrado con un cargo impagado de **45 días**,
  **cuando** se consulta su estado,
  **entonces** la API devuelve `status = "suspendido"` **sin ninguna acción humana previa**, con `suspended_reason = "antiguedad_superada"` y `antiguedad_max_dias = 45`.
- **F4-AC2.** **Dado** ese cliente suspendido,
  **cuando** se intenta registrar un cargo nuevo,
  **entonces** el servidor responde con **HTTP 422** y un error de validación que explica el motivo, y **no se crea ningún asiento**.
- **F4-AC3.** **Dado** un cliente con cargos y pagos,
  **cuando** se calculan sus tramos de antigüedad,
  **entonces** cada principal impagado se asigna al tramo que le corresponde **por la edad de su propio cargo** (`vigente` ≤ 7 d, `envejecido` 8–30 d, `viejo` 31–90 d, `cronico` > 90 d; valor en máquina ASCII, `crónico` es solo la forma de presentación) y la suma de los cuatro tramos es **exactamente igual** al saldo pendiente, sin diferencia de céntimos. `antiguedad_max_dias` se informa aparte y ordena la escalera de riesgos.
- **F4-AC4.** **Dado** un cliente suspendido,
  **cuando** el dueño anula la suspensión de forma explícita,
  **entonces** el estado vuelve a `activo` y quedan registrados **quién** lo hizo y **cuándo** en `suspended_override_at` y `suspended_override_by`, sin reescribir ningún asiento del libro.
- **F4-AC5.** **Dado** un cliente con un cargo de `20,00 €` de hace 45 días y otro de `10,00 €` de hace 10 días, sin pagos,
  **cuando** se consulta su estado,
  **entonces** está `suspendido` con `antiguedad_max_dias = 45` y un saldo pendiente de `30,00 €`; y, **cuando** el dueño registra un `pago` de `20,00 €`,
  **entonces** la imputación FIFO liquida el cargo de 45 días, el saldo pendiente queda en `10,00 €`, `antiguedad_max_dias` pasa a `10`, el cliente vuelve a `activo` y **admite un cargo nuevo**; la `caja` sube `20,00 €` y la `posicion_real` **no cambia**.

### F5 — Posición real de la caja y cierre del día

- **F5-AC1.** **Dado** un cliente con `40,00 €` pendientes,
  **cuando** se registra un `pago` de `30,00 €` **una sola vez, como asiento del libro**,
  **entonces** el `fiado pendiente` baja **en exactamente 30,00 €**, la `caja` **sube en exactamente 30,00 €** y la `posicion_real` **no cambia** —el pago no se duplica como `CashMovement`—, y el tablero React muestra ese mismo reparto.
- **F5-AC2.** **Dado** un día con caja inicial conocida, movimientos registrados y pagos de clientes,
  **cuando** se consulta la posición,
  **entonces** `posicion_real = caja + Σ saldos pendientes`, con `caja = caja inicial + Σ movimientos de caja (entradas − salidas) + Σ pagos de clientes`; un `pago` de cliente **no** genera además un `CashMovement`.
- **F5-AC3.** **Dado** un cierre de día con `esperado = 412,35 €` y `contado = 408,00 €` (valores de la semilla de demostración),
  **cuando** se guarda el cierre,
  **entonces** se almacena `desviacion = −4,35 €` y el valor es visible en la vista del dueño.
- **F5-AC4.** **Dado** dos cierres en la misma fecha para la misma tienda,
  **cuando** se intenta guardar el segundo,
  **entonces** la base de datos lo rechaza por **unicidad de la fecha**.

---

## 2. Matriz de permisos (2 roles × 9 capacidades)

| # | Capacidad | `dueño` | `dependiente` |
| --- | --- | :---: | :---: |
| 1 | Registrar movimientos de caja (entradas / salidas) | Sí | Sí |
| 2 | Registrar el cierre del día (esperado vs. contado) | Sí | Sí |
| 3 | Ver el libro de clientes (alias, límites, saldos) | Sí | **No → 403** |
| 4 | Crear un cliente o modificar su línea de crédito | Sí | No |
| 5 | Registrar un cargo (fiado) o un pago | Sí | No |
| 6 | Ver los tramos de antigüedad y la escalera de riesgos | Sí | No |
| 7 | Anular una suspensión (desbloquear a un cliente) | Sí | No |
| 8 | Ver la posición real de la caja | Sí | No |
| 9 | Gestionar usuarios y roles | Sí | No |

**Aplicación en servidor (obligatoria, no solo ocultación en la interfaz):**

- Grupos de Django `dueno` y `dependiente`.
- Mixins de permiso por vista en **cada** URL y en **cada** vista DRF.
- *Querysets* acotados por **`Shop` y por rol**: los endpoints del libro de clientes filtran por tienda y **deniegan** el rol `dependiente` en el servidor, con independencia de la interfaz. **No existe** una FK de propietario en ninguna entidad: el ámbito es la tienda.
- El payload de `dependiente` en `GET /api/v1/posicion/` devuelve `clientes: []` y **no contiene alias en ninguna ruta del JSON**, ni siquiera anidados en agregados.
- El endpoint de cierre del día devuelve al `dependiente` únicamente `esperado`, `contado` y `desviacion`.
- **Razón de dominio:** el cuaderno se queda en el cajón; es el libro comercial privado del dueño, no un dato operativo de quien atiende el mostrador.

---

## 3. Modelo de datos completo

| Entidad | Campos | Relaciones y reglas |
| --- | --- | --- |
| `Shop` | `id`, `name`, `opening_cash`, `currency`, `created_at` | Una sola fila en el MVP. 1—N todas las entidades siguientes. |
| `Customer` | `id`, `FK shop`, `alias`, `phone` (opcional), `credit_limit` (nulo = «sin límite»), `status` (`activo`/`suspendido`), `suspended_at`, `suspended_reason` (`limite_superado`/`antiguedad_superada`), `suspended_by`, `suspended_override_at`, `suspended_override_by`, `created_at` | 1—N `LedgerEntry`. `credit_limit ≥ 0`. Sin datos identificativos: sin DNI/NIE, sin dirección, sin fotografía. Los campos de suspensión registran **quién** y **cuándo**, sin entidad nueva y sin mutar el libro. |
| `LedgerEntry` | `id`, `FK shop`, `FK customer`, `kind` (`cargo`/`pago`/`nota_credito`), `amount`, `description`, `occurred_at`, `FK author`, `created_at` | N—1 `Customer`, N—1 `User`. **Append-only**: sin `UPDATE` ni `DELETE` en la capa de servicio. `amount > 0`. `occurred_at ≤ now`. |
| `CashMovement` | `id`, `FK shop`, `kind` (`entrada`/`salida`), `concept`, `amount`, `occurred_at`, `FK author`, `created_at` | N—1 `User`. `amount > 0`. `occurred_at ≤ now`. |
| `DayClose` | `id`, `FK shop`, `date` (única por tienda), `expected_cash`, `counted_cash`, `variance`, `FK closed_by`, `closed_at` | N—1 `User`. `date` única por tienda. `variance` calculada, no introducida a mano. |
| `User` | usuario de Django con grupo `dueno` o `dependiente` | N—1 en `LedgerEntry`, `CashMovement` y `DayClose` (autor registrado en cada escritura). |

**Sin columna de saldo.** El saldo pendiente, los tramos de antigüedad, el estado de suspensión y la posición real se **derivan** de los asientos, de modo que cualquier fecha pasada se puede recalcular y el número no puede desincronizarse.

---

## 4. Preguntas que el tribunal de defensa hará

| # | Pregunta | Esqueleto de respuesta (una línea) |
| --- | --- | --- |
| 1 | «¿Por qué no una libreta de papel o un Excel?» | El cuaderno no tiene antigüedad, ni límite, ni regla, y muere con el dueño; el Excel puede envejecer una lista pero no puede imponer una regla ni sobrevivir a la ausencia del dueño. |
| 2 | «¿Esto no es una simple tabla de saldos?» | Un saldo es un número; esto es un libro con saldos **derivados**, antigüedad por fecha de cargo, una línea de crédito con **suspensión automática** y la exposición neta de caja. |
| 3 | «¿Cómo garantizáis que un cliente con 40 días de deuda no recibe más fiado?» | La regla se evalúa en el servidor, dentro de la misma transacción del cargo, devuelve 422 y no crea asiento; la base de datos solo puede vigilar los invariantes por fila (importe positivo, tipo permitido, fecha no futura, fecha de cierre única). |
| 4 | «¿Y la protección de datos? Guardáis deudas de clientes.» | Se guarda un alias, un teléfono opcional e importes: sin DNI, sin dirección, sin datos bancarios, sin fotos de la libreta; el libro es **solo del dueño** y cada escritura registra su autor. |
| 5 | «¿Cómo se calcula la posición real y por qué me fiáis de ella?» | Es `caja + fiado pendiente`: una suma sobre asientos inmutables con una única regla de imputación FIFO, recalculada en cada lectura, y la API devuelve el **desglose** además del total. |
| 6 | «¿Por qué no incluye producto, precio y punto de venta?» | Es alcance deliberado: el MVP responde a la pregunta del dinero; servir en el mostrador está bien cubierto por herramientas baratas y no es la restricción real de la tienda. |
| 7 | «Si un cliente paga, ¿no sube mi posición real?» | No: la `posicion_real` es `caja + fiado pendiente`. Un pago **sube la `caja`** y **baja el fiado pendiente** en la misma cantidad, así que la posición real **no cambia**: el dinero se convierte de deuda en efectivo, no se crea ni se pierde. Lo que sí cambia es la escalera: el cargo más viejo queda liquidado, la antigüedad máxima baja y el cliente vuelve a `Activo`. |

---

## 5. No-objetivos (fuera de alcance)

- Punto de venta, mostrador, caja registradora, tickets y recibos.
- Catálogo de productos, precios, tarifas y códigos de barras.
- Portal del cliente, cuentas de cliente y pagos en línea.
- Cobranza, intereses, recordatorios por correo/SMS y gestión automatizada de cobros.
- Facturación fiscal, impuestos y contabilidad oficial.
- Compras a proveedores, pedidos y entradas de mercancía.
- Multi-sucursal, multi-tenant y facturación por suscripción.
- Subida de ficheros, fotos de la libreta y almacenamiento externo.
- Aplicación móvil nativa.
- Workers en segundo plano, Celery, Redis y WebSockets.
- Modelos de IA o ML, APIs de terceros de pago y web scraping.
