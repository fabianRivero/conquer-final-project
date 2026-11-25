/**
 * The person's own fiados and charges, and her answer to the shop.
 *
 * **The shop asks; she answers.** The answer comes from HER account -
 * the person's session - and the request carries the cookie. The routes
 * are under `cuenta/`, the same prefix as the account itself: they are
 * the CLIENT's routes, and they are a **read** scope plus her answer.
 *
 * **Her answer is hers.** The shop may not answer for her, and a shop
 * that could accept for her would be a shop that could decide for her.
 */

import { cuerpo, peticion } from "./http";

/** One of her own fiados, as she sees it. */
export interface Fiado {
  id: number;
  tienda: string;
  estado: string;
  total: string;
  creado_en: string;
  /** Her reason, when she refused. It may be empty. */
  motivo?: string | null;
  /** The lines, when the fiado is still waiting for her answer. */
  lineas?: {
    producto: string;
    cantidad: string;
    precio_unitario: string;
    total: string;
  }[];
}

/** One of her own charges, with the state it is in. */
export interface Cargo {
  id: number;
  tienda: string;
  /** The shop's id - the payment has to name the shop it is for. */
  tienda_id?: number;
  fecha: string;
  amount: string;
  pagado: string;
  saldo: string;
  /** `pendiente`, `parcial` or `pagado`. */
  estado: string;
}

export const fiados = {
  /** Her own fiados, with their state. */
  mios: () => peticion("/cuenta/fiados/", { credentials: "same-origin" }),

  /** Her own charges, with the state each one is in. */
  misCargos: () => peticion("/cuenta/cargos/", { credentials: "same-origin" }),

  /**
   * **She proposes a payment**, from her own account.
   *
   * The proposal names **no charge**: the FIFO decides which debt it
   * retires (ADR-27). It does name the **shop**, because a payment
   * belongs to ONE shop's book.
   */
  proponerPago: (importe: string, tiendaId?: number) =>
    peticion("/cuenta/pagos/proponer/", {
      method: "POST",
      credentials: "same-origin",
      cuerpo: {
        importe,
        ...(tiendaId !== undefined ? { tienda_id: tiendaId } : {}),
      },
    }),

  /** **She accepts.** The shop asked and she said yes. */
  aceptar: (fiadoId: number) =>
    peticion("/cuenta/fiados/aceptar/", {
      method: "POST",
      credentials: "same-origin",
      cuerpo: { fiado_id: fiadoId },
    }),

  /**
   * **She refuses**, and she may say why.
   *
   * The reason is free text and it may be empty: a refusal without an
   * explanation is not an answer, and an empty explanation is still an
   * answer - she is not obliged to justify herself to the shop.
   */
  rechazar: (fiadoId: number, motivo?: string) =>
    peticion("/cuenta/fiados/rechazar/", {
      method: "POST",
      credentials: "same-origin",
      cuerpo: { fiado_id: fiadoId, motivo: motivo ?? "" },
    }),
};

export { cuerpo };
