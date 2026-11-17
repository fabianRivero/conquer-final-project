/**
 * `/app/propuesta/:id` - the shop's screen.
 *
 * The surface is built in the next slice of the chain (task 7.7). Here
 * it proves that the route resolves and that it carries the id of the
 * proposal it shows.
 */

import { useParams } from "react-router-dom";

export function Propuesta() {
  const { id } = useParams();
  return (
    <main>
      <h1>Propuesta {id}</h1>
      <p>La pantalla del mostrador.</p>
    </main>
  );
}
