# Propuesta de proyecto PFM — `fiado`: La libreta y la caja

**Estado: borrador para validación del equipo docente. Evidencia de entrevistas: pendiente.**

## Problema

El fiado —lo que el cliente se lleva y paga después— vive en la cabeza del dueño y en un cuaderno. El dueño no puede sumar lo que le deben, ni saber desde cuándo, ni impedir que el fiado crezca, ni responder «¿cuánto dinero es realmente mío?» al cerrar. De ahí: deudas que nunca se anulan y una caja que no explica el negocio: el dinero entregado no está dentro. El cuaderno no guarda antigüedad, ni límite, ni regla; y su dinero real —`caja` más lo que le deben— nunca se calcula.

## Usuarios y roles

- **Dueño**: todo —clientes, crédito, cargos y pagos, antigüedad, suspensión, posición real, cierre, usuarios.
- **Dependiente**: registra caja y cierre; **el libro de crédito le devuelve 403**, sin alias ni saldos.
- Razón: el cuaderno se queda en el cajón. Matriz completa en los anexos.

## Alcance mínimo — 5 funcionalidades

1. **Cuentas y dos roles.** *AC:* el `dependiente` recibe 403 en `/api/v1/clientes/`; `/api/v1/posicion/` no expone alias.
2. **Libro de clientes y crédito.** *AC:* con límite de 20 €, un cargo de 25 € se rechaza y no crea asiento.
3. **Cargos y pagos (la libreta).** *AC:* un pago de 30 € reduce el saldo en 30 €, salda primero el cargo más antiguo y sube la `caja` en 30 €.
4. **Antigüedad y suspensión automática.** *AC:* un cargo impagado de 45 días suspende al cliente sin acción humana.
5. **Posición real y cierre del día.** *AC:* un `pago` sube la `caja` en su importe y **no** altera `posicion_real`; el cierre guarda la desviación.

## Entidades de datos

| Entidad | Campos y relaciones |
| --- | --- |
| `Shop` | `opening_cash, currency` — 1—N todas |
| `Customer` | `alias, credit_limit, status` — 1—N `LedgerEntry` |
| `LedgerEntry` | `kind, amount, date, author` — N—1 `Customer` |
| `CashMovement` | `kind, amount, date, author` — N—1 `User` |
| `DayClose` | `date, expected, counted` — N—1 `User` |

Más el `User` de Django; sin columna de saldo: todo se deriva.

## Vista React

`/app/posicion` — «La posición real», sin tablas: (1) **ecuación del negocio** (`Caja` 412,35 € + `Fiado pendiente` 268,90 € = **`Posición real` 681,25 €**); (2) **escalera de riesgos**: deudores por antigüedad, con cinta, límite y estado; (3) **área de dos series**: `Caja` abajo y `Posición real` arriba; **la distancia entre ambas es el fiado pendiente**, el dinero ya entregado; (4) **cierre de hoy** (`Esperado`/`Contado`/`Desviación`). Las cifras son de la semilla, no de entrevistas.

Consume `GET /api/v1/posicion/` de la API propia, mismo origen (sesión + `X-CSRFToken`, sin CORS). **Demo:** un cliente con cargos de 20,00 € (45 días) y 10,00 € (10 días) está `Suspendido`; al registrar un `pago` de 20,00 €, la imputación liquida el cargo de 45 días, la antigüedad máxima pasa a 10 días y el cliente vuelve a `Activo`. La `caja` sube 20,00 € y la `Posición real` **no cambia**: el dinero se convierte, no se crea ni se pierde.

## Enfoque técnico

Django 5.2 + DRF, sesión y CSRF; roles por grupos y mixins, en servidor; **reglas de dominio como funciones puras sin ORM** (`allocate_payments`, `real_position`) con pruebas unitarias; React + TS + Vite servido por Django con WhiteNoise (un origen, sin CORS); Render + Neon free; `DEBUG=False`; secretos en el entorno.

## Fuera de alcance

Punto de venta, productos, precios y recibos; código de barras; portal de cliente y pagos en línea; cobranza, intereses y recordatorios; facturación fiscal; compras a proveedores; varias sucursales; subidas de ficheros; correo y SMS; móvil.

## Evidencia (PENDIENTE)

Tres entrevistas semiestructuradas a dueños de tienda (guion en los anexos), con notas anonimizadas, citas literales y canal de captación.

**Decisión, antes de codificar:** si el crédito no es práctica real, el proyecto cambia a `margen` y la propuesta queda invalidada; si el dueño no anota nada, el MVP se reduce a un cargo de un solo toque.

Fuentes verificadas, **solo contexto y nunca estadística local**: Banco Mundial, Eurostat y NRF/LPRC (cifras y límites en `submission-notes.md`). **Ninguna fuente verificable documenta el fiado**: deben establecerlo las entrevistas.

## Criterios de éxito

- URL pública HTTPS con datos sembrados y una cuenta por rol.
- Tres demostraciones en vivo: un cargo por encima del límite rechazado; la suspensión automática de una deuda de 45 días; y el `pago` de 20,00 € que la liquida y devuelve al cliente a `Activo` sin alterar la `Posición real`.
- Repositorio con README y sin secretos; memoria §3.1–§3.8 con anexo de entrevistas; defensa de 30 min en vivo.

## Ajustes de alcance

**Aceptables:** suprimir el cierre del día (cuatro funcionalidades); aceptar `margen` en lugar de `fiado`; reducir los datos sembrados.

**No negociables:** los dos roles con un 403 real en servidor; la vista React consumiendo la API propia en la URL pública; la URL HTTPS con `DEBUG=False` y datos sembrados. Las cinco funcionalidades son **nuestra elección** dentro del rango de 4 a 8 de la guía.

## Rollback

Nada construido: el repositorio solo contiene `.git`. Si se rechaza, se pierden unas 8 h de exploración y entrevistas; no hay código, historial ni despliegue que revertir. El repliegue es `margen`, que traslada 1:1 su arquitectura. Pila tocada: **backend** (Django nuevo), **frontend** (app React nueva), **despliegue** (Render + Neon nuevos): todo creación, el rollback es borrarlo.

## Anexos

`submission-notes.md` (fuentes, criterios, ajustes, técnico, rollback, tribunal, permisos) · `acceptance-criteria.md` (criterios por funcionalidad) · `evidence-annex.md` (plantilla de entrevistas).
