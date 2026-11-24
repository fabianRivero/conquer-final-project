/**
 * `Cargos` - her own charges, and the state each one is in.
 *
 * **The state is a WORD**: `pendiente` (nobody paid it), `parcial` (a
 * payment retired part of it) or `pagado` (a payment retired all of
 * it). It is derived on read and never stored - a `pagado` column on
 * the charge would break the append-only guarantee of the book.
 *
 * **The charges of EVERY shop she is trusted in.** A person may owe in
 * several, and her account is the one place where all of them are hers
 * together - so each row names its shop.
 */

import { Cargo } from "../api/fiados";

export interface CargosProps {
  /** Her own charges, with their state. */
  cargos: Cargo[];
}

/** The states of a charge, in the words of the person. */
const ESTADO = {
  pendiente: "Sin pagar",
  parcial: "Pagado en parte",
  pagado: "Pagado",
} as const;

export function Cargos({ cargos }: CargosProps) {
  if (cargos.length === 0) {
    return (
      <section aria-labelledby="cargos">
        <h2 id="cargos">Tus cargos</h2>
        <p>No tienes ningun cargo.</p>
      </section>
    );
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
    </section>
  );
}
