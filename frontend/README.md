# TFOTB web app

The explorer for The Flight of The Buffalo. A single-page app (TanStack Start in SPA mode, React, Tailwind, three.js). It holds **no data of its own**: every screen reads from the API in `../src/atlas/api`, and if the API is down it says so.

Layout: a vertical catalogue bar on the left (the one search box, the pages, the entry being looked into, the seed cluster) and the page on the right. The search opens the dossier; on the Graph and Clusters pages it re-centres that page instead. Graph and Clusters follow the entry being looked into (remembered in this browser only).

| Page            | What it shows                                                                                                                                                                                                                                                                                                               | API                                                 |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `/`             | Search, live metrics, seed cluster, categories                                                                                                                                                                                                                                                                              | `/meta`, `/search`, `/terms`                        |
| `/entity/{id}`  | The dossier, as a document (no graph): at-a-glance counts, then sections in two balanced columns: what is known, related diseases (evidence label and route), hypotheses and treatment ideas, evidence read from papers, what is not known, next steps, researchers, patient groups, action cards; Markdown and JSON export | `/entities/{id}` and its sub-routes, `/claims/{id}` |
| `/explorer?id=` | The graph, full screen, with a small panel about the selected node: its links (each opens its evidence) and the route from the centre. No dossier content and no link into the dossier                                                                                                                                      | `/entities/{id}/graph`, `/entities/{id}/routes`     |
| `/clusters?id=` | Groups around the entry: shared observed mechanism, shared gene, a direct link from a paper (hypothesis), similar symptoms; each member keeps its evidence label and the claims behind it. Below: every mechanism cluster in the stored papers                                                                              | `/entities/{id}/clusters`, `/clusters`              |
| `/symptoms`     | Compose symptoms as chips (prefix "no" for absent); candidate diseases with coverage, linked genes, "Take to clinic" and export                                                                                                                                                                                             | `/symptoms?q=`                                      |
| `/simulation`   | Replay of a recorded workflow simulation                                                                                                                                                                                                                                                                                    | `/simulations/{id}`                                 |

**Design.** The screens follow the Lovable design in `Downloads/gene-link-play(1)` (home with metrics, seed cluster and categories; dossier page; explorer; symptom composer; simulation). Departures, each for honesty or because the API differs: the top navigation is a left catalogue bar and the dossier no longer repeats the graph (owner direction 2026-10-04); the explorer's "Hops" control is "Nodes" because the API has no hop depth; the path explorer picks its target by search because the catalogue has tens of thousands of entries; "Live deck view" reads "Replay of a recorded run"; the hard-coded "Collisions 0" is replaced by recorded failures; a Clusters page and a Related diseases tab are added.

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
