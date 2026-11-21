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

import { cuenta, PerfilTienda, Perfiles } from "../api/cuenta";
import { cuerpo } from "../api/http";

/** What the surface is showing. */
type Pantalla = "acceso" | "perfiles";

export function Cuenta() {
  const [pantalla, setPantalla] = useState<Pantalla>("acceso");
  const [perfiles, setPerfiles] = useState<Perfiles | null>(null);
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
