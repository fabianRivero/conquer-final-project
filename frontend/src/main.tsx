/**
 * The mount.
 *
 * One bundle, one origin, three routes. The application takes over the
 * `root` element of `index.html` and nothing else.
 *
 * **The client page does not poll.** The board polls `/api/v1/posicion/`
 * every 20 seconds, and the poll doubles as the keep-alive (ADR-10); the
 * client's page does not, because a poll would multiply the credential's
 * exposure for no benefit.
 */

import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import { crearRouter } from "./router";

const contenedor = document.getElementById("root");

if (!contenedor) {
  throw new Error("El mount point #root no existe en el documento.");
}

ReactDOM.createRoot(contenedor).render(
  <React.StrictMode>
    <RouterProvider router={crearRouter()} />
  </React.StrictMode>,
);
