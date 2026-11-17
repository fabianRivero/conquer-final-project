/**
 * `/app/propuesta/:id` - the shop's screen.
 *
 * The place the confirmation is given: the owner shows it at the counter
 * and the client reads it.
 *
 * **The client does not authenticate to it.** The screen is served by the
 * STAFF session - the surface fetches it with `credentials:
 * "same-origin"` - and the client is standing in front of it.
 *
 * The two actions are the confirmation and the cancellation. The
 * confirmation is where the charge is born, and the cancellation writes
 * nothing but the instant.
 */

import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { Pantalla } from "../components/Pantalla";
import { staff } from "../api/staff";
import { cuerpo } from "../api/http";

interface PantallaPayload {
  lineas: {
    producto: string;
    cantidad: string;
    precio_unitario: string;
    total: string;
  }[];
  total: string;
}

export function Propuesta() {
  const { id } = useParams();
  const [pantalla, setPantalla] = useState<PantallaPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const refrescar = useCallback(async () => {
    if (!id) {
      return;
    }
    try {
      const respuesta = await staff.pantallaPropuesta(Number(id));
      if (!respuesta.ok) {
        const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
        setError(fallo?.codigo_error ?? "la propuesta no se pudo leer");
        return;
      }
      setPantalla(await cuerpo<PantallaPayload>(respuesta));
      setError(null);
    } catch {
      setError("la propuesta no se pudo leer");
    }
  }, [id]);

  useEffect(() => {
    void refrescar();
  }, [refrescar]);

  if (!pantalla) {
    return (
      <main>
        <h1>Propuesta</h1>
        {error ? <p role="alert">{error}</p> : <p>Cargando...</p>}
      </main>
    );
  }

  return (
    <main>
      <h1>Propuesta</h1>
      <Pantalla
        lineas={pantalla.lineas}
        total={pantalla.total}
        onConfirmar={async () => {
          const respuesta = await staff.confirmarPropuesta(Number(id));
          if (!respuesta.ok) {
            const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
            setError(fallo?.codigo_error ?? "no se pudo confirmar");
            return;
          }
          setAviso("Confirmada. El cargo ya es deuda.");
          setError(null);
        }}
        onCancelar={async () => {
          const respuesta = await staff.cancelarPropuesta(Number(id));
          if (!respuesta.ok) {
            const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
            setError(fallo?.codigo_error ?? "no se pudo cancelar");
            return;
          }
          setAviso("Cancelada. No hay deuda.");
          setError(null);
        }}
        error={error}
        aviso={aviso}
      />
    </main>
  );
}
