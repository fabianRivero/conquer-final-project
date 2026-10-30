# product-catalogue Specification

## Purpose

The vocabulary of the ledger: the `Producto` the owner puts on the tab, its default price, and the rule that the catalogue names and prices goods instead of counting them.

## Requirements

### Requirement: PC-01 — The catalogue holds only the goods eligible for fiado

A `Producto` MUST carry `nombre`, `precio`, `unidad` and `activo`; the catalogue MUST expose only the goods eligible for fiado, and a `Producto` that is not `activo` MUST NOT be offered as the default price of a new charge. A `Producto` MUST NOT carry purchase cost, supplier or reorder information: the catalogue is a vocabulary, not a cost model.

**Verification:** integration

#### Scenario: The catalogue exposes only fiado-eligible goods

- GIVEN a seeded catalogue with one `activo` product and one that is not `activo`
- WHEN the catalogue is read
- THEN only the `activo` product is offered as a default price

#### Scenario: A withdrawn product stays readable in what was recorded

- GIVEN a product that was charged and is no longer `activo`
- WHEN the recorded charge is read
- THEN the charge still names that product and its price

### Requirement: PC-02 — `precio` is a default, not a constraint

The owner MAY charge an amount different from `Producto.precio`, and the amount actually charged is what the ledger records. A later change to `Producto.precio` MUST NOT alter any charge already recorded.

**Verification:** integration

#### Scenario: A catalogue price change rewrites nothing

- GIVEN a charge recorded at 1,00 € against a product priced 1,20 €
- WHEN the catalogue price becomes 1,50 €
- THEN the recorded charge still reads 1,00 €

#### Scenario: A price above the catalogue default is accepted

- GIVEN a product priced 1,20 €
- WHEN the owner charges 1,35 €
- THEN the charge is accepted at 1,35 € and the catalogue price is unchanged

### Requirement: PC-03 — The catalogue is readable and seeded

The catalogue MUST be readable by the `dueño` and MUST be seeded with the goods the demo shop puts on the tab, including the seeded `Producto` priced 1,20 €. The seed MUST be re-runnable without duplicating a `Producto`.

**Verification:** integration

#### Scenario: The seeded catalogue is idempotent

- GIVEN the demo dataset has been seeded
- WHEN the seed runs a second time
- THEN the count of `Producto` rows is unchanged and the seeded product still reads 1,20 €
