/**
 * `Vinculos` - the links of the client, and her consent.
 *
 * **A pending link shows the shop's name and the buttons - and nothing
 * else.** If she could see the debt and the ageing first, the consent
 * would be a formality: she would already have seen everything the
 * acceptance reveals.
 *
 * **The reason for a rejection is the SHOP's**, and she reads it. The
 * owner writes why he did not give the credit, and the client sees it:
 * a refusal without an explanation is not an answer.
 *
 * **The buttons are the only thing she can press.** The client's account
 * is a **read** scope: she sees her figures and her links, and she
 * answers the shop's question. She does not edit anything and she does
 * not delete anything.
 */

export interface Vinculo {
  id: number;
  tienda: string;
  estado: string;
  credit_limit?: string | null;
  pendiente?: string | null;
}

export interface VinculosProps {
  /** The links of the client. */
  vinculos: Vinculo[];
  /** Her answer: she accepts the shop's question. */
  onAceptar: (vinculoId: number) => Promise<void>;
  /** Her answer: she refuses. */
  onRechazar: (vinculoId: number) => Promise<void>;
  error?: string | null;
}

/** The states of a link, in the words of the client. */
const ESTADO = {
  pendiente: "Esperando tu respuesta",
  aceptado: "Aceptado",
  rechazado: "Rechazado",
  eliminado: "Retirado por la tienda",
} as const;

export function Vinculos({ vinculos, onAceptar, onRechazar, error }: VinculosProps) {
  return (
    <section aria-labelledby="vinculos">
      <h2 id="vinculos">Tus tiendas</h2>

      {vinculos.length === 0 ? (
        <p>No hay ninguna tienda que te haya preguntado todavia.</p>
      ) : (
        <ul>
          {vinculos.map((vinculo) => (
            <li key={vinculo.id}>
              <p>
                <strong>{vinculo.tienda}</strong> —{" "}
                {ESTADO[vinculo.estado as keyof typeof ESTADO] ??
                  vinculo.estado}
              </p>

              {/*
                A PENDING link shows the shop's name and the buttons -
                and nothing else. The figures open when she accepts.
              */}
              {vinculo.estado === "pendiente" ? (
                <div>
                  <button
                    type="button"
                    onClick={() => {
                      void onAceptar(vinculo.id);
                    }}
                  >
                    Si, soy cliente de confianza aqui
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      void onRechazar(vinculo.id);
                    }}
                  >
                    No
                  </button>
                </div>
              ) : null}

              {vinculo.estado === "aceptado" ? (
                <p>
                  Te pueden fiar hasta {vinculo.credit_limit ?? "sin limite"}.
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}
