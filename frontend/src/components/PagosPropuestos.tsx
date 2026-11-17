/**
 * `PagosPropuestos` - the client's proposed payments, to validate or to
 * reject.
 *
 * **A proposed payment is a request, not a scope.** The client's
 * proposal is a request for the owner to record a payment; only the
 * owner's validation creates the `pago` and its `ImputacionPago` rows.
 *
 * The section is the OWNER's, and it shows what the client proposed:
 * the amount and the reference. The amount the payment will have is
 * **exactly** the proposed one - never recomputed, never rounded.
 */

import { useState } from "react";

export interface PagoPropuesto {
  id: number;
  alias: string;
  importe: string;
  referencia: string;
  estado: string;
}

export interface PagosPropuestosProps {
  pagos: PagoPropuesto[];
  /** The owner's action: validate the proposal. */
  onValidar: (pagoId: number) => Promise<void>;
  /** The owner's action: reject the proposal. */
  onRechazar: (pagoId: number) => Promise<void>;
  error?: string | null;
}

export function PagosPropuestos({
  pagos,
  onValidar,
  onRechazar,
  error,
}: PagosPropuestosProps) {
  const [ocupado, setOcupado] = useState(false);

  async function actuar(accion: (id: number) => Promise<void>, id: number) {
    setOcupado(true);
    try {
      await accion(id);
    } finally {
      setOcupado(false);
    }
  }

  const pendientes = pagos.filter((pago) => pago.estado === "pendiente");

  return (
    <section aria-labelledby="pagos-propuestos">
      <h2 id="pagos-propuestos">Pagos propuestos</h2>
      {pendientes.length === 0 ? (
        <p>No hay pagos propuestos.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Cliente</th>
              <th>Importe</th>
              <th>Referencia</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {pendientes.map((pago) => (
              <tr key={pago.id}>
                <td>{pago.alias}</td>
                <td data-importe={pago.importe}>{pago.importe}</td>
                <td>{pago.referencia}</td>
                <td>
                  <button
                    type="button"
                    disabled={ocupado}
                    onClick={() => actuar(onValidar, pago.id)}
                  >
                    Validar
                  </button>
                  <button
                    type="button"
                    disabled={ocupado}
                    onClick={() => actuar(onRechazar, pago.id)}
                  >
                    Rechazar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}
