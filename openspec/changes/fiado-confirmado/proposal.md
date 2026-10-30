# Propuesta de proyecto PFM — `fiado confirmado`: el fiado que ratifica el cliente

**Estado: para validación del equipo docente. Base del conocimiento: hipótesis de diseño declarada sobre el contexto del `fiado`; sin evidencia de campo. Ver «Base del conocimiento».**
**Este cambio (`fiado-confirmado`) sustituye al alcance `fiado` de `tienda-barrio`**, que queda en disco como historial: su propuesta, especificaciones y diseño se abandonan, no se modifican.

## Problema

El fiado —lo que el cliente se lleva y paga después— vive en la cabeza del dueño y en un cuaderno. El problema de hoy no es solo que el dueño no sepa cuánto le deben: es que **las dos partes no tienen la misma cifra**. El dueño recuerda un importe, el cliente recuerda otro, y el cuaderno no puede zanjarlo porque no tiene regla, no tiene límite y no tiene el testimonio de un tercero. De ahí: deudas que nunca se anulan y una caja que no explica el negocio —el dinero entregado no está dentro.

El contexto lo impone: una tienda de 30–120 m², con 1–3 personas y 100–400 transacciones al día, mayoritariamente en efectivo, en la que **el dueño es el activo**: conoce al cliente por su nombre y eso es su ventaja competitiva. Ningún producto que exija disciplina nueva (contar, categorizar, registrar ventas) se usará; solo vale lo que se apoya en un gesto que la tienda ya hace.

## Usuarios y roles

| Principal | Qué es | Qué puede |
| --- | --- | --- |
| `dueño` | Usuario Django, grupo `dueno` | Todo: clientes, crédito, `cargo`, `pago`, antigüedad, suspensión, `posición real`, cierre, `codigo`, resolución de disputas. |
| `dependiente` | Usuario Django, grupo `dependiente` | Registra `caja` y cierre del día. **El libro de crédito le devuelve 403**, sin alias ni saldos. *Una capacidad estrecha y condicional:* presentar al cliente un `cargo` pendiente y recibir su confirmación, sin ver lista, saldo ni antigüedad. |
| `cliente` | **No es un rol.** No es grupo, ni `User`, ni sesión: es una **credencial portadora (`codigo`) acotada a un único `Customer`**, resuelta en el servidor | Ver sus cargos **confirmados** en detalle, ver sus cargos pendientes como fila resumen, **confirmar** y **disputar** los suyos. Nada más: ni la `caja`, ni la `posición real`, ni otro cliente. |

**Invariante de credenciales:** ningún ámbito de cliente puede existir dentro de una sesión de personal, y ninguna sesión de personal puede promoverse a ámbito de cliente. Por eso la superficie del cliente **no tiene sesión**: la credencial se presenta en cada petición. Matriz completa en los anexos.

## Alcance mínimo — 7 funcionalidades (+1 condicional)

1. **Cuentas, roles y credenciales del cliente** (`client-accounts-and-credentials`). *AC:* `dependiente@tienda.test` recibe **403** en `/api/v1/clientes/` y ningún `codigo` aparece en su payload; el `dueño` emite un `codigo` único en la tienda y rotable.
2. **Catálogo de productos y precios** (`product-catalogue`). *AC:* un `Producto` sembrado a 1,20 € lo devuelve la API del catálogo y se ofrece como precio por defecto de una línea de cargo; el catálogo solo contiene los productos aptos para fiado.
3. **Cargos con líneas de producto** (`itemised-charges`). *AC:* un `cargo` de dos líneas que suma 6,40 € crea dos `CargoLinea` y un `LedgerEntry` de 6,40 €; cambiar después el precio del catálogo no toca el `precio_unitario` almacenado.
4. **Pagos, notas de crédito, antigüedad y suspensión** (`payments-and-ageing`). *AC:* un `pago` de 30 € salda primero el cargo más antiguo y baja `antiguedad_max_dias` de 45 a 10; un cargo impagado de 45 días suspende al cliente sin acción humana, y un cargo nuevo se rechaza con **422** sin crear fila.
5. **Confirmación y disputa del cliente** (`client-confirmation`). *AC:* con un `codigo` válido, el cliente confirma un cargo pendiente; la API devuelve `confirmado_en` y el estado pasa a `confirmado`; el detalle de los cargos **confirmados** aparece en su estado de cuenta; una sesión de `dependiente` no alcanza ningún endpoint de cliente.
6. **Disputas y corrección por `nota de crédito`** (`dispute-resolution`). *AC:* un cargo en disputa de 6,40 € con `importe_reclamado` 4,20 €, resuelto por el `dueño` con una `nota de crédito` de 2,20 €, deja un pendiente de 4,20 € con la fila del `cargo` intacta; una disputa rechazada deja el pendiente en 6,40 € y el estado en `en_disputa`.
7. **Posición real, cierre del día y existencias registradas** (`cash-position`). *AC:* un `pago` de 30 € sube la `caja` en 30 € y **no** altera `posicion_real`; el cierre guarda `esperado`, `contado` y `desviacion`; `existencias_registradas` se devuelve con su calificador de techo y **ningún** endpoint rechaza un `cargo` por falta de existencias.
8. **Condicional — facilitar la confirmación por el `dependiente`** (`confirmation-facilitation`). El `dependiente` puede presentar un cargo pendiente y recibir la confirmación del cliente, registrando `facilitado_por`, y no alcanza lista, saldo ni antigüedad. **Solo se añade si la entrevista N5 muestra que el ayudante da el fiado**; si no, el 403 queda intacto.

Capacidades **modificadas**: ninguna. Las especificaciones de `tienda-barrio` quedan como historial y no se modifican; este change produce especificaciones nuevas.

## Entidades de datos

| Entidad | Campos y relaciones |
| --- | --- |
| `Producto` | `id, nombre, precio, unidad, activo` — vocabulario del libro; solo los productos aptos para fiado |
| `CargoLinea` | `id, FK cargo, FK producto, cantidad, precio_unitario, total` — hija de un `cargo`; `precio_unitario` es una **instantánea** del precio del momento |
| `Confirmacion` | `id, FK cargo, estado (`confirmado` \| `en_disputa`), importe_reclamado, nota, confirmado_en, origen, facilitado_por` — solo se añade; nunca se actualiza ni se borra |
| `Customer` | `alias, credit_limit, status, suspended_reason` + `codigo` (nuevo, único en la tienda) — 1—N `LedgerEntry` |
| `Shop` | `opening_cash, currency` — 1—N todas |
| `LedgerEntry` | `kind, amount, date, author` — N—1 `Customer` |
| `CashMovement` | `kind, amount, date, author` — N—1 `User` |
| `DayClose` | `date, expected, counted` — N—1 `User` |

Más el `User` de Django.

**Invariantes:**
- `LedgerEntry.amount == Σ CargoLinea.total`, comprobado en el servidor dentro de la transacción de escritura.
- **No se almacena nada derivado**: ni saldo, ni antigüedad, ni estado de confirmación. El estado efectivo de un `cargo` se deriva de su última `Confirmacion`; los tramos `vigente` / `envejecido` / `viejo` / `cronico` se derivan de la fecha del cargo.
- El libro es **append-only**: sin `UPDATE` ni `DELETE`. Las correcciones se hacen **añadiendo** una `nota de crédito`, nunca editando.

## Las dos superficies

Un solo bundle Vite, un solo origen, dos modos de credencial.

| Superficie | Quién | Credencial | Contenido |
| --- | --- | --- | --- |
| `/app/posicion` | `dueño` | Sesión Django + `X-CSRFToken` | La ecuación del negocio (`caja + Σ pendiente = posición real`), la escalera de riesgos con cintas de antigüedad y el estado de cada cargo (`confirmado` / `sin_confirmar` / `en_disputa`), y el cierre del día. |
| `/app/cliente` | `cliente` | `codigo` presentado por petición | **Confirmado**: el fiado desglosado que el cliente ha ratificado (producto, cantidad, precio, fecha y hora de la confirmación). **Sin confirmar**: una fila resumen (fecha, importe) con la acción **Confirmar**; el desglose de un cargo sin confirmar aparece **solo dentro** de esa acción. |

La confirmación ocurre **en el mostrador, sobre el propio dispositivo de la tienda**, y esa es la superficie principal: una ratificación que espera a que el cliente llegue a casa no se produce. El móvil del cliente es la secundaria, con la misma credencial y la misma URL.

## Enfoque técnico

Django 5.2 + DRF; **sesión + CSRF** en la superficie de personal y **ninguna sesión** en la del cliente; reglas de dominio como **funciones puras sin ORM** (`allocate_payments`, `bucket_of`, `evaluate_customer`, `real_position`, `estado_cargo`, `confirmacion_efectiva`) con pruebas unitarias; React + TS + Vite servido por Django con **WhiteNoise** (un origen, sin CORS); Render + Neon free; `DEBUG=False`; secretos solo en el entorno. La semilla se amplía con el catálogo, las líneas de cargo, un `codigo` por cliente, un cargo en disputa y varios cargos confirmados.

## El precio del alcance, en abierto

Con los mismos pesos de la rúbrica (25 / 20 / 15 / 15 / 15 / 10), el alcance nuevo **no es la mejor variante por puntuación**:

| Variante | Puntuación /10 |
| --- | --- |
| `fiado` (anterior) | 8,15 |
| `fiado desglosado` | 7,80 |
| `margen` | 7,70 |
| **`fiado confirmado` (este)** | **7,45** |

Toda la diferencia está en **encaje de alcance (−2)** y **riesgo técnico (−1)**: siete funcionalidades en vez de cinco, un tercer tipo de principal, una segunda superficie, un segundo mecanismo de credencial, tres entidades nuevas y una máquina de estados de disputa. El proyecto **no se defiende como «mejor englobado»**: se defiende porque ataca un dolor que el alcance anterior no tocaba, porque el mecanismo es nuevo, porque el alcance está **topado** y porque la decisión la toma la evidencia, no el gusto.

**Dos líneas de corte, declaradas por adelantado:**

1. El gráfico de `serie_caja` de 30 días (un elemento React, no una funcionalidad).
2. `existencias_registradas` — se incluye como techo opcional, no como conteo. Ninguna regla, precio, límite o suspensión depende de la cifra y ningún endpoint rechaza un `cargo` por falta de existencias, así que retirarla no cambia ninguna regla del sistema.

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
| App móvil nativa, escaneo de código de barras o QR | La credencial se teclea; la superficie es una página web. |
| Cuentas de cliente con contraseña, autorregistro, restablecimiento | El cliente tiene una **credencial acotada**, no una cuenta. |
| Editar o borrar un `cargo`, una `Confirmacion` o cualquier asiento | Estructuralmente imposible: el libro es append-only y la API no expone `PUT` / `PATCH` / `DELETE`. |
| Cobranza, intereses, scoring, decisiones automáticas | — |
| Facturación fiscal, varios comercios, multi-sucursal, SaaS | — |
| Subida de ficheros, fotos de la `libreta` | — |
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
| **Condición N5** — ¿da el fiado un `dependiente`? | que el hallazgo lo confirme | **La capacidad condicional `confirmation-facilitation` no se añade.** El `dependiente` registra `caja` y el cierre, y el **403 sobre el libro de crédito queda intacto**. Se conserva el diseño de la ruta y su测试 como trabajo futuro, pero no entra en el alcance. |

**El instrumento de validación existe y no se ha ejecutado.** `evidence-annex.md` conserva el guion revisado (las seis preguntas originales, verbatim, más **N1–N7**), la hoja de captura extendida y la lista de comprobación, para que la validación con campo real pueda ejecutarse más adelante. Sus campos siguen en `PENDIENTE` y **no contienen ninguna cita, cifra ni respuesta**: no hay datos inventados.

**Qué cambia si la validación se ejecuta y contradice el supuesto.** Si la ronda de entrevistas muestra que los dueños no piden la confirmación (Regla 4 vacía), el alcance se reduce a `fiado desglosado` y se retiran la superficie de cliente, las rutas de cliente y los 13 requisitos condicionados. Esa reducción está ya diseñada y acotada en `design.md` §19. El proyecto no depende de que el supuesto sea cierto para estar bien construido: depende de que la hipótesis esté **declarada**.

## Criterios de éxito

- URL pública HTTPS con `DEBUG=False`, datos sembrados y una cuenta por rol.
- En `/app/posicion`: la ecuación del negocio, la escalera con el estado de confirmación de cada cargo y el cierre del día.
- En `/app/cliente`: con un `codigo` sembrado, el cliente ve su cargo confirmado **desglosado** (producto, cantidad, precio, fecha y hora) y su cargo pendiente como **fila resumen** con la acción **Confirmar**, cuyo detalle se revela dentro de la acción.
- **Cuatro demostraciones en vivo**: (1) un `cargo` de dos líneas cuyo desglose y suma cuadran, y cuyo `precio_unitario` no cambia al editar el catálogo; (2) un `dependiente` recibe **403** en `/api/v1/clientes/`; (3) el cliente confirma un cargo y la confirmación queda registrada con `confirmado_en`; (4) una disputa de 6,40 € resuelta con una `nota de crédito` de 2,20 € deja un pendiente de 4,20 € sin alterar la fila del `cargo`.
- Repositorio con README y sin secretos; memoria §3.1–§3.8 con el anexo de validación previsto (ejecutado o no, sin datos inventados); defensa de 30 min en vivo.

## Ajustes de alcance

**Aceptables:** suprimir el gráfico de `serie_caja`; suprimir `existencias_registradas` (es un techo opcional y ninguna regla depende de él); suprimir la superficie remota del cliente (el móvil) y dejar la confirmación solo en el mostrador; reducir los datos sembrados; aceptar `fiado desglosado` o `margen` si la validación con campo real lo contradijera.

**No negociables:** el libro append-only; el **403** del `dependiente` sobre el libro de crédito; la vista React consumiendo la API propia en la URL pública; la URL HTTPS con `DEBUG=False` y datos sembrados. Las siete (+1 condicional) son **nuestra elección** dentro del rango de 4 a 8 de la guía.

## Rollback

Nada construido: el repositorio solo contiene artefactos de planificación. Si esta propuesta se rechaza, el rollback es **borrar la carpeta del change `fiado-confirmado`**; el proyecto anterior (`tienda-barrio`) permanece en disco, sin tocar. No hay código, historial ni despliegue que revertir.

| Componente de la pila | Qué se crearía | Reversión |
| --- | --- | --- |
| **Backend** | Proyecto Django nuevo (proyecto, apps, migraciones, DRF, suite de pruebas) | Eliminar el directorio; no hay datos que migrar |
| **Frontend** | Aplicación React + TS + Vite nueva, con dos rutas | Eliminar el directorio del frontend |
| **Despliegue** | Servicio web nuevo en Render + base de datos nueva en Neon | Eliminar el servicio y la base; ambos gratuitos y sin datos de producción |

Todos son **creación**, no modificación: no queda ningún componente existente en estado incoherente.

## Anexos

`exploration.md` — registro de exploración: T1–T7, la clasificación evidencia / diseño abandonado, el mapa de herencia y los ítems abiertos. · `evidence-annex.md` — instrumento de validación previsto y **no ejecutado**: guion, hoja de captura, seguimiento de captación y lista de decisión, todos sus campos en `PENDIENTE` y sin ninguna cita, cifra ni respuesta. · `tienda-barrio/` — historial intacto, no modificado.
