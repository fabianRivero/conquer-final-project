/**
 * `Pantalla` - the shop's screen.
 *
 * The place the confirmation is given: the owner shows it at the counter
 * and the client reads it.
 *
 * **It shows the full `desglose` and nothing else.** Product, quantity,
 * `precio_unitario` and `total` for every line, plus the proposal's
 * `total`. No balance, no ageing, no other customer, no `credit_limit`,
 * no `codigo` - the payload's schema declares only those fields, so a
 * field that is not declared cannot appear whatever the API hands over.
 *
 * The client reads it from the counter and **does not authenticate to
 * it**: the screen is served by the STAFF session, and the client is
 * standing in front of it.
 *
 * Its two actions are `Confirmar` and `Cancelar`. They are the two
 * buttons of `Pantalla` and not separate components, and the confirmation
 * is where the charge is born.
 */

import { useState } from "react";

export interface LineaPantalla {
  producto: string;
  cantidad: string;
  precio_unitario: string;
  total: string;
}
export interface PantallaProps {
  /** The proposal's lines. */
  lineas: LineaPantalla[];
  /** The proposal's total. */
  total: string;
  /** The owner's action: record the confirmation. */
  onConfirmar: () => Promise<void>;
  /** The owner's action: cancel the proposal. */
  onCancelar: () => Promise<void>;
  /** The refusal of the API, if there was one. */
  error?: string | null;
  /** What happened, for the owner to read. */
  aviso?: string | null;
}

export function Pantalla({
  lineas,
  total,
  onConfirmar,
  onCancelar,
  error,
  aviso,
}: PantallaProps) {
  const [ocupado, setOcupado] = useState(false);

  async function actuar(accion: () => Promise<void>) {
    setOcupado(true);
    try {
      await accion();
    } finally {
      setOcupado(false);
    }
  }

  return (
    <section aria-labelledby="pantalla">
      <h2 id="pantalla">La propuesta</h2>

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
          {lineas.map((linea, indice) => (
            <tr key={indice}>
              <td>{linea.producto}</td>
              <td>{linea.cantidad}</td>
              <td>{linea.precio_unitario}</td>
              <td>{linea.total}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={3}>Total</td>
            <td data-total>{total}</td>
          </tr>
        </tfoot>
      </table>

      <button
        type="button"
        disabled={ocupado}
        onClick={() => actuar(onConfirmar)}
      >
        Confirmar
      </button>
      <button
        type="button"
        disabled={ocupado}
        onClick={() => actuar(onCancelar)}
      >
        Cancelar
      </button>

      {aviso ? <p data-aviso>{aviso}</p> : null}
      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}
