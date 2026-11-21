/**
 * The shop's staff - the routes the OWNER uses to give a user.
 *
 * **Only the owner.** Administrating the staff is the shop's POLICY -
 * the same policy as the `credit_limit` and the catalogue - and the N5
 * gate did not open it. The `dependiente` operates the counter.
 *
 * The credentials travel in the **body**, and the request carries the
 * staff session - so it is a session route, with the CSRF contract of
 * every other mutation.
 */

import { cuerpo, peticion } from "./http";

export interface Miembro {
  id: number;
  username: string;
  rol: string;
  creado_en?: string;
}

export const personal = {
  /** The staff of the shop. */
  listar: () => peticion("/tienda/personal/", { credentials: "same-origin" }),

  /** Give a staff member a user: a username and a password of the shop's. */
  alta: (username: string, password: string, rol: string) =>
    peticion("/tienda/personal/", {
      method: "POST",
      credentials: "same-origin",
      cuerpo: { username, password, rol },
    }),

  /** Take a staff member off the shop. The user and its rows stay. */
  baja: (miembroId: number) =>
    peticion(`/tienda/personal/${miembroId}/`, {
      method: "DELETE",
      credentials: "same-origin",
    }),
};

export { cuerpo };
