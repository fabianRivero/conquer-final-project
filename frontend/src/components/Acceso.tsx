/**
 * `Acceso` - the client's credential field.
 *
 * **One field, `autocomplete="off"`, React state only.** The credential
 * is a bearer secret: it is never written to `localStorage` or
 * `sessionStorage`, it is never put in the URL, and it is cleared on
 * navigation. A credential in the browser's storage is a credential in
 * every script that runs on the page.
 *
 * The `autocomplete` matters for the same reason: the browser's
 * password manager would otherwise keep the credential where the page
 * cannot reach it - and where a leak could.
 */

import { useState } from "react";

export interface AccesoProps {
  /** The credential the client typed. */
  onAcceder: (codigo: string) => void;
  /** The refusal of the API, if there was one. */
  error?: string | null;
}

export function Acceso({ onAcceder, error }: AccesoProps) {
  const [codigo, setCodigo] = useState("");

  function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    onAcceder(codigo.trim());
    // The field is cleared: the credential lives in the caller's state
    // and nowhere else.
    setCodigo("");
  }

  return (
    <section aria-labelledby="acceso">
      <h2 id="acceso">Acceso</h2>
      <form onSubmit={enviar}>
        <label htmlFor="codigo">Tu codigo</label>
        <input
          id="codigo"
          name="codigo"
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={codigo}
          onChange={(e) => setCodigo(e.target.value)}
          required
        />
        <button type="submit">Entrar</button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}
