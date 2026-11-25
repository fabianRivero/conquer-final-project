/**
 * `Cargos` - her own charges, the state each one is in, and the payment
 * she proposes.
 *
 * **The state is a WORD**: `pendiente` (nobody paid it), `parcial` (a
 * payment retired part of it) or `pagado` (a payment retired all of
 * it). It is derived on read and never stored - a `pagado` column on
 * the charge would break the append-only guarantee of the book.
 *
 * **The charges of EVERY shop she is trusted in.** A person may owe in
 * several, and her account is the one place where all of them are hers
 * together - so each row names its shop.
 *
 * **She proposes a payment, and the proposal names the SHOP.**
 * The proposal does not choose which debt it retires - the FIFO decides
 * (ADR-27) - but a payment belongs to ONE shop's book, and the shop is
 * named so that a payment never lands in the wrong one.
 */

import { useState } from "react";

import { Cargo } from "../api/fiados";

export interface CargosProps {
  /** Her own charges, with their state. */
  cargos: Cargo[];
  /** Her proposal: she proposes to pay, and the shop is named. */
  onProponerPago: (importe: string, tienda: string) => Promise<void>;
  error?: string | null;
}

/** The states of a charge, in the words of the person. */
const ESTADO = {
  pendiente: "Sin pagar",
  parcial: "Pagado en parte",
  pagado: "Pagado",
} as const;

export function Cargos({ cargos, onProponerPago, error }: CargosProps) {
  const [importe, setImporte] = useState("");
  const [tienda, setTienda] = useState("");

  if (cargos.length === 0) {
    return (
      <section aria-labelledby="cargos">
        <h2 id="cargos">Tus cargos</h2>
        <p>No tienes ningun cargo.</p>
      </section>
    );
  }

  /** The shops she owes in: one per charge, without repeats. */
  const tiendas = Array.from(
    new Map(
      cargos.map((cargo) => [cargo.tienda, cargo.tienda_id]),
    ).entries(),
  );

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    await onProponerPago(importe.trim(), tienda);
    setImporte("");
  }

  return (
    <section aria-labelledby="cargos">
      <h2 id="cargos">Tus cargos</h2>
      <ul>
        {cargos.map((cargo) => (
          <li key={cargo.id}>
            <p>
              <strong>{cargo.tienda}</strong> — {cargo.amount} € —{" "}
              {ESTADO[cargo.estado as keyof typeof ESTADO] ?? cargo.estado}
            </p>
            <p>
              Pagado: {cargo.pagado} €. Te queda: {cargo.saldo} €.
            </p>
          </li>
        ))}
      </ul>

      {/*
        **She proposes a payment.** The shop is named: a payment belongs
        to ONE shop's book, and the FIFO retires THAT shop's charges.
      */}
      <form onSubmit={enviar}>
        <h3>Proponer un pago</h3>
        <p>
          Propone el importe. **No eliges que deuda paga**: lo decide el
          FIFO, de la mas antigua.
        </p>
        <label htmlFor="pago-importe">El importe</label>
        <input
          id="pago-importe"
          type="text"
          inputMode="decimal"
          value={importe}
          onChange={(e) => setImporte(e.target.value)}
          required
        />
        <label htmlFor="pago-tienda">La tienda</label>
        <select
          id="pago-tienda"
          value={tienda}
          onChange={(e) => setTienda(e.target.value)}
          required
        >
          <option value="">Elige la tienda</option>
          {tiendas.map(([nombre, id]) => (
            <option key={nombre} value={id !== undefined ? String(id) : ""}>
              {nombre}
            </option>
          ))}
        </select>
        <button type="submit">Proponer</button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}
