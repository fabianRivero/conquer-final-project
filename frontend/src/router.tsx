/**
 * The routes of design 11.
 *
 * * `/app/posicion` - the owner's board.
 * * `/app/propuesta/:id` - the shop's screen, the place the
 *   confirmation is given.
 * * `/app/cuenta` - the person's own account.
 *
 * **The routes are paths WITHOUT the trailing slash**, because Django
 * mounts them with one - `/app/posicion/` - and the two would not be
 * the same route. The trailing slash is the server's; the router's paths
 * are the ones the application navigates to, and the server's slash is
 * added by the mount.
 *
 * Each audience keeps its own prefix and its own component: the client's
 * page holds a credential, the staff's holds a shop session, and the
 * person's holds a session of her own. **The three never share a
 * component.**
 */

import { createBrowserRouter } from "react-router-dom";

import { Cuenta } from "./surfaces/Cuenta";
import { Mostrador } from "./surfaces/Mostrador";
import { Posicion } from "./surfaces/Posicion";
import { Propuesta } from "./surfaces/Propuesta";

/**
 * The router.
 *
 * It is exported as a factory and not as a constant, so the tests can
 * build one with a memory history and the application can build one
 * with the browser's.
 */
export function crearRouter() {
  return createBrowserRouter([
    {
      path: "/app/posicion",
      element: <Posicion />,
    },
    {
      path: "/app/propuesta/:id",
      element: <Propuesta />,
    },
    {
      path: "/app/cuenta",
      element: <Cuenta />,
    },
    {
      path: "/app/mostrador",
      element: <Mostrador />,
    },
  ]);
}

/** The paths, as the tests and the links name them. */
export const RUTAS = {
  posicion: "/app/posicion",
  propuesta: (id: number | string) => `/app/propuesta/${id}`,
  cuenta: "/app/cuenta",
  mostrador: "/app/mostrador",
} as const;
