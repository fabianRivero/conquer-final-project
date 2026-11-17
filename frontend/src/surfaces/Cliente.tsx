/**
 * `/app/cliente` - the client's statement.
 *
 * The client reads its own statement and proposes a payment. It never
 * writes to the book: the proposal creates no ledger row, and the owner's
 * validation is what appends the `pago`.
 *
 * **The credential lives in React state and nowhere else.** It is not in
 * `localStorage`, not in `sessionStorage`, not in the URL, and it is
 * cleared on navigation. A credential in the browser's storage is a
 * credential in every script that runs on the page.
 *
 * **The page does not poll.** The board polls every 20 seconds and the
 * poll doubles as the keep-alive; the client's page does not, because a
 * poll would multiply the credential's exposure for no benefit.
 */

import { useCallback, useEffect, useState } from "react";

import { Acceso } from "../components/Acceso";
import { Estado } from "../components/Estado";
import { ProponerPago } from "../components/ProponerPago";
import { cliente, estado as leerEstado } from "../api/cliente";
import { cuerpo } from "../api/http";

export function Cliente() {
  const [codigo, setCodigo] = useState<string | null>(null);
  const [datos, setDatos] = useState<{
    alias: string;
    total: string;
    cargos: {
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
    }[];
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const refrescar = useCallback(async () => {
    if (!codigo) {
      return;
    }
    const resultado = await leerEstado(codigo);
    if (!resultado.ok) {
      setError(resultado.codigo);
      setDatos(null);
      return;
    }
    setDatos(resultado.datos);
    setError(null);
  }, [codigo]);

  useEffect(() => {
    void refrescar();
  }, [refrescar]);

  // The credential is cleared on navigation: it lives in the state of
  // this surface and nowhere else.
  useEffect(() => {
    return () => {
      setCodigo(null);
      setDatos(null);
    };
  }, []);

  if (!codigo || !datos) {
    return (
      <main>
        <h1>Mi cuenta</h1>
        <Acceso onAcceder={setCodigo} error={error} />
      </main>
    );
  }

  return (
    <main>
      <h1>Mi cuenta</h1>
      <Estado alias={datos.alias} total={datos.total} cargos={datos.cargos} />
      <ProponerPago
        onProponer={async (importe, referencia) => {
          const respuesta = await cliente.proponerPago(codigo, {
            importe,
            ...(referencia ? { referencia } : {}),
          });
          if (!respuesta.ok) {
            const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
            setError(fallo?.codigo_error ?? "la propuesta no se pudo enviar");
            return;
          }
          setAviso("Propuesto. El dueno lo anota en el mostrador.");
          setError(null);
        }}
        error={error}
        aviso={aviso}
      />
    </main>
  );
}
