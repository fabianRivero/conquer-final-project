/**
 * `/app/mostrador` - **the counter**.
 *
 * **The attendant asks her for her username and types it.** The system
 * finds her, and the owner prepares the fiado.
 *
 * **There is NO PASSWORD FIELD, and that is the point.** The password
 * is typed by HER, on her own device, from her own account - and it
 * never travels to the counter. The screen the attendant reads asks
 * for a public name and nothing else.
 *
 * **The counter does not answer for her.** It finds her and it
 * prepares the figure; she accepts or refuses it from her own account,
 * and the counter has no way to pretend she did.
 *
 * **The search is scoped to the shop.** The owner of one shop does not
 * look for the customers of another.
 */

import { useCallback, useState } from "react";

import { staff } from "../api/staff";
import { cuerpo } from "../api/http";

/** One person the search found. */
interface Hallada {
  cliente_id: number;
  alias: string;
  username: string;
  credit_limit: string | null;
}

export function Mostrador() {
  const [username, setUsername] = useState("");
  const [halladas, setHalladas] = useState<Hallada[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const buscar = useCallback(async () => {
    const respuesta = await staff.buscarEnElMostrador(username.trim());
    if (!respuesta.ok) {
      const fallo = await cuerpo<{ codigo_error?: string }>(respuesta);
      setError(fallo?.codigo_error ?? "no se pudo buscar");
      return;
    }
    const encontradas = await cuerpo<Hallada[]>(respuesta) ?? [];
    setHalladas(encontradas);
    setError(null);
    setAviso(
      encontradas.length === 0
        ? "Ningun persona de esta tienda tiene ese nombre de usuario."
        : `${encontradas.length} persona(s) encontrada(s).`,
    );
  }, [username]);

  return (
    <main>
      <h1>Mostrador</h1>
      {error ? <p role="alert">{error}</p> : null}
      {aviso ? <p role="status">{aviso}</p> : null}

      <section aria-labelledby="buscar">
        <h2 id="buscar">Buscar a una persona</h2>
        <p>
          Preguntale su nombre de usuario. **La contrasena la teclea
          ella**, en su propia cuenta: no se pide aqui.
        </p>
        <form
          onSubmit={(evento) => {
            evento.preventDefault();
            void buscar();
          }}
        >
          <label htmlFor="mostrador-usuario">Su nombre de usuario</label>
          <input
            id="mostrador-usuario"
            type="text"
            autoComplete="off"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
          <button type="submit">Buscar</button>
        </form>
      </section>

      {halladas.length > 0 ? (
        <section aria-labelledby="halladas">
          <h2 id="halladas">Personas encontradas</h2>
          <ul>
            {halladas.map((persona) => (
              <li key={persona.cliente_id}>
                <p>
                  <strong>{persona.alias}</strong> — {persona.username}
                </p>
                <p>
                  Le pueden fiar hasta {persona.credit_limit ?? "sin limite"}.
                </p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </main>
  );
}
