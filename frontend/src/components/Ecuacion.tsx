/**
 * `Ecuacion` - the equation: `caja + fiado_pendiente = posicion_real`.
 *
 * The three figures come from the API and are NOT computed here: the
 * server derives them, and a client that recomputed them would be a
 * second source of truth for the money.
 *
 * The equation is shown as it is: the cash in the drawer, the credit
 * owed, and what the owner's position really is.
 */

export interface EcuacionProps {
  /** The cash in the drawer. */
  caja: string;
  /** The credit owed to the shop. */
  fiadoPendiente: string;
  /** What the position really is. */
  posicionReal: string;
}

/** The equation, as the three figures the server sent. */
export function Ecuacion({ caja, fiadoPendiente, posicionReal }: EcuacionProps) {
  return (
    <section aria-labelledby="ecuacion">
      <h2 id="ecuacion">La ecuacion</h2>
      <p className="ecuacion">
        <span data-figura="caja">Caja {caja}</span>
        {" + "}
        <span data-figura="fiado-pendiente">Fiado pendiente {fiadoPendiente}</span>
        {" = "}
        <span data-figura="posicion-real">Posicion real {posicionReal}</span>
      </p>
    </section>
  );
}
