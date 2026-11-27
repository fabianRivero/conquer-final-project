# Defensa — 30 minutos en vivo

> **Qué se demuestra:** las cuatro demostraciones de los criterios de éxito, en el
> despliegue público, contra la URL real. **Una sola aplicación, un solo origen.**
>
> **Este guion está ENSAYADO**: cada paso se ejecutó contra el despliegue y se
> comprobó su resultado. Los números que aparecen aquí son los que produce el
> demo sembrado, no los que uno supone.
>
> **Antes de empezar:** comprueba que el despliegue ha sembrado. Si `/health/` responde
> `{"status": "ok"}` pero las cuentas no entran, **el seed todavía no ha corrido**: el
> build siembra al final, y un deploy recién salido tarda. Un e2e en rojo a mitad de
> un deploy con un 403 en el `dependiente` es **el seed a medias**, no un defecto.

**URL:** <https://fiado-confirmado.onrender.com>
**Cuentas:** `dueno@tienda.test`, `dependiente@tienda.test` y `ana` — contraseña
`tienda-demo-2026` para las tres.

**Lo que tiene el demo sembrado:** una tienda, treinta productos, **Ana** como clienta
de confianza con un límite de 100 €, y **tres deudas** — 8,00 €, 7,00 € y 15,00 €, **de más antigua a más
reciente** — más una propuesta pendiente de 2,40 € y otra rechazada de 4,30 €.

> **El orden es lo que importa, no los días exactos:** el aging se cuenta por días
> de calendario y el reloj lo mueve, pero las tres deudas keeps su antigüedad
> relativa, y el FIFO la respeta.

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

**Qué demuestra:** el importe de un `cargo` es **exactamente** la suma de sus líneas
(`IC-02`), y el `precio_unitario` es una **instantánea** (`IC-08`, `CC-06`).

1. Entra como **`dueno@tienda.test`** → `/app/posicion` → **Tablero**.
2. En **«La ecuacion»**, di la de Ana: **30,00 €** de fiado pendiente, y una
   `posicion_real` de 180,00 € con 150,00 € en la caja.
3. Ahora entra como **`ana`** → `https://fiado-confirmado.onrender.com/app/cuenta` →
   **«Tus cargos»**. Sus tres cargos: **8,00 €**, **7,00 €** y **15,00 €**.
4. Abre el de **8,00 €**. Sus dos líneas: **Café molido 1 × 3,50 € = 3,50 €** y
   **Vino 1 × 4,50 € = 4,50 €**.
5. **Dilo:** «las dos líneas suman 8,00, que es exactamente el importe del cargo. Y el
   servidor lo **comprueba** al escribirlo: un cargo cuyo importe no sea la suma de sus
   líneas se rechaza. El desglose no es decorativo, es obligatorio».
6. **Ahora el precio.** El catálogo de hoy tiene el **Café molido a 3,20 €**. Esa línea
   —**la más vieja de las tres**— lo tiene a **3,50 €**.
7. **Dilo:** «el precio de una línea es una **foto** del momento en que se pactó. El
   catálogo cambió después, y por eso el demo trae esa deuda vieja con el precio viejo.
   **Cambiar el catálogo no reescribe la historia del libro.**»

> **Si preguntan cómo se demuestra eso sin editar el catálogo:** no hace falta editarlo.
> El catálogo de este producto es **de solo lectura** — viene de la semilla y no tiene
> ruta de escritura, por diseño (PC-03). La demostración es más fuerte así: no es que
> «cambiamos el precio y la línea no se movió», es que **el precio de la línea y el del
> catálogo son distintos, y la línea conserva el suyo**.

### Demo 2 · El `dependiente` ve el libro, pero no la política (3 min)

**Qué demuestra:** el `dependiente` **lee** el libro de crédito con un **esquema
reducido** (el alias y las deudas, ninguna cifra de la política), y la **política** del
dueño le responde **403 total, sin datos** (`CAC-02`, `§7.1`).

1. Sal de la sesión de Ana. Entra como **`dependiente@tienda.test`**.
2. **En el navegador, en la barra de direcciones:**
   `https://fiado-confirmado.onrender.com/api/v1/catalogo/` → **403**, y el cuerpo es
   `{"codigo_error": "permiso_insuficiente", "detail": "No tienes permiso para esta
   operacion."}` — ni un alias, ni un identificador, ni un número.
3. Ahora: `https://fiado-confirmado.onrender.com/api/v1/clientes/` → **200**, y el
   cuerpo es una lista con el **alias** de cada clienta y su **deuda**. **Nada más**: no
   hay `credit_limit`, no hay antigüedad, no hay `caja`.
4. **Dilo:** «el mismo endpoint, dos respuestas. El `dependiente` lee el libro porque
   **cobrar una deuda exige ver la deuda**, pero la **política** —el límite, la
   suspensión— no es suya».

### Demo 3 · La clienta acepta, y el cargo aparece (4 min)

**Qué demuestra:** el cargo —con su `Confirmacion` y sus líneas— **se escribe en una
sola transacción**, y solo cuando ella acepta (`CC-01`, `IC-03`).

1. Entra como **`dueno@tienda.test`** → **Tablero** → **«Preparar una propuesta»**:
   - **Cliente** → *Ana*
   - **Producto** → *Café molido* (3,20) · **Cantidad** → `1`
   - **Producto** → *Vino* (4,50) · **Cantidad** → `1`
   - **Total (opcional)** → déjalo vacío: lo calcula el servidor
2. **Preparar**. Se abre `/app/propuesta/{id}`: el **desglose**, el total (7,70) y las dos
   acciones, **Confirmar** y **Cancelar**.
3. Vuelve a **«Tus fiados»** en la cuenta de Ana: la propuesta está **pendiente**, y la
   escalera del dueño **sigue mostrando 30,00 €** — una figura pendiente **no mueve
   nada**.
4. En la cuenta de **Ana** → **«Tus fiados»** → **«Sí, acepto este fiado»**.
5. Vuelve a la pestaña del **dueño** y recarga el **Tablero**: el cargo ha aparecido,
   con sus dos líneas.
6. **Dilo:** «aceptó ella, y en la misma transacción se escribieron las cuatro cosas:
   el `LedgerEntry` del cargo, sus dos `CargoLinea`, la `Confirmacion` y el
   `confirmed_at`. O entran las cuatro, o no entra ninguna».

### Demo 4 · El pago se reparte FIFO (5 min)

**Qué demuestra:** un pago se imputa **al cargo más antiguo primero**, y **nunca excede
la deuda que salda**: el exceso es cambio y **no entra en el libro** (`PA-02`,
`ADR-26`).

1. En la cuenta de **Ana** → **«Tus cargos»** → **«Proponer un pago»** → importe
   **20,00** → tienda **Tienda de demostración** → **Proponer**.
2. Como **`dueno@tienda.test`**, en el **Tablero**, la sección de **pagos propuestos**:
   **Validar**.
3. Vuelve a la cuenta de **Ana** → **«Tus cargos»**:
   - **8,00 €** → **Pagado: 8,00 €. Te queda: 0,00 €.**
   - **7,00 €** → **Pagado: 7,00 €. Te queda: 0,00 €.**
   - **15,00 €** → **Pagado: 5,00 €. Te quedan: 10,00 €.**
4. **Dilo:** «20,00 contra 30,00 de deuda. El pago salda **las más antiguas primero**:
   los 8,00 quedan pagados, los 7,00 quedan pagados, y de los 15,00 quedan 5,00. Y el
   **exceso nunca entra**: un pago no puede crear crédito a favor, porque el dueño
   devuelve el cambio».
5. **Y si preguntan por las deudas que no se han tocado:** «el cargo de 7,70 de la
   demostración 3 y la propuesta pendiente de 2,40 son **más nuevos**, y el FIFO es por
   **antigüedad**, no por orden de creación. Y el de 15,00 es el más **nuevo** de las
   tres: no es que se quede a medias por ser viejo, sino porque **el dinero se acaba
   ahí**, y la deuda más reciente es la última a la que llega».

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
| 6 | «¿Y si la clienta no contesta?» | No hay cargo. La figura se queda `pendiente` y **no mueve nada** — y la tienda puede cancelarla. |
| 7 | «¿Por qué el precio de la línea no es el del catálogo?» | Porque el precio es una **instantánea**: la línea conserva el precio del momento en que se pactó. Cambiar el catálogo no reescribe el libro. |
| 8 | «¿Y si la clienta paga, ¿no sube la posición?» | No: `posicion_real` es `caja + fiado pendiente`. Un pago **sube la `caja`** y **baja el fiado pendiente**. Lo que cambia es la composición, no la suma. |
| 9 | «¿Qué harías con más tiempo?» | El techo de existencias, que está cortado y con la regla ya escrita en el dominio; y un **traspaso entre dueños**, que hoy no existe. |
| 10 | «¿Por qué no hay un editor de catálogo?» | Porque el catálogo es **de solo lectura** por diseño: viene de la semilla y no tiene ruta de escritura. Es una decisión de alcance, no un olvido. |

> **Si no sabéis una respuesta:** decidlo. «No lo sé, y está anotado en el registro del
> proyecto» es una respuesta mejor que inventar, y el registro
> (`openspec/changes/fiado-confirmado/state.yaml`) existe exactamente para eso.

---

## Anexo · Si algo falla

| Síntoma | Qué es |
|---|---|
| `/health/` responde pero las cuentas no entran | **el seed del deploy todavía no ha corrido**. Espera y vuelve: el build siembra al final. |
| El `dependiente` recibe 403 en `/api/v1/clientes/` | **idem**: su membresía en la tienda la crea el seed. Espera. |
| La cuenta de Ana no entra por `/app/cuenta` | **ella no entra por `/login/`**: el login del personal exige una sesión con `shop_id` y la de ella no lo tiene. Su login es `POST /api/v1/cuenta/login/`. |
| Una demostración se rompe a mitad | **Ctrl+C y sigue con la siguiente**: las cuatro son independientes, y la 2 y la 4 no dependen de la 1 ni de la 3. |
