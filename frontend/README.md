# TFOTB web app

The explorer for The Flight of The Buffalo. A single-page app (TanStack Start in SPA mode, React, Tailwind, three.js). It holds **no data of its own**: every screen reads from the API in `../src/atlas/api`, and if the API is down it says so.

Layout: a bar across the top with the standing pages (Home, Symptoms, Simulation) and the search. Once something is searched, a second row names it and offers its views: Dossier, Graph, Clusters (the Graph page has no Dossier link). The search opens the dossier; on the Graph and Clusters pages it re-centres that page instead. The views follow the entry being looked into (remembered in this browser only).

| Page | What it shows | API |
| --- | --- | --- |
| `/` | Search, live metrics, example diseases with their related-disease counts, categories | `/meta`, `/search`, `/terms`, `/entities/{id}/related-diseases` |
| `/entity/{id}` | The dossier, as a document (no graph): at-a-glance counts; what is known; related diseases (one row per disease with every reason and its origin, or "No similarities found"); evidence from papers beside hypotheses and treatment ideas; gaps, next steps, researchers and patient groups in capped paired rows; action cards (collapsed); Markdown and JSON export | `/entities/{id}` and its sub-routes, `/claims/{id}` |
| `/explorer?id=` | The graph, full screen, with a small panel about the selected node: its links (each opens its evidence) and the route from the centre. No dossier content and no link into the dossier                                                                                                                                      | `/entities/{id}/graph`, `/entities/{id}/routes`     |
| `/clusters?id=` | Only after a search. Explains what a cluster is (diseases sharing one specific thing with the searched disease), why it helps and what it is not; one card per shared gene, mechanism, parent disease, symptom pattern or proposed link. Without `id` it asks for a search | `/entities/{id}/related-diseases` |
| `/symptoms`     | Compose symptoms as chips (prefix "no" for absent); candidate diseases with coverage, linked genes, "Take to clinic" and export                                                                                                                                                                                             | `/symptoms?q=`                                      |
| `/simulation` | Overnight experiments: the researcher defines parameters (units, ranges, largest change per run), the instrument and plate, pass criteria and "if it fails, change X" rules; the robot plan is checked (pipette range, stock, DMSO, wells, tips, MuJoCo motion) and replayed; each run is scored (Z', CVs, 4PL fit, plateaus) from MEASURED plate-reader readings or labelled SYNTHETIC ones; the next run changes only what the rules allow (optionally ordered by an AI); the log shows every run | `/experiments/example`, `/experiments/plan`, `/experiments/step`, `/experiments/overnight` |

**Design.** The screens follow the Lovable design in `Downloads/gene-link-play(1)` (home with metrics, seed cluster and categories; dossier page; explorer; symptom composer; simulation). Departures, each for honesty or because the API differs: the dossier no longer repeats the graph (owner direction 2026-10-04); the explorer's "Hops" control is "Nodes" because the API has no hop depth; the path explorer picks its target by search because the catalogue has tens of thousands of entries; the simulation page is rebuilt around the researcher's closed-loop experiment (owner direction 2026-10-04); a Clusters page and a Related diseases list are added.

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
