/**
 * `Cinta` - the four ageing ribbons.
 *
 * A charge is bucketed by ITS OWN age, and the four buckets are a
 * partition of the same unpaid charges - so their totals sum exactly to
 * the outstanding, never a separate figure.
 *
 * **The four are named here, not taken from the payload's keys.** The
 * vocabulary is closed - `vigente`, `envejecido`, `viejo`, `cronico` -
 * and a ribbon that only appeared when the server sent it would let a
 * bucket go missing from the board without anyone noticing. The payload's
 * numbers are read by name, and a missing one reads as zero.
 */

export interface Buckets {
  vigente?: string;
  envejecido?: string;
  viejo?: string;
  cronico?: string;
}

/** The four ribbons, in the order of the risk. */
export const CINTAS = ["vigente", "envejecido", "viejo", "cronico"] as const;

export type CintaNombre = (typeof CINTAS)[number];

export interface CintaProps {
  buckets: Buckets;
}

export function Cinta({ buckets }: CintaProps) {
  return (
    <section aria-labelledby="cinta">
      <h2 id="cinta">La cinta</h2>
      <ul>
        {CINTAS.map((nombre) => (
          <li key={nombre} data-cinta={nombre}>
            <span>{nombre}</span>
            <span data-cifra>{buckets[nombre] ?? "0.00"}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
