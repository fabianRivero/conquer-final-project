/**
 * The client audience: the credential and nothing else.
 *
 * The credential travels in the `X-Codigo` header, on every request, and
 * **nowhere else** - never in a query parameter, never in a cookie,
 * never in the body (design 5, R4). A credential in a URL is a credential
 * in the browser's history, in the `Referer` of every outbound request
 * and in every proxy's log.
 *
 * **No cookie is sent.** `credentials: "omit"` is the setting: the
 * client holds no session, and sending one would blur the two scopes.
 * The client's responses set no `Set-Cookie`, so the browser holds no
 * ambient client authority (ADR-4).
 *
 * The credential's scope is exactly three routes: the statement, one
 * own charge, and the proposal of a payment. It grants no write to the
 * book, no read of the credit book, and no read of another customer's
 * data.
 */

import { cuerpo, peticion } from "./http";

/** The header the credential travels in. */
export const CABECERA_CODIGO = "X-Codigo";

/** The client's three routes. */
export const cliente = {
  estado: (codigo: string) =>
    peticion("/cliente/estado/", {
      credentials: "omit",
      headers: { [CABECERA_CODIGO]: codigo },
    }),

  cargo: (codigo: string, id: number) =>
    peticion(`/cliente/cargos/${id}/`, {
      credentials: "omit",
      headers: { [CABECERA_CODIGO]: codigo },
    }),

  proponerPago: (
    codigo: string,
    propuesta: { importe: string; referencia?: string },
  ) =>
    peticion("/cliente/pagos/proponer/", {
      method: "POST",
      credentials: "omit",
      headers: { [CABECERA_CODIGO]: codigo },
      cuerpo: propuesta,
    }),
};

/** One confirmed charge, as the client sees it in the statement. */
export interface CargoCliente {
  id: number;
  fecha: string;
  amount: string;
  confirmado_en: string | null;
  pagado: string;
  saldo: string;
  lineas: {
    producto: string;
    cantidad: string;
    precio_unitario: string;
    total: string;
  }[];
}

/** The client's own statement. */
export interface EstadoCliente {
  alias: string;
  total: string;
  cargos: CargoCliente[];
}

/**
 * Read the statement.
 *
 * The refusal is the same for an unknown, a revoked and a throttled
 * credential - `codigo_invalido` - so the answer says nothing about
 * whether the credential exists.
 */
export async function estado(codigo: string): Promise<
  { ok: true; datos: EstadoCliente } | { ok: false; codigo: string }
> {
  const respuesta = await cliente.estado(codigo);
  if (!respuesta.ok) {
    const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
    return { ok: false, codigo: fallo?.codigo_error ?? "desconocido" };
  }
  return { ok: true, datos: await cuerpo<EstadoCliente>(respuesta) };
}
