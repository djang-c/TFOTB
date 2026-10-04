#!/usr/bin/env bash
# Re-read every paper already in the claim store with the OpenAI models set in .env, into a fresh store, then
# rebuild hypotheses, names and authors, and repackage deploy/store. The previous store is kept in data/cache/.
# Cost is bounded by config/ingest_policy.json (papers per run, characters per paper, output tokens per call).
#
#   bash scripts/reread_with_openai.sh
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
: "${OPENAI_API_KEY:?OPENAI_API_KEY is not set in .env}" "${OPENAI_MODEL_FAST:?set OPENAI_MODEL_FAST in .env}"
: "${OPENAI_MODEL_REASONING:?set OPENAI_MODEL_REASONING in .env}"
PY=".venv/bin/python"
export PYTHONPATH=src LLM_PROVIDER=openai

pmids=$($PY -c "
import json
rows = [json.loads(x) for x in open('data/store/ingest_log.jsonl') if x.strip()]
print(' '.join(sorted({r['source_id'].split(':', 1)[1] for r in rows if r.get('status') == 'ingested'})))")
echo "re-reading $(wc -w <<<"$pmids" | tr -d ' ') papers with $OPENAI_MODEL_FAST"

backup="data/cache/store-before-reread-$(date +%Y%m%dT%H%M%S)"
mkdir -p data/cache && mv data/store "$backup" && mkdir -p data/store
[ -f "$backup/terms.jsonl" ] && cp "$backup/terms.jsonl" data/store/  # visitors' verified terms are not claims
echo "previous store kept in $backup"

# The policy caps papers per run, so run until every paper is done (already-read papers are skipped).
for _ in 1 2 3 4 5 6; do $PY scripts/ingest_papers.py --pmids $pmids; done
$PY scripts/generate_hypotheses.py
$PY scripts/backfill_papers.py
$PY scripts/backfill_labels.py
$PY scripts/export_deploy_store.py
$PY -c "
import collections, json
c = collections.Counter(json.loads(x)['extraction_method'] for x in open('data/store/snapshot/claims.jsonl') if x.strip())
print('claims by model:', dict(c))"
