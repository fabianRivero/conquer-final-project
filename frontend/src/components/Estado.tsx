/**
 * `Estado` - the client's statement.
 *
 * The total owed, and one row per confirmed charge with its
 * `desglose`.
 *
 * **Every charge in the statement is a confirmed charge** with a
 * mandatory itemisation, so every row carries its `lineas[]`. There is
 * no "unconfirmed charge" case any more: a charge without a confirmation
 * does not exist.
 *
 * `pagado` and `saldo` are DERIVED on read by the server - they are the
 * `ImputacionPago` rows against the charge - and they are shown as they
 * arrive. A charge of 15,00 settled by 5,00 reads `5/15`.
 */

export interface LineaCargo {
  producto: string;
  cantidad: string;
  precio_unitario: string;
  total: string;
}

export interface CargoDelEstado {
  id: number;
  fecha: string;
  amount: string;
  confirmado_en: string | null;
  pagado: string;
  saldo: string;
  lineas: LineaCargo[];
}

export interface EstadoProps {
  /** The client's alias. */
  alias: string;
  /** The total owed. */
  total: string;
  /** The client's confirmed charges. */
  cargos: CargoDelEstado[];
}

export function Estado({ alias, total, cargos }: EstadoProps) {
  return (
    <section aria-labelledby="estado">
      <h2 id="estado">Tu cuenta</h2>
      <p>
        Hola, <span data-alias>{alias}</span>. Debes{" "}
        <strong data-total>{total}</strong>.
      </p>

      {cargos.length === 0 ? (
        <p>No tienes cargos.</p>
      ) : (
        <ul>
          {cargos.map((cargo) => (
            <li key={cargo.id} data-cargo={cargo.id}>
              <p>
                <span data-fecha={cargo.fecha}>{cargo.fecha}</span> —{" "}
                <span data-pagado>{cargo.pagado}</span>/{" "}
                <span data-total-cargo>{cargo.amount}</span>
                {cargo.saldo !== cargo.amount ? (
                  <>
                    {" "}
                    (debe <span data-saldo>{cargo.saldo}</span>)
                  </>
                ) : null}
              </p>
              <table>
                <thead>
                  <tr>
                    <th>Producto</th>
                    <th>Cantidad</th>
                    <th>Precio</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {cargo.lineas.map((linea, indice) => (
                    <tr key={indice}>
                      <td>{linea.producto}</td>
                      <td>{linea.cantidad}</td>
                      <td>{linea.precio_unitario}</td>
                      <td>{linea.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
