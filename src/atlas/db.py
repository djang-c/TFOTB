"""SQLite persistence + versioned JSON snapshot (PLAN: T02). Stdlib `sqlite3` only.

Each table stores indexed columns for lookup plus the full validated Pydantic record as JSON.
Rows are re-validated on read. This is the public evidence store: synthetic/private case data
(`CASE-SYN-*`) is refused at write time and lives only in `atlas.store.CaseStore`.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from atlas.schemas import (
    SCHEMA_VERSION,
    ActionCard,
    AssetResult,
    Claim,
    CoverageManifest,
    Entity,
)

M = TypeVar("M", bound=BaseModel)

# table -> (model, primary key field, extra indexed columns)
TABLES: dict[str, tuple[type[BaseModel], str, tuple[str, ...]]] = {
    "entities": (Entity, "id", ("type", "source_type", "review_state", "identity_status")),
    "claims": (
        Claim,
        "claim_id",
        ("subject_id", "predicate", "object_id", "source_type", "review_state", "lineage_id"),
    ),
    "coverage_manifests": (CoverageManifest, "manifest_id", ()),
    "assets": (AssetResult, "asset_id", ("asset_kind",)),
    "action_cards": (ActionCard, "card_id", ("kind", "entity_id")),
}
_BY_MODEL = {model: table for table, (model, _, _) in TABLES.items()}
PRIVATE_MARKER = "CASE-SYN-"


def canonical(model: BaseModel) -> str:
    """Byte-stable JSON for a record: sorted keys, no whitespace, ISO dates."""
    return json.dumps(
        json.loads(model.model_dump_json()), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False,
    )


class AtlasDB:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.conn = sqlite3.connect(str(path))
        try:
            self._init_schema()
        except Exception:
            self.conn.close()
            raise

    def _init_schema(self) -> None:
        c = self.conn
        c.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL) STRICT")
        found = c.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if found is None:
            c.execute("INSERT INTO meta VALUES ('schema_version', ?)", (SCHEMA_VERSION,))
        elif found[0] != SCHEMA_VERSION:
            raise RuntimeError(
                f"database schema {found[0]} != code schema {SCHEMA_VERSION}; rebuild it"
            )
        for table, (_, pk, cols) in TABLES.items():
            col_sql = "".join(f", {col} TEXT" for col in cols)
            c.execute(
                f"CREATE TABLE IF NOT EXISTS {table} "
                f"({pk} TEXT PRIMARY KEY{col_sql}, json TEXT NOT NULL) STRICT"
            )
            for col in cols:
                c.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_{col} ON {table}({col})")
        c.execute(
            "CREATE TABLE IF NOT EXISTS quarantine "
            "(seq INTEGER PRIMARY KEY, payload TEXT NOT NULL, error TEXT NOT NULL) STRICT"
        )
        c.commit()

    # --- writes ---------------------------------------------------------------------------

    def put(self, record: BaseModel) -> None:
        """Insert a validated record. Existing IDs are never overwritten."""
        table = _BY_MODEL[type(record)]
        _, pk, cols = TABLES[table]
        body = canonical(record)
        if PRIVATE_MARKER in body:
            raise ValueError("private/synthetic case data cannot enter the public store")
        self._check_refs(record)
        dumped = record.model_dump(mode="json")
        values = [dumped[pk], *(_text(dumped.get(col)) for col in cols), body]
        names = ", ".join((pk, *cols, "json"))
        marks = ", ".join("?" * len(values))
        try:
            with self.conn:
                self.conn.execute(f"INSERT INTO {table} ({names}) VALUES ({marks})", values)
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"{table}: {dumped[pk]} already exists; records are immutable") from exc

    def quarantine(self, payload: Any, error: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO quarantine (payload, error) VALUES (?, ?)",
                (json.dumps(payload, sort_keys=True, default=str), error[:300]),
            )

    def _check_refs(self, record: BaseModel) -> None:
        if isinstance(record, ActionCard):
            missing = [c for c in record.claim_ids if not self._exists("claims", c)]
            missing += [a for a in record.asset_ids if not self._exists("assets", a)]
            if record.coverage_manifest_id and not self._exists(
                "coverage_manifests", record.coverage_manifest_id
            ):
                missing.append(record.coverage_manifest_id)
        elif isinstance(record, AssetResult):
            missing = [c for c in record.relevance_claim_ids if not self._exists("claims", c)]
        else:
            return
        if missing:
            raise ValueError(f"unknown references: {sorted(missing)}")

    def _exists(self, table: str, key: str) -> bool:
        pk = TABLES[table][1]
        q = f"SELECT 1 FROM {table} WHERE {pk} = ?"
        return self.conn.execute(q, (key,)).fetchone() is not None

    # --- reads ----------------------------------------------------------------------------

    def get(self, model: type[M], key: str) -> M | None:
        table = _BY_MODEL[model]
        pk = TABLES[table][1]
        row = self.conn.execute(f"SELECT json FROM {table} WHERE {pk} = ?", (key,)).fetchone()
        return None if row is None else model.model_validate_json(row[0])

    def all(self, model: type[M]) -> list[M]:
        table = _BY_MODEL[model]
        pk = TABLES[table][1]
        rows = self.conn.execute(f"SELECT json FROM {table} ORDER BY {pk}").fetchall()
        return [model.model_validate_json(r[0]) for r in rows]

    def quarantined(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT payload, error FROM quarantine ORDER BY seq").fetchall()
        return [{"payload": json.loads(p), "error": e} for p, e in rows]

    def close(self) -> None:
        self.conn.close()


def _text(value: Any) -> str | None:
    return None if value is None else str(value)


# --- snapshot ------------------------------------------------------------------------------

# Dependency order: referenced tables load before the records that reference them.
SNAPSHOT_ORDER = ("entities", "claims", "coverage_manifests", "assets", "action_cards")


def export_snapshot(db: AtlasDB, out_dir: str | Path, dataset_version: str, built_at: str) -> dict:
    """Write one sorted JSONL file per table plus manifest.json with per-file SHA-256.

    `built_at` is passed in (not read from the clock) so identical inputs give identical bytes.
    Row counts come from the rows actually written.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files: dict[str, dict[str, Any]] = {}
    for table in SNAPSHOT_ORDER:
        model = TABLES[table][0]
        lines = [canonical(r) + "\n" for r in db.all(model)]
        data = "".join(lines).encode()
        (out / f"{table}.jsonl").write_bytes(data)
        files[f"{table}.jsonl"] = {"rows": len(lines), "sha256": hashlib.sha256(data).hexdigest()}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "dataset_version": dataset_version,
        "built_at": built_at,
        "files": files,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def load_snapshot(snap_dir: str | Path, db_path: str | Path = ":memory:") -> AtlasDB:
    """Rebuild a database from a snapshot, refusing tampered or mismatched files.

    All files are verified before anything is written; a failed load leaves no partial DB file.
    The quarantine table is never exported: it holds unvalidated upload payloads.
    """
    snap = Path(snap_dir)
    manifest = json.loads((snap / "manifest.json").read_text())
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"snapshot schema {manifest['schema_version']} != {SCHEMA_VERSION}")
    expected = {f"{t}.jsonl" for t in SNAPSHOT_ORDER}
    if set(manifest["files"]) != expected:
        raise ValueError(f"snapshot manifest lists {sorted(manifest['files'])}, expected {sorted(expected)}")
    lines: dict[str, list[str]] = {}
    for table in SNAPSHOT_ORDER:
        name = f"{table}.jsonl"
        data = (snap / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest["files"][name]["sha256"]:
            raise ValueError(f"checksum mismatch: {name}")
        lines[table] = data.decode().splitlines()
        if len(lines[table]) != manifest["files"][name]["rows"]:
            raise ValueError(f"row count mismatch: {name}")

    on_disk = str(db_path) != ":memory:"
    if on_disk and Path(db_path).exists():
        raise ValueError(f"{db_path} already exists; load into a new path")
    db = AtlasDB(db_path)
    try:
        for table in SNAPSHOT_ORDER:
            model = TABLES[table][0]
            for line in lines[table]:
                db.put(model.model_validate_json(line))
    except Exception:
        db.close()
        if on_disk:
            Path(db_path).unlink(missing_ok=True)
        raise
    return db
