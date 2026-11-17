/**
 * `PropuestaForm` - prepare a proposal.
 *
 * The owner prepares a fiado with its itemisation. **The proposal names
 * no charge**: it carries the customer, the lines and the total, and the
 * charge exists only at the confirmation.
 *
 * The total is optional in the request: when it is absent the server
 * derives it from the lines, and when it is present it must equal their
 * sum (rule 3).
 */

import { useState } from "react";

export interface LineaPropuesta {
  producto_id: number;
  cantidad: string;
  precio_unitario?: string;
}

export interface PropuestaFormProps {
  /** The customers of the shop, to propose to. */
  clientes: { id: number; alias: string }[];
  /** The products of the catalogue, to sell. */
  productos: { id: number; nombre: string; precio: string }[];
  /** The owner's action: prepare the proposal. */
  onPreparar: (
    clienteId: number,
    lineas: LineaPropuesta[],
    total?: string,
  ) => Promise<void>;
  error?: string | null;
}

export function PropuestaForm({
  clientes,
  productos,
  onPreparar,
  error,
}: PropuestaFormProps) {
  const [clienteId, setClienteId] = useState("");
  const [lineas, setLineas] = useState<LineaPropuesta[]>([
    { producto_id: 0, cantidad: "1" },
  ]);
  const [total, setTotal] = useState("");
  const [enviando, setEnviando] = useState(false);

  function cambiarLinea(indice: number, campo: "producto_id" | "cantidad", valor: string) {
    setLineas((previas) =>
      previas.map((linea, i) =>
        i === indice ? { ...linea, [campo]: campo === "producto_id" ? Number(valor) : valor } : linea,
      ),
    );
  }

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setEnviando(true);
    try {
      await onPreparar(
        Number(clienteId),
        lineas.filter((linea) => linea.producto_id !== 0),
        total === "" ? undefined : total,
      );
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section aria-labelledby="propuesta-form">
      <h2 id="propuesta-form">Preparar una propuesta</h2>
      <form onSubmit={enviar}>
        <label htmlFor="propuesta-cliente">Cliente</label>
        <select
          id="propuesta-cliente"
          value={clienteId}
          onChange={(e) => setClienteId(e.target.value)}
          required
        >
          <option value="">Elige un cliente</option>
          {clientes.map((cliente) => (
            <option key={cliente.id} value={cliente.id}>
              {cliente.alias}
            </option>
          ))}
        </select>

        <table>
          <thead>
            <tr>
              <th>Producto</th>
              <th>Cantidad</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {lineas.map((linea, indice) => (
              <tr key={indice}>
                <td>
                  <select
                    value={linea.producto_id}
                    onChange={(e) => cambiarLinea(indice, "producto_id", e.target.value)}
                    required
                  >
                    <option value={0}>Elige un producto</option>
                    {productos.map((producto) => (
                      <option key={producto.id} value={producto.id}>
                        {producto.nombre}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={linea.cantidad}
                    onChange={(e) => cambiarLinea(indice, "cantidad", e.target.value)}
                    required
                  />
                </td>
                <td>
                  <button
                    type="button"
                    onClick={() =>
                      setLineas((previas) =>
                        previas.filter((_, i) => i !== indice),
                      )
                    }
                  >
                    Quitar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <button
          type="button"
          onClick={() =>
            setLineas((previas) => [...previas, { producto_id: 0, cantidad: "1" }])
          }
        >
          Anadir linea
        </button>

        <label htmlFor="propuesta-total">Total (opcional)</label>
        <input
          id="propuesta-total"
          type="text"
          inputMode="decimal"
          value={total}
          onChange={(e) => setTotal(e.target.value)}
        />
        <button type="submit" disabled={enviando}>
          Preparar
        </button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}
