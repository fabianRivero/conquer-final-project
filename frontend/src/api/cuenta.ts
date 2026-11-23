/**
 * The person's account - the third audience.
 *
 * **The person owns her account.** She chose the username and the
 * password, and she is the only one who changes them. The shop neither
 * issues them nor knows them.
 *
 * **A session, like the staff's, and not a credential.** The staff's
 * session names a shop; the person's names a person - and it carries no
 * `shop_id`, which is exactly what keeps it away from the staff routes.
 * That is why the requests here send the cookie (`same-origin`) and the
 * client's do not (`omit`).
 *
 * The three credential modes now live in `staff.ts`, `cliente.ts` and
 * this one - and all of them build their URLs in `http.ts`, so none of
 * them can build one of its own.
 */

import { cuerpo, peticion } from "./http";

/** The person's own profile. */
export interface PerfilCliente {
  id: number;
}

/** A business the person owns. */
export interface PerfilTienda {
  id: number;
  nombre: string;
  direccion: string;
  nif: string;
}

/** Everything the person has: one client profile, several businesses. */
export interface Perfiles {
  cliente: PerfilCliente | null;
  tiendas: PerfilTienda[];
}

export const cuenta = {
  /** Create the account. The person chooses her username and password. */
  registro: (username: string, password: string) =>
    peticion("/cuenta/registro/", {
      method: "POST",
      credentials: "same-origin",
      cuerpo: { username, password },
    }),

  /** Sign in. The session is written without a `shop_id`. */
  login: (username: string, password: string) =>
    peticion("/cuenta/login/", {
      method: "POST",
      credentials: "same-origin",
      cuerpo: { username, password },
    }),

  logout: () =>
    peticion("/cuenta/logout/", {
      method: "POST",
      credentials: "same-origin",
      cuerpo: {},
    }),

  /** Her profiles: one client, several businesses. */
  perfiles: () => peticion("/perfiles/", { credentials: "same-origin" }),

  /** Create the client profile - "I am a client in the world of credit". */
  crearPerfilCliente: () =>
    peticion("/perfiles/cliente/", {
      method: "POST",
      credentials: "same-origin",
      cuerpo: {},
    }),

  /** Create a business profile. */
  crearPerfilTienda: (nombre: string, direccion: string, nif: string) =>
    peticion("/perfiles/tienda/", {
      method: "POST",
      credentials: "same-origin",
      cuerpo: { nombre, direccion, nif },
    }),

  /**
   * Claim the customer row the shop created for her.
   *
   * **The shop registers a person before she has an account**, and it
   * calls her by an ALIAS. Then she registers herself - and she chose
   * her username, which is not the alias - so the account and the row
   * have to meet. This is the meeting: she names the alias the shop
   * gave her, and the row is hers.
   */
  reclamar: (alias: string) =>
    peticion("/cuenta/reclamar/", {
      method: "POST",
      credentials: "same-origin",
      cuerpo: { alias },
    }),
};

/** Read the body's JSON, or the refusal's body. */
export { cuerpo };
