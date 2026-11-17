/**
 * `ProponerPago` - the client proposes a payment.
 *
 * **The proposal names NO charge.** The body carries an `importe` and a
 * `referencia`, and nothing else: the FIFO decides which charges the
 * payment retires, and a body that carries a `cargo_id` is refused with
 * `campo_no_admitido` (ADR-27).
 *
 * The client does not choose which debt it pays - it proposes an amount
 * and the shop applies it, oldest first.
 *
 * **The owner still records the payment.** The proposal creates no
 * ledger row; it is a request, and the owner's validation is what
 * appends the `pago`. The component says so plainly, because a client
 * that believes its payment was recorded would be a client that believes
 * it still owes the money.
 */

import { useState } from "react";

export interface ProponerPagoProps {
  /** The client's action: propose the payment. */
  onProponer: (importe: string, referencia: string) => Promise<void>;
  /** The refusal of the API, if there was one. */
  error?: string | null;
  /** What happened. */
  aviso?: string | null;
}

export function ProponerPago({ onProponer, error, aviso }: ProponerPagoProps) {
  const [importe, setImporte] = useState("");
  const [referencia, setReferencia] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setEnviando(true);
    try {
      await onProponer(importe.trim(), referencia.trim());
      setImporte("");
      setReferencia("");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section aria-labelledby="proponer-pago">
      <h2 id="proponer-pago">Proponer un pago</h2>
      <form onSubmit={enviar}>
        <label htmlFor="importe">Importe</label>
        <input
          id="importe"
          name="importe"
          type="text"
          inputMode="decimal"
          value={importe}
          onChange={(e) => setImporte(e.target.value)}
          required
        />

        <label htmlFor="referencia">Referencia (opcional)</label>
        <input
          id="referencia"
          name="referencia"
          type="text"
          value={referencia}
          onChange={(e) => setReferencia(e.target.value)}
        />

        <button type="submit" disabled={enviando}>
          Proponer
        </button>
      </form>

      <p>
        Proponer no registra el pago:{" "}
        <strong data-aviso="quien-registra">
          el dueno lo anota en el mostrador
        </strong>
        . La propuesta se aplica a tus deudas, de la mas antigua a la mas
        reciente.
      </p>

      {aviso ? <p data-aviso>{aviso}</p> : null}
      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}
