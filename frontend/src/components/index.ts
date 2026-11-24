/**
 * The components of the owner's board.
 *
 * They are built one by one, and each one is a piece of the payload the
 * API answers. The board has TWO shapes - the owner's and the
 * `dependiente`'s - and the components that read the owner's fields are
 * only rendered when the payload carries them.
 */

export { Cinta } from "./Cinta";
export { Cargos } from "./Cargos";
export { CerrarDia } from "./Cierre";
export { Credenciales } from "./Credenciales";
export { Ecuacion } from "./Ecuacion";
export { Escalera } from "./Escalera";
export { Fiados } from "./Fiados";
export { PagosPropuestos } from "./PagosPropuestos";
export { Personal } from "./Personal";
export { PropuestaForm } from "./PropuestaForm";
export { Vinculos } from "./Vinculos";
