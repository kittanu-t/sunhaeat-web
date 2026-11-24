# SunHaEat Web

**Find places to eat across Thailand's 20 northeastern provinces, with a map and a Thai chat assistant that says what it does not know.**

Built as an NLP/AI portfolio project. A successor to the [SunHaEat LINE bot](https://github.com/kittanu-t/SunHaEat), with new data, a new stack and a web security design. It is not affiliated with any restaurant listed.

> Status: release 1 is built and tested locally. Not deployed yet. Gemini has not been evaluated yet; see [Evaluation](#evaluation).

## What it does

- **Search and map** over 30,348 real places from open data, plus 12 clearly labelled fictional places that show a complete page.
- **Place pages** that print "no data yet" instead of hiding or guessing a price, menu or opening time.
- **Free chat**: Thai rules read the question first. Gemini is called only when rules are not enough, may only return filters and IDs from a supplied list, and never writes the answer.
- **Guided chat**: five questions, no language model, works when AI is off.

![Search results and map on desktop](docs/images/search-desktop.png)

| Phone search | Chat |
|---|---|
| ![Phone search](docs/images/home-phone.png) | ![Chat on a phone](docs/images/chat1-phone.png) |

## How it works

```text
Browser -> Next.js (Vercel) -> FastAPI (Vercel Python) -> Postgres + PostGIS (Supabase)
   |         signed BFF            rules, search, quota
   '- MapLibre + OpenFreeMap          '-> Gemini (optional; rules answer when it fails)
```

| Folder | Contents |
|---|---|
| `apps/web` | Next.js 16 pages and the BFF: guest session, Turnstile, HMAC signing, CSP |
| `apps/api` | FastAPI: search, two chat modes, atomic quotas |
| `pipeline` | Overture extract, filtering, dedupe, Thai food tagging, transactional import |
| `supabase/migrations` | Schema, row-level security, least-privilege runtime role |
| `eval` | 126 draft questions, metrics, runner |

Design decisions and evidence: [design](docs/superpowers/specs/2026-11-24-sunhaeat-web-design.md), [data gate](docs/evidence/2026-11-24-data-gate.md), [dataset build](docs/evidence/dataset-build.md), [threat model](docs/threat-model.md).

## Run it

Needs Node 24, Python 3.12, [uv](https://docs.astral.sh/uv/) and Docker (throwaway PostGIS for tests).

```sh
npm ci
uv sync --project apps/api
npm test -w apps/web                                   # BFF and security unit tests
uv run --project apps/api --directory apps/api pytest  # API, RLS, pipeline and metrics on real Postgres
npx -w apps/web playwright install chromium
npm run e2e -w apps/web                                # build, then browser tests on phone and desktop sizes
```

To rebuild the dataset (about 130 MB download), from the repository root with `PYTHONPATH="apps/api;."` on Windows or `apps/api:.` elsewhere:

```sh
uv run --project apps/api python pipeline/fetch_overture.py data/raw
uv run --project apps/api python -m pipeline.build_dataset data/raw data/build
IMPORT_DATABASE_URL=... uv run --project apps/api python -m pipeline.import_dataset data/build
```

Configuration is listed in [.env.example](.env.example). Deployment and recovery: [operations](docs/operations.md).

## Evaluation

Only the rules system has been measured, and only on the 46-question **dev** split that was also used to fix parser bugs (slot F1 micro 0.953, macro 0.934 on 20 questions; four questions showed places that break what was really asked). Questions were drafted by the same assistant that wrote the rules and have not been reviewed by a person, so these numbers are optimistic. The 80-question test split is untouched. Details and limits: [eval-r1](docs/evidence/eval-r1.md).

## Measured locally

Lighthouse 12 mobile, three runs each on the production build with the real dataset: home 93/94/94, real place page 97/96/96, demo place page 96/97/96, chat 96/95/95; accessibility 100 on all four. Phones load the map only when asked. Hosted numbers will differ.

## Data and licences

- Code: [MIT](LICENSE).
- Places: [Overture Maps](https://overturemaps.org) release 2026-11-18.0, from Meta and Microsoft (CDLA-Permissive-2.0) and AllThePlaces (CC0-1.0), filtered, deduplicated and retagged. The dataset is not in this repository.
- Map: OpenFreeMap, © OpenMapTiles, data © OpenStreetMap contributors. See [NOTICE](NOTICE).
- The source has no prices, menus, reviews or opening hours, and almost no operating status. Phone numbers are deliberately not imported.
