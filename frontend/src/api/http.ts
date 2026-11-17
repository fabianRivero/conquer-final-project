/**
 * The ONLY place a URL is built.
 *
 * **The same-origin contract** (design 11): every request uses a
 * RELATIVE path (`/api/v1/…`), and this module refuses any absolute
 * URL - a path that starts with a scheme, or with `//`. So a second host
 * cannot be introduced by accident: not by a typo, not by a pasted URL,
 * not by a config value that came from somewhere else.
 *
 * The refusal is a THROWN error and not a silent correction. A silent
 * correction would hide the mistake, and the mistake is the whole
 * threat: a request that goes to another host carries the session
 * cookie to a host that does not own it.
 *
 * The two credential modes live in `staff.ts` and `cliente.ts`, and both
 * of them build their URLs HERE - so neither can build one of its own.
 */

/** The prefix of every API path. */
export const API = "/api/v1";

/**
 * Whether the path is a RELATIVE one.
 *
 * A path is relative when it names no origin: it starts with a single
 * slash, and it does not start with the protocol-relative `//`.
 */
export function esRelativo(camino: string): boolean {
  return (
    camino.startsWith("/") &&
    !camino.startsWith("//") &&
    !/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(camino)
  );
}

/**
 * Build the URL of an API path, or refuse.
 *
 * The path is checked and NOT fixed: a path that names an origin is an
 * error, and the error is thrown where it happened.
 */
export function url(ruta: string): string {
  if (!esRelativo(ruta)) {
    throw new Error(
      `La ruta debe ser relativa al origen: ${JSON.stringify(ruta)}`,
    );
  }
  return `${API}${ruta}`;
}

/** The options every request carries, whatever the audience is. */
export interface OpcionesPeticion extends RequestInit {
  /** The body, already serialised. */
  cuerpo?: unknown;
}

/**
 * The shared request.
 *
 * It reads the CSRF token from the cookie when there is one, and it
 * never sets `credentials` on its own: the two audiences differ there,
 * and the difference is the whole point of the two modules.
 */
export async function peticion(
  ruta: string,
  opciones: OpcionesPeticion = {},
): Promise<Response> {
  const { cuerpo, ...resto } = opciones;
  const cabeceras = new Headers(resto.headers ?? {});
  if (cuerpo !== undefined) {
    cabeceras.set("Content-Type", "application/json");
  }
  const token = tokenCsrf();
  if (token) {
    cabeceras.set("X-CSRFToken", token);
  }

  // The body is built here and NOT passed through as `undefined`:
  // `exactOptionalPropertyTypes` refuses an explicit undefined, and a
  // request with no body must carry no body key at all.
  const init: RequestInit = { ...resto, headers: cabeceras };
  if (cuerpo !== undefined) {
    init.body = JSON.stringify(cuerpo);
  }
  return await fetch(url(ruta), init);
}

/**
 * The CSRF token, read from the cookie Django set.
 *
 * The cookie is not read for the client's requests: the client has no
 * session, so there is nothing for CSRF to protect (ADR-4). The header
 * is harmless there, but the module that sends it is the client's own
 * and it decides.
 */
export function tokenCsrf(): string | null {
  const nombre = "csrftoken";
  const partes = document.cookie.split(";");
  for (const parte of partes) {
    const [clave, ...resto] = parte.trim().split("=");
    if (clave === nombre) {
      return decodeURIComponent(resto.join("="));
    }
  }
  return null;
}

/**
 * Read the body's JSON, or the refusal's body.
 *
 * Every refusal of the application answers with two keys -
 * `codigo_error` and `detail` - and the caller usually wants the code.
 */
export async function cuerpo<T>(respuesta: Response): Promise<T> {
  if (respuesta.status === 204) {
    return undefined as T;
  }
  const texto = await respuesta.text();
  if (!texto) {
    return undefined as T;
  }
  try {
    return JSON.parse(texto) as T;
  } catch {
    return texto as unknown as T;
  }
}
