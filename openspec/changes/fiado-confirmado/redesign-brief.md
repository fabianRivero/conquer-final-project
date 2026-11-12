# Rediseño brief — `fiado-confirmado` v2

## Qué cambió y por qué

El mecanismo de disputa y la `nota de crédito` se eliminan. El problema que→「fiado confirmado» resolvía —*las dos partes no tienen la misma cifra*— se resuelve ahora **por prevención** en lugar de por resolución:

> El dueño prepara un fiado con su desglose. En la tienda, el cliente lo ve en una pantalla y lo **confirma**. Solo entonces el cargo existe y pasa a ser deuda. Si no lo confirma, el dueño cancela la propuesta y no queda deuda.

El resultado es un modelo con **dos** tipos de movimiento en el libro (`cargo`, `pago`) en vez de tres, **un** estado de confirmación en vez de dos, y **cero** notas de crédito.

## El modelo nuevo, completo

### El ciclo de vida de un fiado

```
1. El dueño prepara un FiadoPropuesto
     → cliente + líneas (producto, cantidad, precio unitario) + total
     → NO genera deuda. El pendiente del cliente no se mueve.

2. El cliente ve la pantalla de la propuesta EN LA TIENDA y la confirma
     → se registra una Confirmacion(confirmado, confirmado_en, origen)
     → en la MISMA transacción se escriben el LedgerEntry(cargo) y sus CargoLinea
     → AHORA sí es deuda. El pendiente se mueve.

3. Si el cliente no confirma, el dueño cancela la propuesta
     → no hay cargo, no hay deuda. La propuesta queda cancelada.

4. El cliente entra en su portal con su codigo
     → ve lo que ha confirmado, con su desglose completo
     → propone un pago (no escribe en el libro); el dueño lo valida y lo registra.
     → el comprobante (imagen, PDF o documento) es una EXTENSIÓN PREVISTA, no implementada.
```

### Lo que desaparece

| Elemento | Dónde estaba |
|---|---|
| `kind='nota_credito'` | `LEDGER_ENTRY_KINDS`, `EntryKind`, `allocate_payments(credit_notes=)`, `outstanding`, `evaluate_customer` |
| `estado='en_disputa'` | `CONFIRMATION_STATES`, `ConfirmState`, `estado_cargo`, `transicion_permitida` |
| `importe_reclamado` | `Confirmacion` y sus CHECKs |
| `cargo_id` en `LedgerEntry` | `models.py` y sus dos constraints |
| `uniq_confirmacion_one_disputa_per_cargo` | `models.py` |
| `uniq_ledgerentry_one_reconciliation_per_cargo` | `models.py` |
| `chk_ledgerentry_cargo_only_on_credit_note` | `models.py` |
| `chk_confirmacion_state_fields` | `models.py` |
| `chk_confirmacion_importe_non_negative` | `models.py` |
| La capability `dispute-resolution` | 4 requisitos (DR-01…DR-04) — **ya eliminada de las specs** |
| El estado `sin_confirmar` | `estado_cargo`; ya no hay un cargo sin confirmar |
| `escalado_sin_confirmar` | `domain/confirmation.py` — el flag de 7 días pierde su objeto |
| `ConfirmarAccion`, `Disputar` | React, en la superficie del cliente |
| `POST /api/v1/cliente/confirmar/`, `POST /api/v1/cliente/disputar/` | API |

### Lo que aparece

| Elemento | Qué es |
|---|---|
| **`FiadoPropuesto`** | Tabla nueva: `shop`, `customer`, `estado` (`pendiente`/`confirmado`/`cancelado`), `total`, `created_at`, `confirmed_at?`, `canceled_at?`, `user` (quién lo preparó), `facilitado_por?`. Sus `lineas` son `PropuestaLinea`: `producto`, `cantidad`, `precio_unitario`, `total`. |
| **La pantalla de la propuesta, en la tienda** | Donde el cliente confirma. Es una superficie **de personal**, no del cliente: la ruta de lectura y la de confirmación las sirve la sesión del dueño. |
| **`Confirmacion`** | Se queda, con **un solo estado**: `confirmado`. Campos: `cargo`, `confirmado_en`, `origen`, `facilitado_por?`. Sin `importe_reclamado`. |
| **La propuesta de pago del cliente** | El cliente propone un pago desde su portal: `cliente`, `importe`, `referencia` (texto), `estado` (`pendiente`/`validado`/`rechazado`). **No escribe en el libro**; el dueño lo valida y registra el `pago`. |

### La invariante que cambia y por qué importa

**El cliente nunca escribe en el libro.** Antes escribía cargos, pagos, notas de crédito, confirmaciones y disputas. Ahora escribe **nada**: ni una fila del libro, ni una `Confirmacion`. Su `codigo` es un identificador de **lectura** y le permite **proponer** un pago.

Esto deja intacto el principio que ya está en el código (`"A client never writes to the ledger directly"`), y con él la mitad de la arquitectura de scopes (§7, §8) y el threat model (§12). **Menos superficie de escritura = menos superficie de ataque.**

### El desglose pasa a ser obligatorio

Un cargo sin líneas deja de existir. La razón es de modelo, no de rigor: **el cliente confirma una figura que puede ver desglosada**. Si no hay desglose, no hay nada que confirmar, y entonces el "confirmado" no significaría nada.

Esto elimina el caso "cargo sin itemización" de IC-02 y hace que `lineas_descuadradas` sea siempre exigible.

### El `codigo` y su alcance

- Sigue siendo una credencial portadora, por tienda, con un `prefix`, hasheada, rotable, y con throttle.
- Su alcance baja: **lectura del estado de cuenta del cliente + propuesta de un pago**.
- El `codigo` **no** habilita confirmar ni disputar (ya no existen para el cliente).

### El comprobante: extensión prevista, NO implementada

El cliente podrá adjuntar un comprobante (imagen, PDF o documento) al proponer un pago. **No se implementa en este cambio.** Se declara como extensión prevista con su propia línea de corte, en el mismo patrón que `serie_caja` (línea de corte 1) y `existencias_registradas` (Regla 6). En el artefacto se declara **qué** haría falta (almacenamiento de ficheros, subida multipart, validación de tipo y tamaño, un modelo de adjunto) y **por qué** no entra: el almacenamiento de ficheros binarios en un servidor efímero o en la base de datos añade una capacidad completa, y un comprobante bancario es dato personal.

## Las specs ya reescritas — léelas, son el contrato

Ya están en `openspec/changes/fiado-confirmado/specs/`:

- `client-confirmation/spec.md` — **reescrita entera**. CC-01…CC-07 nuevos.
- `itemised-charges/spec.md` — **reescrita entera**. IC-03 y IC-04 cambiados, IC-07 exige desglose.
- `payments-and-ageing/spec.md` — PA-01, PA-05, PA-07, PA-09, PA-10 cambiados; PA-04 eliminada.
- `confirmation-facilitation/spec.md` — **reescrita entera**. CF-01 y CF-02 nuevos.
- `dispute-resolution/` — **ELIMINADA**.

Y `requirement-index.md` está regenerado: **48 requisitos, 15 condicionales, 83 escenarios**.

## El mapa exacto de qué reescribir en el diseño

`design.md` tiene 19 secciones y 621 líneas. These son las que cambian:

| Sección | Qué hay que hacer |
|---|---|
| §1 Technical Approach | La tercera idea ("un cargo es deuda desde que se registra") pasa a ser "un cargo es deuda desde que el cliente lo confirma". Mencionar el ciclo preparar→confirmar→deuda. |
| §2 The Ten Decisions | **D7** (doble confirmación / doble reconciliación) → reescribirla: ahora es "un cargo por propuesta confirmada, y una propuesta por cargo". **D9** (el flag de 7 días sobre `sin_confirmar`) → **desaparece**: no hay cargo sin confirmar, así que no hay nada que escalar. **D6** (la frontera de fuga del `dependiente`) → se mantiene pero el `dependiente` ahora prepara propuestas, no presenta cargos. **D3** (transporte del `codigo`) → se mantiene, pero su alcance baja. **D5** (modelo de movimiento de stock) → se mantiene. Añadir una decisión nueva sobre el comprobante (extensión prevista). |
| §3 Data Model | Los 12 entidades → 13 (nace `FiadoPropuesto` y `PropuestaLinea`; `CodigoIntento` se queda). `LEDGER_ENTRY_KINDS` → 2 valores. `Confirmacion` → un estado, sin `importe_reclamado`. `LedgerEntry` → sin `cargo`. Los 5 constraints que se van. Los 2 índices parciales que se van. Los que se quedan: `uniq_confirmacion_one_confirmado_per_cargo`. **Nuevos**: los de `FiadoPropuesto` (estado, unicidad de propuesta viva por cliente) y los de `PropuestaLinea` (cantidad positiva, precio no negativo, total = cantidad × precio). |
| §4 ADRs | Los 24 ADRs. Los que desaparecen o se reescriben: el de la doble confirmación (ADR-20), el del estado derivado de la confirmación (ADR-18), el de reconciliar una disputa (ADR-19). Los que se reescriben: el de la credencial (ADR-16) por su alcance nuevo. Añadir: el ADR de "el cargo existe solo al confirmar" y el del comprobante como extensión. |
| §5 Client Credential | Su alcance: lectura del estado de cuenta + propuesta de pago. El throttled de siempre. El leak surface, sin cambios de fondo. Los 9 RED tests, con R6 y R9 reescritos (ahora hablan de la fila almacenada, no de la reconciliación). |
| §6 Confirmation State Machine | **Reescrita entera.** Deja de ser una máquina de dos estados con vuelta atrás. El nuevo flujo: `FiadoPropuesto.pendiente → confirmado` (escribe cargo + líneas + `Confirmacion`) y `FiadoPropuesto.pendiente → cancelado` (no escribe nada). Una transición de ida, sin vuelta. Y el `Confirmacion` con un solo estado. |
| §7 Permission Matrix | Actualizar: el cliente **no** confirma ni disputa; solo lee y propone un pago. El `dependiente` prepara propuestas. El dueño prepara, confirma y registra pagos. |
| §8 Scope Mechanisms | El cliente pierde el poder de escritura. La invariante "un ámbito actuante por petición" se mantiene. Añadir la nota de que la propuesta de pago es una **petición**, no un ámbito. |
| §9 API Contracts | Las rutas: quitar `POST /api/v1/cliente/confirmar/` y `POST /api/v1/cliente/disputar/`. Añadir `GET /api/v1/propuestas/{id}/pantalla/` y `POST /api/v1/propuestas/{id}/confirmar/` y `POST /api/v1/propuestas/{id}/cancelar/` (**de personal**), y `POST /api/v1/cliente/pagos/proponer/` (**de cliente, no escribe en el libro**). Los serializers: el del cliente lleva el desglose de los cargos **confirmados** y ya no el estado `sin_confirmar` ni el `disputa`. |
| §10 Pure Rules Module | Actualizar las firmas: `allocate_payments` sin `credit_notes`; `outstanding` sin notas; `evaluate_customer` sin notas; `estado_cargo` con dos estados; y **eliminar** `transicion_permitida` y `escalado_sin_confirmar` si dejan de tener objeto. Añadir la regla del desglose obligatorio. |
| §11 The Two React Surfaces | El tablero del dueño gana: preparar propuesta, ver la pantalla de confirmación, registrar pagos. La superficie del cliente pierde `ConfirmarAccion` y `Disputar`, y gana "ver el desglose de lo confirmado" y "proponer un pago". Añadir la tercera superficie: **la pantalla de la tienda**. |
| §12 Security Architecture | Actualizar el leak surface. Añadir el landmine del comprobante (no implementado) y el de la pantalla compartida (el cliente ve la pantalla del dueño: ¿qué se garantiza?). |
| §13 Data Flow | **Reescrita**: el flujo de la propuesta y la confirmación, el flujo del pago (propuesta→validación→registro), y el flujo de la lectura del portal. Se elimina el flujo de la disputa. |
| §14 File Changes | Los ficheros: los que ya existen, más `FiadoPropuesto`, `PropuestaLinea`, la propuesta de pago, la pantalla de la tienda. |
| §15 Testing Strategy | Actualizar: los tests de constraints, los unitarios, los de integración, y añadir los de la pantalla de la tienda. |
| §16 Traceability Matrix | **Regenerar**: 48 requisitos (no 53), cada uno con su casa en el diseño. La columna de diseño de cada fila cambia. |
| §17 Threat Matrix | Las 5 filas de referencia siguen siendo N/A. La fila de "la superficie del cliente" cambia: ya no hay escrituras del cliente. Añadir la fila de la pantalla de la tienda. |
| §18 Migration / Rollout | El seed cambia: el dataset lleva un cargo confirmado, uno pendiente de confirmar, una propuesta cancelada, un cliente con codigo. |
| §19 Open Questions | Actualizar: las preguntas que dependían de las entrevistas (Regla 4) siguen, pero las que dependían de la disputa se reformulan. |

Las secciones §18.1 (deployment spine) y §12.2 (landmines) se conservan en su mayor parte.

## Reglas de escritura

- **Prose en English.** Todos los identificadores de dominio en español: `fiado`, `cargo`, `pago`, `propuesta`, `linea`, `desglose`, `caja`, `dependiente`, `dueño`, `libreta`, `posición real`, `confirmación`, `existencias_registradas`, `codigo`, `Producto`, `CargoLinea`, `Propuesta`, `PropuestaLinea`, `Confirmacion`, `LedgerEntry`, `CashMovement`, `DayClose`, `Customer`, `Shop`, `CustomerCodigo`, `CodigoIntento`, `FiadoPropuesto`, `PagoPropuesto`, `antiguedad_max_dias`, `suspended_reason`, `vigente`/`envejecido`/`viejo`/`cronico`, `credit_limit`, `posicion_real`, `precio_unitario`, `confirmado_en`, `facilitado_por`, `pendiente`/`confirmado`/`cancelado`, `techo_no_conteo`.
- **Nunca traduzcas un identificador al inglés.**
- Tablas y diagramas, no prosa. Es el estilo de la casa.
- No reescribas lo que no cambia: §18.1, §12.2 (salvo los landmines nuevos), §4 (los ADR que siguen vivos), §5 (salvo el alcance), §7.1, §8 (salvo el punto del cliente).
- **El tamaño objetivo es 26.000–34.000 bytes**, como el diseño anterior. Si te pasas, comprime en vez de continuar.
- Escribe en **una sección por turno de generación**, nunca todo el fichero de una vez. Empieza por §1–§3 y sigue.
