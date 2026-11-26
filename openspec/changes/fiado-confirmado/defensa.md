# Defensa — 30 minutos en vivo

> **Qué se demuestra:** las cuatro demostraciones de los criterios de éxito, en el
> despliegue público, contra la URL real. **Una sola aplicación, un solo origen.**
>
> **Antes de empezar:** comprueba que el despliegue ha sembrado. Si `/health/` responde
> `{"status": "ok"}` pero las cuentas no entran, **el seed todavía no ha corrido**: el
> build siembra al final, y un deploy recién salido tarda. Un e2e en rojo a mitad de un
> deploy con un 403 en el `dependiente` es **el seed a medias**, no un defecto.

**URL:** <https://fiado-confirmado.onrender.com>
**Cuentas:** `dueno@tienda.test`, `dependiente@tienda.test` y `ana` — contraseña
`tienda-demo-2026` para las tres.

---

## 0:00 — 0:02 · La apertura (60 segundos)

> «El `fiado` vive hoy en la cabeza del dueño y en un cuaderno. El problema no es solo
> que no sepa cuánto le deben: es que **nadie sabe si la deuda es real**. Un cuaderno no
> tiene antigüedad, ni límite, ni regla.
>
> Este producto hace tres cosas. **La tienda pregunta.** **La clienta contesta, desde su
> propia cuenta.** Y **el cargo existe solo después de que ella acepta** — antes de eso
> no hay deuda. Todo lo demás se deriva de ahí: el saldo, la antigüedad, la suspensión,
> la posición real de la tienda.
>
> Lo voy a enseñar funcionando, en la URL pública. Son cuatro demostraciones.»

---

## 0:02 — 0:18 · Las cuatro demostraciones

### Demo 1 · El desglose cuadra, y el precio es una foto (4 min)

**Qué demuestra:** el importe de un `cargo` es **exactamente** la suma de sus líneas, y el
`precio_unitario` es una **instantánea**: editar el catálogo después no reescribe lo
guardado (`IC-02`, `IC-08`).

1. Entra como **`dueno@tienda.test`** → `/app/posicion` → **Tablero**.
2. Baja a **«Preparar una propuesta»**:
   - **Cliente** → *Ana*
   - **Producto** → *Jamón* (6,90) · **Cantidad** → `1`
   - **Producto** → *Lechuga* (1,10) · **Cantidad** → `1`
   - **Total (opcional)** → déjalo vacío: lo calcula el servidor
3. **Preparar**. Se abre `/app/propuesta/{id}`: el **desglose** y las dos acciones,
   **Confirmar** y **Cancelar**.
4. **Dilo antes de confirmar:** «las dos líneas suman 8,00, y ese 8,00 es el que va a
   quedar guardado».
5. Vuelve al **Tablero**, edita el catálogo: **Jamón** → `9,90`. Guarda.
6. **Dilo:** «el precio **guardado** sigue siendo 6,90. El catálogo cambió; la línea es
   una foto del momento en que se preparó».
7. **Vuelve a `/app/cuenta` con `ana` y acepta** — eso es la demo 3, y suelta con ella.

> **Si preguntan por qué el precio se congela:** es lo que hace que una deuda antigua
> siga siendo la que se pactó. Si el precio se actualizara, cambiar el catálogo reescribiría
> la historia del libro.

### Demo 2 · El `dependiente` ve el libro, pero no la política (3 min)

**Qué demuestra:** el `dependiente` **lee** el libro de crédito con un **esquema
reducido** (el alias y las deudas, ninguna cifra de la política), y la **política** del
dueño le responde **403 total, sin datos** (`CAC-02`, `§7.1`).

1. Sal de la sesión del dueño. Entra como **`dependiente@tienda.test`**.
2. **En el navegador, en la barra de direcciones:**
   `https://fiado-confirmado.onrender.com/api/v1/catalogo/` → **403**, y el cuerpo es
   `{"codigo_error": "permiso_insuficiente", "detail": "."}` — ni un alias, ni un
   identificador, ni un número.
3. Ahora: `https://fiado-confirmado.onrender.com/api/v1/clientes/` → **200**, y el cuerpo
   es una lista con el **alias** de cada clienta y su **deuda**. **Nada más**: no hay
   `credit_limit`, no hay antigüedad, no hay `caja`.
4. **Dilo:** «el mismo endpoint, dos respuestas. El `dependiente` lee el libro porque
   **cobrar una deuda exige ver la deuda**, pero la **política** —el límite, la
   suspensión— no es suya».

> **Si preguntan por el 403 y no el 200:** antes de que la puerta N5 se abriera, el
> `dependiente` no alcanzaba el libro. La decisión la tomó el propietario y es una
> **decisión de producto bajo una hipótesis declarada**, no una regla del libro.

### Demo 3 · La clienta acepta, y el cargo aparece (4 min)

**Qué demuestra:** el cargo —con su `Confirmacion` y sus líneas— **se escribe en una
sola transacción**, y solo cuando ella acepta (`CC-01`, `IC-03`).

1. Sal de la sesión del `dependiente`. Entra como **`dueno@tienda.test`**.
2. En el **Tablero**, mira la **escalera**: Ana aparece **sin cargo nuevo**. La
   propuesta está `pendiente` y **no mueve nada**.
3. Abre otra pestaña (o una ventana privada) y entra como **`ana`** →
   `https://fiado-confirmado.onrender.com/app/cuenta` → **«Tus fiados»**.
4. **«Sí, acepto este fiado»**.
5. Vuelve a la pestaña del **dueño** y recarga el **Tablero**: el cargo ha aparecido,
   con sus dos líneas.
6. **Dilo:** «aceptó ella, y en la misma transacción se escribieron las cuatro cosas:
   el `LedgerEntry` del cargo, sus dos `CargoLinea`, la `Confirmacion` y el
   `confirmed_at`. O entram las cuatro, o no entra ninguna».

> **Si preguntan por qué la clienta no ve «la pantalla»:** la pantalla
> `/app/propuesta/{id}` es **del local**. La clienta responde **desde su cuenta**, que es
> lo que hace que la respuesta sea de ella y no del dueño. En una tienda con dos
> mostradores, el mismo `fiado` lo ven los dos: la figura es del local, la respuesta es
> de la persona.

### Demo 4 · El pago se reparte FIFO (5 min)

**Qué demuestra:** un pago se imputa **al cargo más antiguo primero**, y **nunca excede
la deuda que salda**: el exceso es cambio y **no entra en el libro** (`PA-02`, `ADR-26`).

1. Como **`dueno@tienda.test`**, prepara **tres** propuestas, **en este orden** (el orden
   es la antigüedad):

   | # | Líneas | Total |
   |---|---|---|
   | 1 | *Jamón* 6,90 + *Lechuga* 1,10 | **8,00** |
   | 2 | *Queso* 4,75 + *Tomates* 2,25 | **7,00** |
   | 3 | *Gambas* 12,50 + *Café* 2,50 | **15,00** |

2. Como **`ana`**, acepta las tres en **«Tus fiados»**.
3. Como **`ana`**, en **«Tus cargos»** → **«Proponer un pago»** → importe **20,00** →
   tienda **Tienda de demostración** → **Proponer**.
4. Como **`dueno@tienda.test`**, en el **Tablero**, la sección de **pagos propuestos**:
   **validar**.
5. Como **`ana`**, en **«Tus cargos»**: sus tres cargos quedan en **8/8, 7/7 y 5/15**.
6. **Dilo:** «20,00 contra 30,00 de deuda. El pago salda **el más viejo primero**: los
   8,00 quedan pagados, los 7,00 quedan pagados, y de los 15,00 quedan 5,00. Y el
   **exceso nunca entra**: un pago no puede crear crédito a favor, porque el dueño
   devuelve el cambio».

---

## 0:18 — 0:23 · La arquitectura en cinco minutos

1. **Una app, una base, un origen.** Django 5.2 + DRF, React + TypeScript + Vite
   servido por WhiteNoise **desde el mismo origen** que la API. Sin segundo host, sin
   CORS, sin worker, sin Redis. **PostgreSQL 16** (Neon en producción: el PostgreSQL
   gratis de Render caduca a los 30 días).
2. **El libro es append-only.** Ni `UPDATE` ni `DELETE` sobre `LedgerEntry`,
   `CargoLinea`, `Confirmacion`, `PropuestaLinea` ni `ImputacionPago`. Las correcciones
   son filas nuevas.
3. **Nada derivado se guarda.** Ni saldo, ni antigüedad, ni tramos, ni estado de
   confirmación, ni crédito a favor. Cada uno es una pregunta que se responde leyendo
   las filas.
4. **Las reglas son funciones puras**, en `backend/tienda/domain/`, sin ORM y sin HTTP. Se
   prueban **sin base de datos** — el propio `pytest-django` impide que una prueba sin
   `@pytest.mark.django_db` toque la base, así que la propiedad no se afirma: **se
   impone**.
5. **Y lo que el proyecto NO afirma.** La base del conocimiento es una **hipótesis de
   diseño declarada**: no se hizo ninguna entrevista a dueños de tienda, y no se va a
   hacer. La ronda se cerró el 2026-11-25. Eso deja sin medir una cosa —que una tienda no
   dé crédito a quien no tiene cuenta— y **lo decimos en vez de disimularlo**.

---

## 0:23 — 0:30 · Las preguntas del tribunal

| # | Pregunta | Respuesta en una línea |
|---|---|---|
| 1 | «¿Por qué no una libreta o un Excel?» | El cuaderno no tiene antigüedad, ni límite, ni regla, y muere con el dueño; el Excel puede enumerar saldos pero no puede *decidir*. |
| 2 | «¿No es esto una tabla de saldos?» | Un saldo es un número; esto es un libro con saldos **derivados**, antigüedad por fecha de cargo, y una **puerta**: sin la respuesta de la clienta no hay deuda. |
| 3 | «¿Cómo garantizáis que una clienta con 40 días no recibe más fiado?» | La regla se evalúa **en el servidor, dentro de la misma transacción**: la suspensión se lee en la lectura y el cargo se escribe en la misma operación. |
| 4 | «¿Y la protección de datos? Guardáis deudas.» | Se guarda un alias, un teléfono opcional e importes: sin DNI, sin dirección, y **la cuenta es de la clienta**. Lo que no se guarda es lo derivado. |
| 5 | «¿Cómo se calcula la posición real y por qué me fiáis?» | Es `caja + fiado pendiente`, una suma sobre asientos inmutables. Y un pago **no la altera**: sube la `caja` y baja el fiado pendiente. |
| 6 | «¿Por qué no incluye producto, precio y punto de venta?» | Alcance deliberado: el MVP responde a la pregunta del dinero. El producto y el precio **sí** están —en el desglose y en la instantánea—, pero el punto de venta no. |
| 7 | «Si la clienta paga, ¿no sube la posición?» | No: `posicion_real` es `caja + fiado pendiente`. Un pago **sube la `caja`** y **baja el fiado pendiente**. Lo que cambia es la composición, no la suma. |
| 8 | «¿Y si la clienta no contesta?» | No hay cargo. La figura se queda `pendiente` y **no mueve nada** — y la tienda puede cancelarla. |
| 9 | «¿Y si la tienda quiere fiarle más de su límite?» | No puede: el límite es una regla del servidor, no un campo que el dueño escriba en el momento. Para **subirlo** hay que cambiar la política del vínculo, y eso se ve. |
| 10 | «¿Qué harías con más tiempo?» | El techo de existencias, que está cortado y con la regla ya escrita en el dominio; y un **traspaso entre dueños**, que hoy no existe. |

> **Si no sabéis una respuesta:** decidlo. «No lo sé, y está anotado en el registro del
> proyecto» es una respuesta mejor que inventar, y el registro
> (`openspec/changes/fiado-confirmado/state.yaml`) existe exactamente para eso.

---

## Anexo · Si algo falla

| Síntoma | Qué es |
|---|---|
| `/health/` responde pero las cuentas no entran | **el seed del deploy todavía no ha corrido**. Espera y vuelve: el build siembra al final. |
| El `dependiente` recibe 403 en `/api/v1/clientes/` | **idem**: su membresía en la tienda la crea el seed. Espera. |
| El `dependiente` recibe 200 en `/api/v1/clientes/` pero **no** ve a Ana | Ana es clienta de la tienda **de demostración**; si no aparece, el seed no ha terminado. |
| Una demostración se rompe a mitad | **Ctrl+C y sigue con la siguiente**: las cuatro son independientes, y la 2 y la 4 no dependen de la 1 ni de la 3. |
