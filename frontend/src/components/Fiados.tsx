/**
 * `Fiados` - her own fiados, and her answer to the shop.
 *
 * **The shop asks; she answers.** A pending fiado shows the shop's
 * name, the figure, **its lines** and the buttons. The lines are there
 * BEFORE she answers, because the answer is about those lines: a figure
 * she cannot see broken down is not a figure she can confirm.
 *
 * **The reason for a refusal is hers.** She may write one, and she may
 * leave it empty: a refusal without an explanation is not an answer,
 * and an empty explanation is still an answer. **She is not obliged to
 * justify herself to the shop.**
 *
 * **The reason of a refusal is READ.** The owner wrote the figure and
 * she wrote the answer, and the answer carries the explanation.
 */

import { useState } from "react";

import { Fiado } from "../api/fiados";

export interface FiadosProps {
  /** Her own fiados, with their state. */
  fiados: Fiado[];
  /** Her answer: she accepts. */
  onAceptar: (fiadoId: number) => Promise<void>;
  /** Her answer: she refuses, and she may say why. */
  onRechazar: (fiadoId: number, motivo: string) => Promise<void>;
  error?: string | null;
}

/** The states of a fiado, in the words of the person. */
const ESTADO = {
  pendiente: "Esperando tu respuesta",
  aceptado: "Aceptado",
  rechazado: "Rechazado",
} as const;

/** The money, as the reader reads it. */
function dinero(valor: string): string {
  return `${valor} €`;
}

export function Fiados({
  fiados,
  onAceptar,
  onRechazar,
  error,
}: FiadosProps) {
  const [motivos, setMotivos] = useState<Record<number, string>>({});
  const [negando, setNegando] = useState<number | null>(null);

  if (fiados.length === 0) {
    return (
      <section aria-labelledby="fiados">
        <h2 id="fiados">Tus fiados</h2>
        <p>No hay ningun fiado preparado.</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="fiados">
      <h2 id="fiados">Tus fiados</h2>

      <ul>
        {fiados.map((fiado) => (
          <li key={fiado.id}>
            <p>
              <strong>{fiado.tienda}</strong> —{" "}
              {ESTADO[fiado.estado as keyof typeof ESTADO] ?? fiado.estado} —{" "}
              {dinero(fiado.total)}
            </p>

            {/* The lines, BEFORE she answers: the answer is about them. */}
            {fiado.lineas && fiado.lineas.length > 0 ? (
              <ul>
                {fiado.lineas.map((linea, indice) => (
                  <li key={indice}>
                    {linea.producto} — {linea.cantidad} ×{" "}
                    {dinero(linea.precio_unitario)} = {dinero(linea.total)}
                  </li>
                ))}
              </ul>
            ) : null}

            {fiado.estado === "pendiente" ? (
              <div>
                <button
                  type="button"
                  onClick={() => {
                    void onAceptar(fiado.id);
                  }}
                >
                  Si, acepto este fiado
                </button>

                {/*
                  The reason is hers, and it is OPTIONAL. The field
                  appears when she asks for it, and it may stay empty:
                  a refusal without an explanation is still an answer.
                */}
                {negando === fiado.id ? (
                  <div>
                    <label htmlFor={`motivo-${fiado.id}`}>
                      Por que no (puedes dejarlo vacio)
                    </label>
                    <input
                      id={`motivo-${fiado.id}`}
                      type="text"
                      value={motivos[fiado.id] ?? ""}
                      onChange={(e) =>
                        setMotivos({ ...motivos, [fiado.id]: e.target.value })
                      }
                    />
                    <button
                      type="button"
                      onClick={() => {
                        setNegando(null);
                        void onRechazar(
                          fiado.id,
                          (motivos[fiado.id] ?? "").trim(),
                        );
                      }}
                    >
                      Rechazar
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setNegando(null);
                      }}
                    >
                      Cancelar
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => {
                      setNegando(fiado.id);
                    }}
                  >
                    No, rechazo este fiado
                  </button>
                )}
              </div>
            ) : null}

            {/* The reason she gave, read back. */}
            {fiado.estado === "rechazado" && fiado.motivo ? (
              <p>Tu motivo: {fiado.motivo}</p>
            ) : null}
          </li>
        ))}
      </ul>
      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}
