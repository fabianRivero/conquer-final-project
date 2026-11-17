/**
 * The three routes of design 11.
 *
 * * `/app/posicion` - the owner's board.
 * * `/app/propuesta/:id` - the shop's screen, the place the
 *   confirmation is given.
 * * `/app/cliente` - the client's statement.
 *
 * **The routes are paths WITHOUT the trailing slash**, because Django
 * mounts them with one - `/app/posicion/` - and the two would not be
 * the same route. The trailing slash is the server's; the router's paths
 * are the ones the application navigates to, and the server's slash is
 * added by the mount.
 *
 * The client is a separate audience with its own prefix, and the two
 * never share a component: the client's page holds a credential and the
 * staff's holds a session.
 */

import { createBrowserRouter } from "react-router-dom";

import { Cliente } from "./surfaces/Cliente";
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
      path: "/app/cliente",
      element: <Cliente />,
    },
  ]);
}

/** The paths, as the tests and the links name them. */
export const RUTAS = {
  posicion: "/app/posicion",
  propuesta: (id: number | string) => `/app/propuesta/${id}`,
  cliente: "/app/cliente",
} as const;
