# `fiado-confirmado`

**The charge that exists only after the PERSON confirms it.**

A corner shop sells on credit — the `fiado`. Today it lives in the
owner's head and in a notebook: the owner does not know how much is owed,
how old the debt is, or whether this customer is still worth trusting.
Some shops keep a spreadsheet, and the spreadsheet cannot answer a
question either.

This project makes the `fiado` a record with rules. The shop prepares a
figure; **the client answers from her own account** — she accepts or she
refuses — and **the charge exists only after she says yes**. Everything
else is derived from that: the outstanding, the ageing, the suspension,
the shop's real position.

## The three audiences

| Principal | What it is | What it does |
|---|---|---|
| `dueño` | a staff user, member of one shop | everything: the customers, the credit policy, the book, the day close, the proposals |
| `dependiente` | a staff user, member of one shop | the drawer, the day close, and — since the N5 gate opened — the credit book through a **reduced schema**, plus the proposals **it prepared itself** |
| the **person** | **not a role**: she has her own account | her own links, her own charges, her own `fiado`s, and her own answer to the shop's question |

There is **no credential** and no third audience: a client without an
account cannot have a `fiado`, and without a `fiado` there is no debt to
pay.

## The stack

One service, one database, one origin — no second host, no CORS, no
worker, no Redis.

- **Backend** — Django 5.2 + Django REST Framework, in `backend/`
- **Frontend** — React 18 + TypeScript + Vite, in `frontend/`
- **Database** — PostgreSQL 16 (Neon in production, a local server for
  the tests)
- **Deploy** — a Render web service serving the API *and* the built
  bundle from the same origin through WhiteNoise

## Quick start

```powershell
# 1. The toolchain: Python 3.14, the pinned dependencies, PostgreSQL 16
#    on 127.0.0.1:5433 and the `fiado_test` database. Everything it
#    creates lives OUTSIDE the repository.
.\scripts\setup-toolchain.ps1

# 2. The database and the demo data
$env:DATABASE_URL = "postgres://fiado:fiado@127.0.0.1:5433/fiado"
python backend\manage.py migrate
python backend\manage.py seed_demo

# 3. The API, and the bundle
python backend\manage.py runserver
npm --prefix frontend install
npm --prefix frontend run dev
```

## The tests

```powershell
.\scripts\test.ps1              # unit + integration
.\scripts\test.ps1 -Unit        # unit only, no database needed
```

Or directly — `pytest` is not on the PATH, the form is always
`python -m pytest`:

```
python -m pytest backend/tests/unit -q          # no database, by construction
python -m pytest backend/tests/integration -q   # PostgreSQL 16 on :5433
```

**The integration suite never runs on SQLite** — a migration executes raw
SQL that SQLite does not understand, and the suite would fail with a
syntax error that says nothing about the code. `scripts/test.ps1` sets
the environment it needs.

The end-to-end suite runs against the **deployed public URL**:

```
$env:PUBLIC_URL = "https://fiado-confirmado.onrender.com"
python -m pytest backend/tests/e2e -q
```

## The demo accounts

`seed_demo` creates a demo shop with one account per staff role, and a
person who is a trusted client of it.

| Account | Password | What it sees |
|---|---|---|
| `dueno@tienda.test` | `tienda-demo-2026` | the whole board: the equation, the ladder, the close, the proposals, the proposed payments |
| `dependiente@tienda.test` | `tienda-demo-2026` | the drawer, the close, and the credit book **reduced** |
| `ana` | `tienda-demo-2026` | her own account: her links, her charges, her `fiado`s, and her answer |

The seed is **idempotent**: running it twice leaves the same demo, and
the build runs it on every deploy.

## The deployment

<https://fiado-confirmado.onrender.com> — HTTPS, `DEBUG=False`, one
service serving both the pages and the API, and the health endpoint at
`/health/`.

The build installs the dependencies, builds the bundle, collects the
static files, runs the migrations and seeds the demo. **The seed is
part of the deploy**: a deploy that has not seeded yet is a deploy whose
demo data is not there yet.

## The layout

```
backend/            Django + DRF
  tienda/           the models, the rules and the API
    domain/         the pure rules, with no ORM and no HTTP
    api/            the serializers, the views and the routes
  tests/
    unit/           the pure rules, with no database by construction
    integration/    the Django test client against PostgreSQL
    e2e/            the deployed public URL
frontend/           React + TypeScript + Vite
  src/surfaces/     the three screens: the board, the shop's screen, the person's account
  src/components/   one component per piece of a payload
openspec/changes/fiado-confirmado/
  proposal.md       the proposal, the scope and the success criteria
  design.md         the design: the model, the rules, the routes and the permissions
  specs/            one directory per capability, with its requirements
  state.yaml        the register: what is decided, what is built, what is left
```

## What to read first

1. `openspec/changes/fiado-confirmado/proposal.md` — the problem, the
   scope and the success criteria.
2. `openspec/changes/fiado-confirmado/design.md` — the model, the rules
   and the boundaries. **Section 19** says which questions are still
   open and who owns them.

## What this project does NOT claim

**The knowledge base is a declared design hypothesis, not field
evidence.** No interview with a shop owner was run for this variant, and
none is going to be: the owner closed that round on 2026-11-25. The
scope, the four `Regla` gates and the account rewrite are the owner's
decisions taken under that hypothesis, and the design says so where it
matters.

Two things are deliberately **not** built, and the register says why:

- **The stock ceiling** (`CP-07`, Regla 6) — the rule is in the domain
  and the route is not; the proposal listed it as an acceptable
  reduction.
- **The validation round with shop owners** — closed, and the instrument
  is kept as the record of the method that was available.

## The language

Prose in English; **every domain identifier, entity, field and API field
stays in the project's Spanish vocabulary** (`fiado`, `cargo`, `pago`,
`cliente`, `dueño`, `dependiente`, `vinculo`, `propuesta`, `caja`).
