/**
 * The link, and the client's consent.
 *
 * **The shop asks; the client answers.** The answer comes from HER
 * account - the person's session - and the request carries the cookie.
 * The routes are under `cuenta/`, the same prefix as the account
 * itself: they are the CLIENT's routes, and they are a **read** scope
 * plus her answer.
 */

import { cuerpo, peticion } from "./http";

export interface Vinculo {
  id: number;
  tienda: string;
  estado: string;
  credit_limit?: string | null;
  pendiente?: string | null;
}

export const vinculos = {
  /** The links of the client. **Read only** - she sees, she does not edit. */
  misVinculos: () => peticion("/cuenta/vinculos/", { credentials: "same-origin" }),

  /** She accepts the shop's question. */
  aceptar: (vinculoId: number) =>
    peticion("/cuenta/vinculos/aceptar/", {
      method: "POST",
      credentials: "same-origin",
      cuerpo: { vinculo_id: vinculoId },
    }),

  /** She refuses. */
  rechazar: (vinculoId: number) =>
    peticion("/cuenta/vinculos/rechazar/", {
      method: "POST",
      credentials: "same-origin",
      cuerpo: { vinculo_id: vinculoId },
    }),
};

export { cuerpo };
