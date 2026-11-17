/**
 * `Cierre` - the close of the day.
 *
 * The form takes the `contado` - what the owner counted in the drawer -
 * and the server derives the `esperado` and the `desviacion`. The
 * request may NOT carry `esperado` or `desviacion` (rule 14), so the
 * form does not even offer them.
 */

import { useState } from "react";

export interface CierreProps {
  /** The close of today, or `null` when the day is not closed yet. */
  cierreHoy: {
    date: string;
    esperado: string;
    contado: string;
    desviacion: string;
  } | null;
  /** The owner's action: post the count. */
  onCerrar: (contado: string) => Promise<void>;
  /** The refusal of the API, if there was one. */
  error?: string | null;
}

export function CerrarDia({ cierreHoy, onCerrar, error }: CierreProps) {
  const [contado, setContado] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setEnviando(true);
    try {
      await onCerrar(contado);
      setContado("");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section aria-labelledby="cierre">
      <h2 id="cierre">El cierre</h2>
      {cierreHoy ? (
        <dl data-cierre="hoy">
          <dt>Fecha</dt>
          <dd>{cierreHoy.date}</dd>
          <dt>Esperado</dt>
          <dd>{cierreHoy.esperado}</dd>
          <dt>Contado</dt>
          <dd>{cierreHoy.contado}</dd>
          <dt>Desviacion</dt>
          <dd>{cierreHoy.desviacion}</dd>
        </dl>
      ) : (
        <p>Hoy todavia no se ha cerrado.</p>
      )}

      <form onSubmit={enviar}>
        <label htmlFor="contado">Contado</label>
        <input
          id="contado"
          name="contado"
          type="text"
          inputMode="decimal"
          value={contado}
          onChange={(e) => setContado(e.target.value)}
          required
        />
        <button type="submit" disabled={enviando}>
          Cerrar el dia
        </button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}
