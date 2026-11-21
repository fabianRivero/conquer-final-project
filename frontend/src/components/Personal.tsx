/**
 * `Personal` - the staff the shop gave a user.
 *
 * **Only the owner sees this.** Administrating the staff is the shop's
 * POLICY - the same policy as the `credit_limit` and the catalogue - and
 * the N5 gate did not open it. The `dependiente` operates the counter.
 *
 * The owner gives a staff member a **user**: a username and a password
 * that belong to the SHOP, not to the person. A `dependiente` who is
 * also a person in her own right holds a **separate** account - a
 * different user, a different password, a different session - and the
 * shop knows nothing about it.
 *
 * **The password is the owner's.** She sets it, and she hands it over.
 * The field is masked, and it is cleared as soon as the request is sent:
 * a password in the browser's storage is a password in every script that
 * runs on the page.
 */

import { useState } from "react";

export interface Miembro {
  id: number;
  username: string;
  rol: string;
}

export interface PersonalProps {
  /** The staff of the shop. */
  miembros: Miembro[];
  /** The owner's act: give a staff member a user. */
  onAlta: (
    username: string,
    password: string,
    rol: string,
  ) => Promise<void>;
  /** The owner's act: take a staff member off the shop. */
  onBaja: (miembroId: number) => Promise<void>;
  error?: string | null;
}

export function Personal({ miembros, onAlta, onBaja, error }: PersonalProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [rol, setRol] = useState("dependiente");

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    await onAlta(username.trim(), password, rol);
    // The password is cleared as soon as the request is sent: it lived
    // in the state and nowhere else.
    setUsername("");
    setPassword("");
  }

  return (
    <section aria-labelledby="personal">
      <h2 id="personal">Personal de la tienda</h2>

      <table>
        <thead>
          <tr>
            <th>Usuario</th>
            <th>Rol</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {miembros.map((miembro) => (
            <tr key={miembro.id}>
              <td>{miembro.username}</td>
              <td>{miembro.rol}</td>
              <td>
                <button
                  type="button"
                  onClick={() => {
                    void onBaja(miembro.id);
                  }}
                >
                  Quitar
                </button>
              </td>
            </tr>
          ))}
          {miembros.length === 0 ? (
            <tr>
              <td colSpan={3}>Todavia no hay personal.</td>
            </tr>
          ) : null}
        </tbody>
      </table>

      <form onSubmit={enviar}>
        <h3>Dar de alta a un empleado</h3>
        <label htmlFor="personal-usuario">Nombre de usuario</label>
        <input
          id="personal-usuario"
          type="text"
          autoComplete="off"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />
        <label htmlFor="personal-contrasena">Contrasena</label>
        <input
          id="personal-contrasena"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <label htmlFor="personal-rol">Rol</label>
        <select
          id="personal-rol"
          value={rol}
          onChange={(e) => setRol(e.target.value)}
        >
          <option value="dependiente">Dependiente</option>
          <option value="dueno">Dueno</option>
        </select>
        <button type="submit">Dar de alta</button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}
