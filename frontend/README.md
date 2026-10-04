# TFOTB web app

The explorer for The Flight of The Buffalo. A single-page app (TanStack Start in SPA mode, React, Tailwind, three.js). It holds **no data of its own**: every screen reads from the API in `../src/atlas/api`, and if the API is down it says so.

| Page            | What it shows                                                                                                                                                                                                            | API                                                 |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------- |
| `/`             | Search, live counts, entry points                                                                                                                                                                                        | `/meta`, `/search`                                  |
| `/explorer?id=` | Evidence graph; tabs: Overview (what is known, hypotheses and treatment ideas, what is not known, researchers, patient groups), Connections (related diseases, evidence label, route), Action cards, Claims and evidence | `/entities/{id}` and its sub-routes, `/claims/{id}` |
| `/symptoms?q=`  | Candidate diseases for described symptoms (research hypotheses)                                                                                                                                                          | `/symptoms`                                         |
| `/clusters`     | Diseases grouped by a shared observed mechanism                                                                                                                                                                          | `/clusters`                                         |
| `/simulation`   | Replay of a recorded workflow simulation                                                                                                                                                                                 | `/simulations/{id}`                                 |

**Unknown terms.** Press Enter on something the catalogue has never seen and the API (`POST /lookup`) checks it against NLM MeSH and Europe PMC. A verified medical term is added to the shared catalogue with the papers found; anything else is kept only in this browser (`localStorage`) and labelled unverified. Text that looks like a personal identifier is refused before anything is sent.

## Run

```bash
make dev                  # API on :8000 and this app on :3000   (or: cd frontend && npm ci && npm run dev)
npm run lint && npm run typecheck && npm test && npm run build
```

`VITE_API_BASE` (build time) is the API address; the default is `http://localhost:8000/api`. The build writes a static site to `dist/client`; every route is served by `_shell.html` (see `vercel.json`).

## Browser smoke test

`npm run e2e` drives the real app against the real API in headless Google Chrome and checks what a visitor sees (search, the CLN3 and Niemann-Pick link and its label, the evidence drawer and its DOI link, treatment ideas labelled as hypotheses, symptoms, clusters, simulation, an unverified term kept locally, identifiers refused). It needs the API and `npm run dev` running and the reference data downloaded. Set `CHROME_PATH` if Chrome is not in the macOS default location.

`E2E_LOOKUP_VERIFIED=1` also checks a verified lookup. That **adds a real term to the API's shared term store** and uses the internet, so run it against a throwaway API: copy `data/store` somewhere, start `uvicorn` with `STORE_PATH=<copy>/atlas.db CORS_ORIGINS=http://localhost:3001`, start the app with `VITE_API_BASE=http://localhost:8001/api npm run dev -- --port 3001`, and pass `BASE_URL=http://localhost:3001`.
