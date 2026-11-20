/**
 * `/app/posicion` - the owner's board.
 *
 * The board has **TWO shapes**, and the surface renders them apart:
 *
 * * the OWNER's payload: `caja`, `fiado_pendiente`, `posicion_real`,
 *   `buckets`, `clientes[]`, `serie_caja[]` and `cierre_hoy`;
 * * the `dependiente`'s payload: `caja`, `clientes` and `cierre_hoy`, and
 *   NOTHING else.
 *
 * The reduced payload is not the full one with the fields removed: it is
 * built from a different schema, so a field that is not declared cannot
 * appear whatever the query returns. **The surface does not invent the
 * difference**: it asks the payload which shape it is, and renders the
 * owner's components only when the owner is at the counter.
 *
 * The board **polls `/api/v1/posicion/` every 20 seconds**, and the
 * poll doubles as the keep-alive (ADR-10).
 */

import { useCallback, useEffect, useState } from "react";

import {
  Cinta,
  CerrarDia,
  Credenciales,
  Ecuacion,
  Escalera,
  PagosPropuestos,
  PropuestaForm,
} from "../components";
import { staff } from "../api/staff";
import { cuerpo } from "../api/http";

/** The owner's payload. */
interface TableroDueno {
  caja: string;
  fiado_pendiente: string;
  posicion_real: string;
  buckets: Record<string, string>;
  clientes: {
    alias: string;
    pendiente: string;
    antiguedad_max_dias: number;
    suspendido: boolean;
    motivo: string | null;
  }[];
  serie_caja: { fecha: string; caja: string }[];
  cierre_hoy: {
    date: string;
    esperado: string;
    contado: string;
    desviacion: string;
  } | null;
}

/** The `dependiente`'s payload. */
interface TableroDependiente {
  caja: string;
  clientes: unknown[];
  cierre_hoy: {
    date: string;
    esperado: string;
    contado: string;
    desviacion: string;
  } | null;
}

/**
 * One customer, as the `dependiente` reads it.
 *
 * The reduced schema carries the alias and the debts - and NONE of the
 * owner's policy: no `credit_limit`, no ageing, no `codigo`, no prefix.
 * The type declares only what the `dependiente` may see, so a field that
 * the server does not send has no place to be read from.
 */
interface ClienteDependiente {
  id: number;
  alias: string;
  pendiente: string;
  cargos: unknown[];
}

type Tablero = TableroDueno | TableroDependiente;

/** How often the board polls. The poll doubles as the keep-alive. */
export const SEGUNDOS_ENTRE_POLL = 20;

/** Whether the payload is the owner's. */
function esDelDueno(tablero: Tablero): tablero is TableroDueno {
  return "fiado_pendiente" in tablero;
}

export function Posicion() {
  const [tablero, setTablero] = useState<Tablero | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [clientes, setClientes] = useState<{
    id: number;
    alias: string;
    prefix: string | null;
    issued_at: string | null;
  }[]>([]);
  const [productos, setProductos] = useState<{
    id: number;
    nombre: string;
    precio: string;
  }[]>([]);
  const [pagos, setPagos] = useState<
    {
      id: number;
      alias: string;
      importe: string;
      referencia: string;
      estado: string;
    }[]
  >([]);
  const [clientesDependiente, setClientesDependiente] = useState<ClienteDependiente[]>(
    [],
  );

  const refrescar = useCallback(async () => {
    try {
      const respuesta = await staff.posicion();
      if (!respuesta.ok) {
        const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
        setError(fallo?.codigo_error ?? "el tablero no se pudo leer");
        return;
      }
      setTablero(await cuerpo<Tablero>(respuesta));
      setError(null);
    } catch {
      setError("el tablero no se pudo leer");
    }
  }, []);

  useEffect(() => {
    void refrescar();
    const temporizador = setInterval(() => {
      void refrescar();
    }, SEGUNDOS_ENTRE_POLL * 1000);
    return () => clearInterval(temporizador);
  }, [refrescar]);

  const recargarCredenciales = useCallback(async () => {
    const respuesta = await staff.clientes();
    if (!respuesta.ok) {
      return;
    }
    const datos = await cuerpo<
      {
        id: number;
        alias: string;
        prefix: string | null;
        issued_at: string | null;
      }[]
    >(respuesta);
    setClientes(datos ?? []);
  }, []);

  /**
   * The `dependiente`'s customer list.
   *
   * The reduced schema: the alias and the debts, and none of the owner's
   * policy. The `dependiente` prepares the fiados, so it needs to know
   * **who** it is fiando - and the debts it already carries, because it
   * collects them.
   */
  const recargarClientesDependiente = useCallback(async () => {
    const respuesta = await staff.clientes();
    if (!respuesta.ok) {
      return;
    }
    const datos = await cuerpo<ClienteDependiente[]>(respuesta);
    setClientesDependiente(datos ?? []);
  }, []);

  useEffect(() => {
    void (async () => {
      // The three lists answer a BARE LIST, not a paginated object with
      // `results`: the API returns them as arrays.
      await recargarCredenciales();
      const catalogo = await staff.catalogo();
      if (catalogo.ok) {
        const datos = await cuerpo<
          { id: number; nombre: string; precio: string }[]
        >(catalogo);
        setProductos(datos ?? []);
      }
      const propuestos = await staff.pagosPropuestos();
      if (propuestos.ok) {
        const datos = await cuerpo<
          {
            id: number;
            alias: string;
            importe: string;
            referencia: string;
            estado: string;
          }[]
        >(propuestos);
        setPagos(datos ?? []);
      }
      // The `dependiente`'s customers: the reduced schema.
      await recargarClientesDependiente();
    })();
  }, [recargarCredenciales, recargarClientesDependiente]);
  if (!tablero) {
    return (
      <main>
        <h1>Tablero</h1>
        {error ? <p role="alert">{error}</p> : <p>Cargando...</p>}
      </main>
    );
  }

  return (
    <main>
      <h1>Tablero</h1>
      {error ? <p role="alert">{error}</p> : null}

      {esDelDueno(tablero) ? (
        <>
          <Ecuacion
            caja={tablero.caja}
            fiadoPendiente={tablero.fiado_pendiente}
            posicionReal={tablero.posicion_real}
          />
          <Cinta buckets={tablero.buckets} />
          <Escalera clientes={tablero.clientes} />
          <CerrarDia
            cierreHoy={tablero.cierre_hoy}
            onCerrar={async (contado) => {
              const hoy = new Date().toISOString().slice(0, 10);
              const respuesta = await staff.cerrarDia({ date: hoy, contado });
              if (!respuesta.ok) {
                const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
                setError(fallo?.codigo_error ?? "el cierre no se pudo registrar");
                return;
              }
              await refrescar();
            }}
            error={error}
          />
          <Credenciales
            clientes={clientes.map((cliente) => ({
              id: cliente.id,
              alias: cliente.alias,
              prefix: cliente.prefix ?? null,
              issued_at: cliente.issued_at ?? null,
            }))}
            onRotar={async (clienteId) => {
              const respuesta = await staff.emitirCodigo(clienteId);
              if (!respuesta.ok) {
                const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
                setError(fallo?.codigo_error ?? "la credencial no se pudo emitir");
                return null;
              }
              await refrescar();
              await recargarCredenciales();
              return await cuerpo<{
                codigo: string;
                prefix: string;
                issued_at: string;
              }>(respuesta);
            }}
            error={error}
          />
          <PropuestaForm
            clientes={clientes}
            productos={productos}
            onPreparar={async (clienteId, lineas, total) => {
              const respuesta = await staff.prepararPropuesta({
                cliente_id: clienteId,
                lineas,
                ...(total ? { total } : {}),
              });
              if (!respuesta.ok) {
                const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
                setError(fallo?.codigo_error ?? "la propuesta no se pudo preparar");
              }
            }}
            error={error}
          />
        </>
      ) : (
        <>
          <p data-figura="caja">Caja {tablero.caja}</p>
          <CerrarDia
            cierreHoy={tablero.cierre_hoy}
            onCerrar={async (contado) => {
              const hoy = new Date().toISOString().slice(0, 10);
              const respuesta = await staff.cerrarDia({ date: hoy, contado });
              if (!respuesta.ok) {
                const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
                setError(fallo?.codigo_error ?? "el cierre no se pudo registrar");
              }
            }}
            error={error}
          />
          {/*
            The `dependiente` prepares the fiados too, so it gets the
            proposal form - with the customers of the REDUCED schema, and
            with the catalogue, which is the owner's.
          */}
          <PropuestaForm
            clientes={clientesDependiente.map((cliente) => ({
              id: cliente.id,
              alias: cliente.alias,
            }))}
            productos={productos}
            onPreparar={async (clienteId, lineas, total) => {
              const respuesta = await staff.prepararPropuesta({
                cliente_id: clienteId,
                lineas,
                ...(total ? { total } : {}),
              });
              if (!respuesta.ok) {
                const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
                setError(fallo?.codigo_error ?? "la propuesta no se pudo preparar");
              }
            }}
            error={error}
          />
        </>
      )}

      <PagosPropuestos
        pagos={pagos}
        onValidar={async (pagoId) => {
          await staff.validarPago(pagoId);
          await refrescar();
        }}
        onRechazar={async (pagoId) => {
          await staff.rechazarPago(pagoId);
          await refrescar();
        }}
        error={error}
      />
    </main>
  );
}
