/**
 * The staff audience: the session and the CSRF token.
 *
 * The staff scope is the SESSION - `request.session["shop_id"]` plus a
 * Django group - and every request sends the session cookie with
 * `credentials: "same-origin"`.
 *
 * **The two audiences never mix.** The client sends `credentials:
 * "omit"` and no cookie; the staff sends the session. There is no
 * route that accepts both, and the difference here is the first half of
 * that guarantee: the browser never holds ambient client authority.
 *
 * Every mutation carries `X-CSRFToken`, which `http.ts` reads from the
 * cookie Django set. A missing or invalid token is refused with 403 and
 * creates no row.
 */

import { cuerpo, peticion } from "./http";

/** The staff endpoints of design 9.1. */
export const staff = {
  posicion: () => peticion("/posicion/", { credentials: "same-origin" }),

  cierre: () => peticion("/cierre/", { credentials: "same-origin" }),

  catalogo: () => peticion("/catalogo/", { credentials: "same-origin" }),

  clientes: () => peticion("/clientes/", { credentials: "same-origin" }),

  cliente: (id: number) =>
    peticion(`/clientes/${id}/`, { credentials: "same-origin" }),

  registrarCaja: (movimiento: { kind: string; concept: string; amount: string }) =>
    peticion("/caja/", {
      method: "POST",
      credentials: "same-origin",
      cuerpo: movimiento,
    }),

  cerrarDia: (cierre: { date: string; contado: string }) =>
    peticion("/cierre/", {
      method: "POST",
      credentials: "same-origin",
      cuerpo: cierre,
    }),

  prepararPropuesta: (propuesta: {
    cliente_id: number;
    lineas: { producto_id: number; cantidad: string; precio_unitario?: string }[];
    total?: string;
  }) =>
    peticion("/propuestas/", {
      method: "POST",
      credentials: "same-origin",
      cuerpo: propuesta,
    }),

  pantallaPropuesta: (id: number) =>
    peticion(`/propuestas/${id}/pantalla/`, { credentials: "same-origin" }),

  confirmarPropuesta: (id: number) =>
    peticion(`/propuestas/${id}/confirmar/`, {
      method: "POST",
      credentials: "same-origin",
      cuerpo: {},
    }),

  cancelarPropuesta: (id: number) =>
    peticion(`/propuestas/${id}/cancelar/`, {
      method: "POST",
      credentials: "same-origin",
      cuerpo: {},
    }),

  pagosPropuestos: () =>
    peticion("/pagos-propuestos/", { credentials: "same-origin" }),

  validarPago: (id: number) =>
    peticion(`/pagos-propuestos/${id}/validar/`, {
      method: "POST",
      credentials: "same-origin",
      cuerpo: {},
    }),

  rechazarPago: (id: number) =>
    peticion(`/pagos-propuestos/${id}/rechazar/`, {
      method: "POST",
      credentials: "same-origin",
      cuerpo: {},
    }),
};

/** The board's payload, as the owner's and the `dependiente`'s differ. */
export interface Posicion {
  caja?: string;
  clientes?: unknown[];
  cierre_hoy?: unknown;
  fiado_pendiente?: string;
  posicion_real?: string;
  escalera?: unknown[];
  buckets?: unknown;
}

/** Read the board, and tell the caller whether it was refused. */
export async function posicion(): Promise<
  { ok: true; datos: Posicion } | { ok: false; codigo: string }
> {
  const respuesta = await staff.posicion();
  if (!respuesta.ok) {
    const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
    return { ok: false, codigo: fallo?.codigo_error ?? "desconocido" };
  }
  return { ok: true, datos: await cuerpo<Posicion>(respuesta) };
}
