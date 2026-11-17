/**
 * `Credenciales` - issue or rotate a `codigo`.
 *
 * **The plaintext is shown ONCE.** The issuing response is the only time
 * the credential exists in the clear, and it is the client's own: the
 * board shows the `prefix` - the non-secret head - and the date, and the
 * plaintext goes to the client and nowhere else.
 *
 * The rotation is the same route as the issuing: `POST
 * /api/v1/clientes/{id}/codigo/` revokes the active one and issues
 * another, so the board only has one action.
 */

import { useState } from "react";

export interface CredencialEmitida {
  /** The plaintext. It exists only in this response. */
  codigo: string;
  /** The non-secret head of it. */
  prefix: string;
  /** When it was issued. */
  issued_at: string;
}

export interface CredencialesProps {
  /** The customers of the shop, with their credentials' state. */
  clientes: {
    id: number;
    alias: string;
    prefix: string | null;
    issued_at: string | null;
  }[];
  /** The owner's action: issue or rotate. */
  onRotar: (clienteId: number) => Promise<CredencialEmitida | null>;
  error?: string | null;
}

export function Credenciales({ clientes, onRotar, error }: CredencialesProps) {
  const [emitida, setEmitida] = useState<CredencialEmitida | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function rotar(clienteId: number) {
    setOcupado(true);
    try {
      const resultado = await onRotar(clienteId);
      setEmitida(resultado);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <section aria-labelledby="credenciales">
      <h2 id="credenciales">Credenciales</h2>

      {emitida ? (
        <p data-plaintext="visible">
          Credencial de <strong>{emitida.prefix}</strong>:{" "}
          <code data-plaintext>{emitida.codigo}</code>
          <br />
          <small>Se muestra una sola vez. El cliente debe anotarla.</small>
        </p>
      ) : null}

      <table>
        <thead>
          <tr>
            <th>Alias</th>
            <th>Prefijo</th>
            <th>Emitida</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {clientes.map((cliente) => (
            <tr key={cliente.id}>
              <td>{cliente.alias}</td>
              <td data-prefijo>{cliente.prefix ?? "-"}</td>
              <td>{cliente.issued_at ?? "-"}</td>
              <td>
                <button
                  type="button"
                  disabled={ocupado}
                  onClick={() => rotar(cliente.id)}
                >
                  {cliente.prefix ? "Rotar" : "Emitir"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}
