/**
 * `Escalera` - the risk ladder.
 *
 * The customers with something pending, sorted by `antiguedad_max_dias`
 * DESCENDING: the oldest debt first, because the oldest debt is the one
 * that ages into a suspension.
 *
 * **The sort is not done here.** The API already sorts the ladder that
 * way, and a client that sorted it again would be a second place where
 * the order could drift. The rows are rendered in the order they arrive.
 */

export interface ClienteEscalera {
  alias: string;
  pendiente: string;
  antiguedad_max_dias: number;
  suspendido: boolean;
  motivo: string | null;
}

export interface EscaleraProps {
  clientes: ClienteEscalera[];
}

export function Escalera({ clientes }: EscaleraProps) {
  return (
    <section aria-labelledby="escalera">
      <h2 id="escalera">La escalera</h2>
      {clientes.length === 0 ? (
        <p>Nadie debe nada.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Alias</th>
              <th>Pendiente</th>
              <th>Antiguedad (dias)</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {clientes.map((cliente) => (
              <tr key={cliente.alias} data-suspendido={cliente.suspendido}>
                <td>{cliente.alias}</td>
                <td>{cliente.pendiente}</td>
                <td>{cliente.antiguedad_max_dias}</td>
                <td>
                  {cliente.suspendido
                    ? `suspendido${cliente.motivo ? ` (${cliente.motivo})` : ""}`
                    : "activo"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
