/**
 * `/app/cuenta` - the person's own account.
 *
 * **The person owns her account.** She creates it, she chose the
 * username and the password, and she is the only one who changes them.
 * The shop neither issues them nor knows them.
 *
 * **The password lives in React state and nowhere else.** It is not in
 * `localStorage`, not in `sessionStorage`, not in the URL, and it is
 * cleared as soon as the request is sent. A password in the browser's
 * storage is a password in every script that runs on the page.
 *
 * **This surface is not the staff's.** It lives under its own path, and
 * the session it opens carries no shop: the person is not in a shop.
 * That is what keeps this session away from the staff routes.
 *
 * The three things she can do here:
 *
 * 1. create her account;
 * 2. sign in;
 * 3. hold her profiles - **one** client profile, because she is one
 *    client wherever she buys on credit, and **several** business
 *    profiles, because a person may own more than one shop.
 */

import { useCallback, useState } from "react";

import { Cargos } from "../components/Cargos";
import { Fiados } from "../components/Fiados";
import { Vinculos } from "../components/Vinculos";
import { cuenta, PerfilTienda, Perfiles } from "../api/cuenta";
import { fiados as fiadosApi, Cargo, Fiado } from "../api/fiados";
import { vinculos as vinculosApi, Vinculo } from "../api/vinculos";
import { cuerpo } from "../api/http";

/** What the surface is showing. */
type Pantalla = "acceso" | "perfiles";

export function Cuenta() {
  const [pantalla, setPantalla] = useState<Pantalla>("acceso");
  const [perfiles, setPerfiles] = useState<Perfiles | null>(null);
  const [susVinculos, setSusVinculos] = useState<Vinculo[]>([]);
  const [susFiados, setSusFiados] = useState<Fiado[]>([]);
  const [susCargos, setSusCargos] = useState<Cargo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const refrescar = useCallback(async () => {
    const respuesta = await cuenta.perfiles();
    if (!respuesta.ok) {
      setError("los perfiles no se pudieron leer");
      return;
    }
    setPerfiles(await cuerpo<Perfiles>(respuesta));
    setPantalla("perfiles");

    // The links: the shops that asked her, and the answer she gave.
    const delVinculo = await vinculosApi.misVinculos();
    if (delVinculo.ok) {
      setSusVinculos(await cuerpo<Vinculo[]>(delVinculo) ?? []);
    }

    // The fiados waiting for her answer, and her charges.
    const delFiado = await fiadosApi.mios();
    if (delFiado.ok) {
      setSusFiados(await cuerpo<Fiado[]>(delFiado) ?? []);
    }
    const delCargo = await fiadosApi.misCargos();
    if (delCargo.ok) {
      setSusCargos(await cuerpo<Cargo[]>(delCargo) ?? []);
    }
  }, []);

  return (
    <main>
      <h1>Tu cuenta</h1>
      {error ? <p role="alert">{error}</p> : null}
      {aviso ? <p role="status">{aviso}</p> : null}

      {pantalla === "acceso" ? (
        <AccesoPersona
          onEntrar={async (usuario, contrasena) => {
            const respuesta = await cuenta.login(usuario, contrasena);
            if (!respuesta.ok) {
              const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
              setError(fallo?.codigo_error ?? "no se pudo entrar");
              return;
            }
            setError(null);
            await refrescar();
          }}
          onRegistrar={async (usuario, contrasena) => {
            const respuesta = await cuenta.registro(usuario, contrasena);
            if (!respuesta.ok) {
              const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
              setError(fallo?.codigo_error ?? "no se pudo crear la cuenta");
              return;
            }
            setError(null);
            setAviso("Cuenta creada. Ya puedes entrar.");
          }}
          error={error}
        />
      ) : (
        <section aria-labelledby="perfiles">
          <h2 id="perfiles">Tus perfiles</h2>

          <h3>Cliente</h3>
          {perfiles?.cliente ? (
            <p>Ya tienes tu perfil de cliente.</p>
          ) : (
            <button
              type="button"
              onClick={async () => {
                const respuesta = await cuenta.crearPerfilCliente();
                if (!respuesta.ok) {
                  const fallo = await cuerpo<{ codigo_error?: string }>(
                    respuesta,
                  );
                  setError(fallo?.codigo_error ?? "no se pudo crear el perfil");
                  return;
                }
                setError(null);
                await refrescar();
              }}
            >
              Crear mi perfil de cliente
            </button>
          )}

          <h3>Tus negocios</h3>
          <ul>
            {(perfiles?.tiendas ?? []).map((tienda: PerfilTienda) => (
              <li key={tienda.id}>
                {tienda.nombre}
                {tienda.direccion ? ` - ${tienda.direccion}` : ""}
              </li>
            ))}
          </ul>

          {/*
            The links: the shops that asked her, and her answer. **A
            pending link shows the shop's name and the buttons - and
            nothing else.**
          */}
          <Vinculos
            vinculos={susVinculos}
            onAceptar={async (vinculoId) => {
              const respuesta = await vinculosApi.aceptar(vinculoId);
              if (!respuesta.ok) {
                const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
                setError(fallo?.codigo_error ?? "no se pudo aceptar");
                return;
              }
              setError(null);
              await refrescar();
            }}
            onRechazar={async (vinculoId) => {
              const respuesta = await vinculosApi.rechazar(vinculoId);
              if (!respuesta.ok) {
                const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
                setError(fallo?.codigo_error ?? "no se pudo rechazar");
                return;
              }
              setError(null);
              await refrescar();
            }}
            error={error}
          />

          {/*
            **The fiados, and her answer.** The shop asked and she
            answers here - the figure, its lines, and the buttons. And
            the reason of a refusal is HERS: she may write one and she
            may leave it empty.
          */}
          <Fiados
            fiados={susFiados}
            onAceptar={async (fiadoId) => {
              const respuesta = await fiadosApi.aceptar(fiadoId);
              if (!respuesta.ok) {
                const fallo = await cuerpo<{ codigo_error?: string }>(
                  respuesta,
                );
                setError(fallo?.codigo_error ?? "no se pudo aceptar");
                return;
              }
              setError(null);
              setAviso("Aceptaste el fiado.");
              await refrescar();
            }}
            onRechazar={async (fiadoId, motivo) => {
              const respuesta = await fiadosApi.rechazar(fiadoId, motivo);
              if (!respuesta.ok) {
                const fallo = await cuerpo<{ codigo_error?: string }>(
                  respuesta,
                );
                setError(fallo?.codigo_error ?? "no se pudo rechazar");
                return;
              }
              setError(null);
              setAviso("Rechazaste el fiado.");
              await refrescar();
            }}
            error={error}
          />

          {/*
            **Her charges, with the state each one is in** - including
            `parcial`, the payment that retired part of a charge - and
            the payment she proposes.
          */}
          <Cargos
            cargos={susCargos}
            onProponerPago={async (importe, tienda) => {
              const respuesta = await fiadosApi.proponerPago(
                importe,
                tienda ? Number(tienda) : undefined,
              );
              if (!respuesta.ok) {
                const fallo = await cuerpo<{ codigo_error?: string }>(
                  respuesta,
                );
                setError(fallo?.codigo_error ?? "no se pudo proponer el pago");
                return;
              }
              setError(null);
              setAviso("Propusiste el pago. La tienda lo valida.");
              await refrescar();
            }}
            error={error}
          />

          {/*
            **The claim.** The shop registered her before she had an
            account, and it calls her by an alias. Her account finds the
            row she claims - and until she claims it, the account and the
            row are two things, and the shop's question waits.

            It appears only when there is nothing to answer: a shop that
            asked her means the row is already hers, and there is
            nothing left to claim.
          */}
          {susVinculos.length === 0 ? (
            <FormularioReclamar
              onReclamar={async (alias) => {
                const respuesta = await cuenta.reclamar(alias);
                if (!respuesta.ok) {
                  const fallo = await cuerpo<{ codigo_error?: string }>(
                    respuesta,
                  );
                  setError(fallo?.codigo_error ?? "no se pudo reclamar");
                  return;
                }
                setError(null);
                setAviso("Reclamaste tu ficha. Ya puedes ver tus tiendas.");
                await refrescar();
              }}
              error={error}
            />
          ) : null}

          <FormularioTienda
            onCrear={async (nombre, direccion, nif) => {
              const respuesta = await cuenta.crearPerfilTienda(
                nombre,
                direccion,
                nif,
              );
              if (!respuesta.ok) {
                const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
                setError(fallo?.codigo_error ?? "no se pudo crear el negocio");
                return;
              }
              setError(null);
              await refrescar();
            }}
            error={error}
          />
        </section>
      )}
    </main>
  );
}

interface AccesoPersonaProps {
  onEntrar: (usuario: string, contrasena: string) => Promise<void>;
  onRegistrar: (usuario: string, contrasena: string) => Promise<void>;
  error?: string | null;
}

function AccesoPersona({ onEntrar, onRegistrar, error }: AccesoPersonaProps) {
  const [usuario, setUsuario] = useState("");
  const [contrasena, setContrasena] = useState("");

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    await onEntrar(usuario.trim(), contrasena);
    // The password is cleared as soon as the request is sent: it lived
    // in the state and nowhere else.
    setContrasena("");
  }

  async function registrar(evento: React.FormEvent) {
    evento.preventDefault();
    await onRegistrar(usuario.trim(), contrasena);
    setContrasena("");
  }

  return (
    <>
      <section aria-labelledby="entrar">
        <h2 id="entrar">Entrar</h2>
        <form onSubmit={enviar}>
          <label htmlFor="cuenta-usuario">Tu nombre de usuario</label>
          <input
            id="cuenta-usuario"
            name="username"
            type="text"
            autoComplete="username"
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
            required
          />
          <label htmlFor="cuenta-contrasena">Tu contrasena</label>
          <input
            id="cuenta-contrasena"
            name="password"
            type="password"
            autoComplete="current-password"
            value={contrasena}
            onChange={(e) => setContrasena(e.target.value)}
            required
          />
          <button type="submit">Entrar</button>
        </form>
      </section>

      <section aria-labelledby="crear-cuenta">
        <h2 id="crear-cuenta">Crear una cuenta</h2>
        <p>
          Eliges tu nombre de usuario y tu contrasena. La tienda no los
          conoce y no puede cambiarlos.
        </p>
        <form onSubmit={registrar}>
          <label htmlFor="registro-usuario">Nombre de usuario</label>
          <input
            id="registro-usuario"
            name="username"
            type="text"
            autoComplete="username"
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
            required
          />
          <label htmlFor="registro-contrasena">Contrasena</label>
          <input
            id="registro-contrasena"
            name="password"
            type="password"
            autoComplete="new-password"
            value={contrasena}
            onChange={(e) => setContrasena(e.target.value)}
            required
          />
          <button type="submit">Crear cuenta</button>
        </form>
      </section>
      {error ? <p role="alert">{error}</p> : null}
    </>
  );
}

interface FormularioReclamarProps {
  onReclamar: (alias: string) => Promise<void>;
  error?: string | null;
}

/**
 * **The claim of the customer row.**
 *
 * The shop registered her before she had an account, and it calls her by
 * an alias - "Ana". Her username is her own and it is not the alias.
 * She names the alias the shop gave her, and the row is hers.
 *
 * The alias is not a secret: it is the name the shop calls her by, and
 * the shop says it out loud.
 */
function FormularioReclamar({ onReclamar, error }: FormularioReclamarProps) {
  const [alias, setAlias] = useState("");

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    await onReclamar(alias.trim());
    setAlias("");
  }

  return (
    <form onSubmit={enviar}>
      <h3>Reclamar tu ficha</h3>
      <p>
        Una tienda te llamo de otra manera antes de que tuvieras cuenta.
        Escribe el nombre con el que te registraron y tu ficha sera tuya.
      </p>
      <label htmlFor="reclamar-alias">El nombre que te dio la tienda</label>
      <input
        id="reclamar-alias"
        type="text"
        value={alias}
        onChange={(e) => setAlias(e.target.value)}
        required
      />
      <button type="submit">Reclamar</button>
      {error ? <p role="alert">{error}</p> : null}
    </form>
  );
}

interface FormularioTiendaProps {
  onCrear: (
    nombre: string,
    direccion: string,
    nif: string,
  ) => Promise<void>;
  error?: string | null;
}

function FormularioTienda({ onCrear, error }: FormularioTiendaProps) {
  const [nombre, setNombre] = useState("");
  const [direccion, setDireccion] = useState("");
  const [nif, setNif] = useState("");

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    await onCrear(nombre.trim(), direccion.trim(), nif.trim());
    setNombre("");
    setDireccion("");
    setNif("");
  }

  return (
    <form onSubmit={enviar}>
      <h3>Crear un negocio</h3>
      <label htmlFor="negocio-nombre">Nombre</label>
      <input
        id="negocio-nombre"
        type="text"
        value={nombre}
        onChange={(e) => setNombre(e.target.value)}
        required
      />
      <label htmlFor="negocio-direccion">Direccion</label>
      <input
        id="negocio-direccion"
        type="text"
        value={direccion}
        onChange={(e) => setDireccion(e.target.value)}
      />
      <label htmlFor="negocio-nif">NIF</label>
      <input
        id="negocio-nif"
        type="text"
        value={nif}
        onChange={(e) => setNif(e.target.value)}
      />
      <button type="submit">Crear</button>
      {error ? <p role="alert">{error}</p> : null}
    </form>
  );
}
