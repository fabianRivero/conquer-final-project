# Propuesta de proyecto PFM — `fiado confirmado`: el fiado que ratifica el cliente

**Estado: para validación del equipo docente. Base del conocimiento: hipótesis de diseño declarada sobre el contexto del `fiado`; sin evidencia de campo. Ver «Base del conocimiento».**
**Este cambio (`fiado-confirmado`) sustituye al alcance `fiado` de `tienda-barrio`**, que queda en disco como historial: su propuesta, especificaciones y diseño se abandonan, no se modifican.
**Revisión v2 — 2026-11-12.** El modelo de producto cambió tras esta propuesta: el mecanismo de disputa y la `nota de crédito` se eliminaron y la confirmación se convirtió en la **puerta** del cargo, no en su ratificación. Ver «Qué cambió en la v2».

## Problema

El fiado —lo que el cliente se lleva y paga después— vive en la cabeza del dueño y en un cuaderno. El problema de hoy no es solo que el dueño no sepa cuánto le deben: es que **las dos partes no tienen la misma cifra**. El dueño recuerda un importe, el cliente recuerda otro, y el cuaderno no puede zanjarlo porque no tiene regla, no tiene límite y no tiene el testimonio de un tercero.

La v1 atacaba ese problema por la vía de la **resolución**: el cliente disputaba lo que el dueño anotaba y el dueño arbitraba con una `nota de crédito`. Es un modelo que necesita que las dos partes distrusten del registro común, y que produce un asiento de corrección por cada desacuerdo.

La v2 lo ataca por la vía de la **prevención**: **el cargo no existe hasta que el cliente lo ve desglosado y lo confirma**. El dueño prepara una figura con su desglose; en el mostrador, sobre el dispositivo de la tienda, el cliente la ve y la ratifica; solo entonces el cargo se escribe en el libro. Si el cliente no confirma, el dueño cancela la propuesta y **no queda deuda**. El desacuerdo que la disputa arbitrava desaparece, porque la cifra la fijó el cliente antes de que existiera.

El contexto lo impone: una tienda de 30–120 m², con 1–3 personas y 100–400 transacciones al día, mayoritariamente en efectivo, en la que **el dueño es el activo**: conoce al cliente por su nombre y eso es su ventaja competitiva. Ningún producto que exija disciplina nueva (contar, categorizar, registrar ventas) se usará; solo vale lo que se apoya en un gesto que la tienda ya hace — y la confirmación en el mostrador es exactamente eso.

## Usuarios y roles

| Principal | Qué es | Qué puede |
| --- | --- | --- |
| `dueño` | Usuario Django, grupo `dueno` | Todo: clientes, crédito, `cargo`, `pago`, antigüedad, suspensión, `posición real`, cierre, `codigo`, propuestas, confirmaciones y validación de pagos. |
| `dependiente` | Usuario Django, grupo `dependiente` | Registra `caja` y cierre del día. **El libro de crédito le devuelve 403**, sin alias ni saldos. *Una capacidad estrecha y condicional:* preparar **una** propuesta y registrar su confirmación, sin ver lista, saldo ni antigüedad — y solo si la gate N5 se abre. |
| `cliente` | **No es un rol.** No es grupo, ni `User`, ni sesión: es una **credencial portadora (`codigo`) acotada a un único `Customer`**, resuelta en el servidor | Ver sus cargos **confirmados** con su desglose completo, y **proponer un pago**. **Nada más**: ni confirmar, ni cancelar, ni disputar, ni registrar un pago, ni la `caja`, ni la `posición real`, ni otro cliente. |

**Invariante de credenciales:** ningún ámbito de cliente puede existir dentro de una sesión de personal, y ninguna sesión de personal puede promoverse a ámbito de cliente. Por eso la superficie del cliente **no tiene sesión**: la credencial se presenta en cada petición. Y una segunda invariante, propia de la v2: **el cliente nunca escribe en el libro**. Su credencial abre **lectura** y **propuesta**; el `cargo`, su desglose y su confirmación los registra la sesión de personal; el `pago` lo registra el dueño. Matriz completa en los anexos.

## Alcance mínimo — 7 funcionalidades (+1 condicional)

1. **Cuentas, roles y credenciales del cliente** (`client-accounts-and-credentials`). *AC:* `dependiente@tienda.test` recibe **403** en `/api/v1/clientes/` y ningún `codigo` aparece en su payload; el `dueño` emite un `codigo` único en la tienda y rotable.
2. **Catálogo de productos y precios** (`product-catalogue`). *AC:* un `Producto` sembrado a 1,20 € lo devuelve la API del catálogo y se ofrece como precio por defecto de una línea de cargo; el catálogo solo contiene los productos aptos para fiado.
3. **Cargos con líneas de producto** (`itemised-charges`). *AC:* un `cargo` de dos líneas que suma 6,40 € crea dos `CargoLinea` y un `LedgerEntry` de 6,40 €; cambiar después el precio del catálogo no toca el `precio_unitario` almacenado. **El desglose es obligatorio**: un cargo sin líneas no puede existir.
4. **Pagos, antigüedad y suspensión** (`payments-and-ageing`). *AC:* un `pago` de 30 € salda primero el cargo más antiguo y baja `antiguedad_max_dias` de 45 a 10; un cargo impagado de 45 días suspende al cliente sin acción humana, y un cargo nuevo se rechaza con **422** sin crear fila. **Sin notas de crédito**: un `pago` nunca excede la deuda que salda y el exceso lo devuelve el dueño como cambio.
5. **La propuesta, la pantalla de la tienda y la confirmación** (`client-confirmation`). *AC:* el dueño prepara una `FiadoPropuesto` con su desglose y **el libro no cambia**; el cliente ve la propuesta en la pantalla del mostrador y la confirma; la confirmación escribe el `cargo`, sus `CargoLinea` y la fila de `Confirmacion` **en la misma transacción**. El cliente nunca escribe en el libro: su credencial solo lee y propone.
6. **La propuesta del cliente y el pago que registra el dueño** (`client-confirmation`). *AC:* el cliente propone un pago desde su portal y **no escribe ninguna fila del libro**; el dueño lo valida y entonces se registra el `pago` con su reparto. Un `pago` mayor que el pendiente se rechaza con **422**.
7. **Posición real, cierre del día y existencias registradas** (`cash-position`). *AC:* un `pago` de 30 € sube la `caja` en 30 € y **no** altera `posicion_real`; el cierre guarda `esperado`, `contado` y `desviacion`; `existencias_registradas` se devuelve con su calificador de techo y **ningún** endpoint rechaza un `cargo` por falta de existencias.
8. **Condicional — facilitar la confirmación por el `dependiente`** (`confirmation-facilitation`). El `dependiente` puede preparar **una** propuesta y registrar su confirmación, anotando `facilitado_por`, y no alcanza lista, saldo ni antigüedad. **Solo se añade si la entrevista N5 muestra que el ayudante da el fiado**; si no, el 403 queda intacto.

Capacidades **modificadas**: ninguna. Las especificaciones de `tienda-barrio` quedan como historial y no se modifican; este change produce especificaciones nuevas.

## Entidades de datos

| Entidad | Campos y relaciones |
| --- | --- |
| `Producto` | `id, nombre, precio, unidad, activo` — vocabulario del libro; solo los productos aptos para fiado |
| `CargoLinea` | `id, FK cargo, FK producto, cantidad, precio_unitario, total` — hija de un `cargo`; `precio_unitario` es una **instantánea** del precio del momento |
| `PropuestaLinea` | `id, FK propuesta, FK producto, cantidad, precio_unitario, total` — el mismo desglose, antes de que el cargo exista |
| `FiadoPropuesto` | `id, FK shop, FK customer, FK user, FK facilitado_por?, estado (`pendiente` \| `confirmado` \| `cancelado`), total, created_at, confirmed_at?, canceled_at?` — **una transición de ida**, nunca de vuelta |
| `Confirmacion` | `id, FK cargo, estado (`confirmado`), confirmado_en, origen, FK facilitado_por?` — **un solo estado**; solo se añade, nunca se actualiza ni se borra |
| `ImputacionPago` | `id, FK pago, FK cargo, importe` — **una fila por cada par (pago, cargo)** que el pago toca; el grano es el cargo |
| `PagoPropuesto` | `id, FK shop, FK customer, importe, referencia, estado (`pendiente` \| `validado` \| `rechazado`), created_at, resolved_at?, FK resolved_by?` — la petición del cliente; **no escribe en el libro** |
| `Customer` | `id, alias, phone?, credit_limit?, created_by?, suspended_override_at?, suspended_override_by?` — **sin `status`, sin `suspended_reason`, sin `codigo`** |
| `Shop` | `id, name, opening_cash, currency, is_demo` — 1—N todas |
| `LedgerEntry` | `id, kind (`cargo` \| `pago`), amount, occurred_at, created_at, FK user` — N—1 `Customer`; **sin `cargo_id`** |
| `CashMovement` | `id, kind (`entrada` \| `salida`), amount, occurred_at, concept, FK user` — N—1 `Shop` |
| `DayClose` | `id, date, esperado, contado, desviacion, FK user` — N—1 `Shop` |

Más el `User` de Django, los grupos `dueno` y `dependiente`, `CustomerCodigo` (la credencial) y `CodigoIntento` (el registro de throttle).

**Invariantes:**
- `LedgerEntry.amount == Σ CargoLinea.total`, comprobado en el servidor dentro de la transacción de escritura. **El desglose es obligatorio**: un cargo sin líneas no se puede escribir.
- **No se almacena nada derivado**: ni saldo, ni antigüedad, ni estado de confirmación, ni antigüedad de tramos, ni **crédito a favor**. El estado efectivo de un `cargo` se deriva de su `Confirmacion`; los tramos `vigente` / `envejecido` / `viejo` / `cronico` se derivan de la fecha del cargo; el saldo pendiente de un cargo se deriva de sus `ImputacionPago`.
- El libro es **append-only**: sin `UPDATE` ni `DELETE`. Cinco tablas lo son — `LedgerEntry`, `CargoLinea`, `Confirmacion`, `PropuestaLinea` e `ImputacionPago`. Las correcciones, si las hay, son **filas nuevas**.
- **El cliente nunca escribe en el libro.** La confirmación la registra la sesión de personal; el pago, el dueño tras validar la propuesta del cliente.
- **Un cliente nunca tiene crédito a favor.** Un `pago` nunca excede la deuda que salda; el exceso lo devuelve el dueño como cambio y no entra en el libro.

## Las tres superficies

Un solo bundle Vite, un solo origen, tres modos de credencial.

| Superficie | Quién | Credencial | Contenido |
| --- | --- | --- | --- |
| `/app/posicion` | `dueño` | Sesión Django + `X-CSRFToken` | La ecuación del negocio (`caja + Σ pendiente = posición real`), la escalera de riesgos con cintas de antigüedad y el estado de cada cargo (`confirmado` / `sin_confirmar`), el cierre del día, las propuestas pendientes y los pagos propuestos. |
| `/app/propuesta/{id}` | `dueño` | Sesión Django + `X-CSRFToken` | **La pantalla del mostrador.** El `desglose` completo de la propuesta — producto, cantidad, `precio_unitario` y `total` — y nada más: ni saldo, ni antigüedad, ni otro cliente. Sus dos acciones son **Confirmar** y **Cancelar**. |
| `/app/cliente` | `cliente` | `codigo` presentado por petición | Los cargos **confirmados** con su desglose completo, lo que ya pagó de cada uno y lo que le queda, y la **propuesta de un pago**. No hay acción de confirmar ni de cancelar: el cliente no escribe. |

La confirmación ocurre **en el mostrador, sobre el propio dispositivo de la tienda**, y esa es la superficie principal: una ratificación que espera a que el cliente llegue a casa no se produce. El móvil del cliente es la secundaria, con la misma credencial y la misma URL — pero para *leer* y para *proponer un pago*.

## Enfoque técnico

Django 5.2 + DRF; **sesión + CSRF** en las superficies de personal y **ninguna sesión** en la del cliente; reglas de dominio como **funciones puras sin ORM** (`allocate_payments`, `imputations_of`, `bucket_of`, `evaluate_customer`, `real_position`, `estado_cargo`, `confirmacion_efectiva`, `propuesta_transicion_permitida`) con pruebas unitarias; React + TS + Vite servido por Django con **WhiteNoise** (un origen, sin CORS); Render + Neon free; `DEBUG=False`; secretos solo en el entorno. La semilla se amplía con el catálogo, las líneas de cargo, un `codigo` por cliente, **un cargo confirmado**, **una propuesta pendiente** y **una propuesta cancelada**.

## Qué cambió en la v2

La v1 de esta propuesta atacaba el desacuerdo por la vía de la resolución. La v2 lo hace por la prevención, y eso toca el modelo entero:

| | v1 | v2 |
|---|---|---|
| El desacuerdo | se **arbitra**: disputa, `importe_reclamado`, `nota de crédito` | se **previene**: el cargo no existe hasta que el cliente lo confirma |
| El cargo | existe desde que el dueño lo anota | existe desde que el cliente lo confirma |
| El cliente | confirma, disputa y cancela | **lee y propone un pago**. No escribe nada |
| El libro | `cargo`, `pago`, `nota_credito` | `cargo`, `pago` |
| `Confirmacion` | dos estados: `confirmado`, `en_disputa` | un estado: `confirmado` |
| El pago | puede exceder la deuda y deja un crédito a favor | nunca excede la deuda; el exceso es cambio |
| El reparto de un pago | se recalcula al leer | se **registra** en `ImputacionPago`, por cargo |
| Capacidades | 7 + 1 condicional, con `dispute-resolution` | 7 + 1 condicional, **sin** `dispute-resolution` |
| Requisitos | 53 | **48** |

**Qué se conserva:** el esqueleto del libro append-only, el FIFO, la antigüedad, el `credit_limit`, la suspensión automática, el **403** del `dependiente`, la superficie de personal con sesión + CSRF, el montaje del mismo origen, la `posición real` aditiva, el `Decimal` en el cable, el contrato 422 y el plan de `seed_demo`.

**Qué se pierde, y por qué:** la capability `dispute-resolution` entera, con sus cuatro requisitos, y la `nota de crédito` como mecanismo de corrección. No es que la disputa sea imposible: es que **el cargo no se escribe hasta que el cliente lo ha visto desglosado**, así que la cifra que se disputa nunca existió como deuda. El propio `dispute-resolution` era un mecanismo de arbitraje para un problema que la v2 elimina en el origen.

## El precio del alcance, en abierto

Con los mismos pesos de la rúbrica (25 / 20 / 15 / 15 / 15 / 10), el alcance nuevo **no es la mejor variante por puntuación**:

| Variante | Puntuación /10 |
| --- | --- |
| `fiado` (anterior) | 8,15 |
| `fiado desglosado` | 7,80 |
| `margen` | 7,70 |
| **`fiado confirmado` (este)** | **7,45** |

Toda la diferencia está en **encaje de alcance (−2)** y **riesgo técnico (−1)**: siete funcionalidades en vez de cinco, un tercer tipo de principal, **tres** superficies, un segundo mecanismo de credencial, **cuatro** entidades nuevas y una máquina de estados de confirmación. El proyecto **no se defiende como «mejor englobado»**: se defiende porque ataca un dolor que el alcance anterior no tocaba, porque el mecanismo es nuevo, porque el alcance está **topado** y porque la decisión la toma la evidencia, no el gusto.

**Tres líneas de corte, declaradas por adelantado:**

1. El gráfico de `serie_caja` de 30 días (un elemento React, no una funcionalidad).
2. `existencias_registradas` — se incluye como techo opcional, no como conteo. Ninguna regla, precio, límite o suspensión depende de la cifra y ningún endpoint rechaza un `cargo` por falta de existencias, así que retirarla no cambia ninguna regla del sistema.
3. El **comprobante** del pago — se declara como extensión prevista, **no implementada**: un `PagoPropuesto` lleva un `importe` y una `referencia` de texto, sin fichero, sin subida y sin modelo de adjunto. El almacenamiento binario en un servidor efímero es una capacidad entera, y un comprobante bancario es dato personal.

**Repliegues nombrados:**
- Si la confirmación no se adopta (Regla 4 vacía) → **`fiado desglosado`** (7,80): catálogo y líneas de cargo, sin portal de cliente.
- Si el crédito no es una práctica real (Regla 1 vacía) → **`margen`** (7,70).

**No negociables:** el libro append-only · el **403** del `dependiente` · la vista React consumiendo la API propia en la URL pública · la URL pública HTTPS con `DEBUG=False` y datos sembrados.

**Riesgos que asumimos:** que el dueño no llegue a pedir la confirmación (fricción social, no técnica); que la tienda no tenga dispositivo para el mostrador; que el cliente no tenga navegador en el móvil; y que `existencias_registradas` derive de movimientos sin las ventas en efectivo, por lo que es un **techo y nunca un conteo**.

## Fuera de alcance

| Fuera | Por qué |
| --- | --- |
| Punto de venta, caja registradora, `venta`, recibos, código de barras, tender, cajón | Registrar a mano 100–400 ventas diarias en efectivo es un punto de venta **sin hardware**, contra un dueño que nunca ha registrado una venta y no va a empezar. Un POS no ratifica deudas. |
| Conteo físico de existencias, `conteo`, ajustes de inventario | Un conteo exige un conteo, y contar es justo la acción que la tienda no va a adoptar. |
| Coste de compra, `coste_medio`, margen, proveedores, órdenes de compra | Es el terreno de `margen`: el catálogo es un vocabulario, no un modelo de costes. |
| Correo, SMS, notificaciones, recordatorios | El SMTP saliente está bloqueado en los planes gratuitos; la confirmación está diseñada en persona. |
| Pagos en línea, tarjeta, transferencias | — |
| **Crédito a favor del cliente, saldos a favor, `credit_a_favor`** | Una tienda **devuelve el cambio**. Un crédito a favor sería una capacidad entera —envejecer, limitar, conciliar y explicar un saldo que no es una deuda—, y un valor derivado almacenado. La regla que lo impide es una sola: **un `pago` nunca excede la deuda que salda**. |
| **Subida del comprobante de pago, foto del recibo** | Declarado como extensión prevista, no implementado (ADR-25). |
| App móvil nativa, escaneo de código de barras o QR | La credencial se teclea; la superficie es una página web. |
| Cuentas de cliente con contraseña, autorregistro, restablecimiento | El cliente tiene una **credencial acotada**, no una cuenta. |
| Editar o borrar un `cargo`, una `Confirmacion` o cualquier asiento | Estructuralmente imposible: el libro es append-only y la API no expone `PUT` / `PATCH` / `DELETE`. |
| Cobranza, intereses, scoring, decisiones automáticas | — |
| Facturación fiscal, varios comercios, multi-sucursal, SaaS | — |
| Worker en segundo plano, Celery, Redis, WebSockets, un segundo servicio | — |
| Que el cliente vea algo que no sea suyo | El ámbito de la credencial es un único `Customer` por construcción. |

## Base del conocimiento — hipótesis de diseño declarada

**Esta propuesta se construye sobre una hipótesis de diseño, no sobre evidencia de campo collected.** La práctica del `fiado` en tiendas de barrio se toma como **contexto del dominio conocido**: el fiado existe, se anota en una libreta o en la cabeza, y el dueño no sabe con exactitud cuánto se le debe. Esa es la base sobre la que se diseña el producto.

**Ninguna fuente pública verificable documenta la práctica del `fiado`.** Las fuentes públicas (Banco Mundial, Eurostat, NRF/LPRC) son **contexto como máximo, nunca estadística local**, y no se ha realizado ninguna entrevista a dueños de tienda para esta variante. Por eso **las decisiones de alcance que en la fase de exploración dependían de las entrevistas se toman aquí como decisiones de diseño bajo supuesto**, y quedan declaradas como tales:

| Decisión | Criterio que se aplicaría con evidencia | Criterio que se aplica aquí (sin evidencia) |
|---|---|---|
| **Regla 4** — ¿sobrevive la confirmación del cliente? | que los dueños lo pidan | **Se construye la superficie de confirmación.** Es la hipótesis central del proyecto: el cliente ratifica su propia cifra. Si el supuesto falla, el repliegue nombrado es `fiado desglosado` (7,80), que conserva el catálogo y las líneas de cargo y retira la superficie de cliente. |
| **Regla 5** — ¿se anota qué productos? | que los dueños anoten el detalle | **Se construye el catálogo con líneas de cargo.** Es lo que da sentido al desglose que el cliente ratifica; sin él, la confirmación no tiene un artefacto que ratificar. |
| **Regla 6** — ¿se lleva el inventario? | que los dueños lo carry | **`existencias_registradas` se incluye como techo opcional, no como conteo.** Ningún endpoint rechaza un `cargo` por falta de existencias y ninguna regla depende de la cifra, así que su presencia o ausencia no altera ninguna regla del sistema. Es la línea de corte más barata del alcance. |
| **Condición N5** — ¿da el fiado un `dependiente`? | que el hallazgo lo confirme | **La capacidad condicional `confirmation-facilitation` no se añade.** El `dependiente` registra `caja` y el cierre, y el **403 sobre el libro de crédito queda intacto**. Se conserva el diseño de la ruta y su test como trabajo futuro, pero no entra en el alcance. |

**El instrumento de validación existe y no se ha ejecutado.** `evidence-annex.md` conserva el guion revisado (las seis preguntas originales, verbatim, más **N1–N7**), la hoja de captura extendida y la lista de comprobación, para que la validación con campo real pueda ejecutarse más adelante. Sus campos siguen en `PENDIENTE` y **no contienen ninguna cita, cifra ni respuesta**: no hay datos inventados.

**Qué cambia si la validación se ejecuta y contradice el supuesto.** Si la ronda de entrevistas muestra que los dueños no piden la confirmación (Regla 4 vacía), el alcance se reduce a `fiado desglosado` y se retiran la superficie de cliente, las rutas de cliente y los **10 requisitos condicionados**. Esa reducción está ya diseñada y acotada en `design.md` §19. El proyecto no depende de que el supuesto sea cierto para estar bien construido: depende de que la hipótesis esté **declarada**.

## Criterios de éxito

- URL pública HTTPS con `DEBUG=False`, datos sembrados y una cuenta por rol.
- En `/app/posicion`: la ecuación del negocio, la escalera con el estado de confirmación de cada cargo, el cierre del día, las propuestas pendientes y los pagos propuestos.
- En `/app/propuesta/{id}`: el `desglose` de la propuesta y sus dos acciones, **Confirmar** y **Cancelar**.
- En `/app/cliente`: con un `codigo` sembrado, el cliente ve sus cargos **confirmados** desglosados, lo que ya pagó de cada uno y lo que le queda, y puede **proponer un pago** — sin ninguna acción de escribir.
- **Cuatro demostraciones en vivo**: (1) un `cargo` de dos líneas cuyo desglose y suma cuadran, y cuyo `precio_unitario` no cambia al editar el catálogo; (2) un `dependiente` recibe **403** en `/api/v1/clientes/`; (3) el dueño prepara una propuesta, el cliente la ve en la pantalla y la confirma, y el `cargo` queda escrito con su `Confirmacion` y sus líneas **en la misma transacción**; (4) un cliente que debe 8,00 €, 7,00 € y 15,00 € paga 20,00 €, y sus tres cargos quedan en **8/8, 7/7 y 5/15**.
- Repositorio con README y sin secretos; memoria §3.1–§3.8 con el anexo de validación previsto (ejecutado o no, sin datos inventados); defensa de 30 min en vivo.

## Ajustes de alcance

**Aceptables:** suprimir el gráfico de `serie_caja`; suprimir `existencias_registricas` (es un techo opcional y ninguna regla depende de él); suprimir la superficie remota del cliente (el móvil) y dejar la confirmación solo en el mostrador; reducir los datos sembrados; aceptar `fiado desglosado` o `margen` si la validación con campo real lo contradijera.

**No negociables:** el libro append-only; el **403** del `dependiente` sobre el libro de crédito; la vista React consumiendo la API propia en la URL pública; la URL HTTPS con `DEBUG=False` y datos sembrados. Las siete (+1 condicional) son **nuestra elección** dentro del rango de 4 a 8 de la guía.

## Rollback

El alcance de la v2 ya tiene código en el repositorio: el esqueleto Django, el modelo de datos de dieciséis entidades con su migración, la capa de reglas puras y sus tres suites de pruebas. El rollback del código es revertir la rama; el del alcance completo sigue siendo discarding la carpeta del change.

| Componente de la pila | Qué se crearía | Reversión |
| --- | --- | --- |
| **Backend** | Proyecto Django con apps, migraciones, DRF y suite de pruebas | Eliminar el directorio; no hay datos de producción que migrar |
| **Frontend** | Aplicación React + TS + Vite con tres rutas | Eliminar el directorio del frontend |
| **Despliegue** | Servicio web en Render + base de datos en Neon | Eliminar el servicio y la base; ambos gratuitos y sin datos de producción |

El libro no se destruye: es append-only, así que un rollback no corrompe un registro.

## Anexos

`exploration.md` — registro de exploración: T1–T7, la clasificación evidencia / diseño abandonado, el mapa de herencia y los ítems abiertos. **Es el registro histórico de cómo se tomaron las decisiones, y describe el modelo v1**: el rediseño v2 no lo reescribe, lo que lo convierte en historia y no en contrato. · `evidence-annex.md` — instrumento de validación previsto y **no ejecutado**: guion, hoja de captura, seguimiento de captación y lista de decisión, todos sus campos en `PENDIENTE` y sin ninguna cita, cifra ni respuesta. · `redesign-brief.md` — el encargo del rediseño v2 y el mapa de qué cambiar. · `tienda-barrio/` — historial intacto, no modificado.
