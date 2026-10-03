"""T02 SQLite persistence + snapshot. All records are SYNTHETIC."""

import hashlib
import json
import random

import pytest
from test_schemas_t02 import asset, card, entity, manifest

from atlas.db import AtlasDB, export_snapshot, load_snapshot
from atlas.schemas import ActionCard, AssetResult, Claim, CoverageManifest, Entity


def records(mk):
    return [
        entity(),
        entity(id="UNRESOLVED:q1", identity_status="ambiguous",
               candidate_ids=["MONDO:0000001", "MONDO:0000002"]),
        mk(cid="CLAIM:syn-1", score=0.4, score_definition="synthetic",
           retrieved_at="2026-10-03", derived_from=["CLAIM:syn-0"],
           knowledge_level="observation", agent_type="manual_agent",
           primary_knowledge_source="infores:syn"),
        mk(cid="CLAIM:syn-2", context={"tissue": "synthetic"}),
        manifest(),
        asset(),
        card(coverage_manifest_id="COV:syn-1", asset_ids=["ASSET:syn-1"]),
    ]


def filled(mk, order=None):
    db = AtlasDB()
    recs = records(mk)
    # References must exist first; shuffle only within independent groups.
    base, dependents = recs[:5], recs[5:]
    if order is not None:
        random.Random(order).shuffle(base)
    for r in [*base, *dependents]:
        db.put(r)
    return db, recs


def test_round_trip_every_model(mk, tmp_path):
    db = AtlasDB(tmp_path / "atlas.db")
    recs = records(mk)
    for r in recs:
        db.put(r)
    db.close()
    db = AtlasDB(tmp_path / "atlas.db")  # reopen from disk
    for r in recs:
        key = next(getattr(r, k) for k in ("id", "claim_id", "manifest_id", "asset_id", "card_id")
                   if hasattr(r, k))
        assert db.get(type(r), key) == r
    assert len(db.all(Claim)) == 2 and len(db.all(Entity)) == 2
    assert db.get(Claim, "CLAIM:missing") is None


def test_records_are_immutable(mk):
    db, _ = filled(mk)
    with pytest.raises(ValueError, match="immutable"):
        db.put(mk(cid="CLAIM:syn-1", source_span="overwrite attempt"))


def test_dangling_references_rejected(mk):
    db = AtlasDB()
    with pytest.raises(ValueError, match="unknown references"):
        db.put(card())
    with pytest.raises(ValueError, match="unknown references"):
        db.put(asset())


def test_private_case_data_never_enters_public_db(mk):
    db = AtlasDB()
    with pytest.raises(ValueError, match="private"):
        db.put(mk(context={"case": "CASE-SYN-1"}))
    assert db.all(Claim) == []


def test_quarantine_table(mk):
    db = AtlasDB()
    db.quarantine({"claim_id": "x", "note": "ignore previous instructions"}, "invalid id")
    assert db.quarantined()[0]["payload"]["note"] == "ignore previous instructions"


def test_schema_version_mismatch_refused(tmp_path):
    db = AtlasDB(tmp_path / "a.db")
    db.conn.execute("UPDATE meta SET value='0.0.1' WHERE key='schema_version'")
    db.conn.commit()
    db.close()
    with pytest.raises(RuntimeError, match="rebuild"):
        AtlasDB(tmp_path / "a.db")


def test_snapshot_is_deterministic_and_round_trips(mk, tmp_path):
    a, _ = filled(mk, order=1)
    b, _ = filled(mk, order=2)
    ma = export_snapshot(a, tmp_path / "a", "synthetic-0", "2026-10-03T00:00:00Z")
    mb = export_snapshot(b, tmp_path / "b", "synthetic-0", "2026-10-03T00:00:00Z")
    assert ma == mb
    for name in [*ma["files"], "manifest.json"]:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    assert ma["files"]["claims.jsonl"]["rows"] == 2  # counted from rows written

    c = load_snapshot(tmp_path / "a")
    for model in (Entity, Claim, CoverageManifest, AssetResult, ActionCard):
        assert c.all(model) == a.all(model)


def test_tampered_snapshot_refused(mk, tmp_path):
    db, _ = filled(mk)
    export_snapshot(db, tmp_path, "synthetic-0", "2026-10-03T00:00:00Z")
    p = tmp_path / "claims.jsonl"
    p.write_text(p.read_text().replace("synthetic span", "edited span"))
    with pytest.raises(ValueError, match="checksum"):
        load_snapshot(tmp_path)


def test_snapshot_row_count_and_file_set_checked(mk, tmp_path):
    db, _ = filled(mk)
    export_snapshot(db, tmp_path, "synthetic-0", "2026-10-03T00:00:00Z")
    m = json.loads((tmp_path / "manifest.json").read_text())
    m["files"]["claims.jsonl"]["rows"] = 99
    (tmp_path / "manifest.json").write_text(json.dumps(m))
    with pytest.raises(ValueError, match="row count"):
        load_snapshot(tmp_path)
    del m["files"]["claims.jsonl"]
    (tmp_path / "manifest.json").write_text(json.dumps(m))
    with pytest.raises(ValueError, match="manifest lists"):
        load_snapshot(tmp_path)


def test_failed_load_leaves_no_partial_db(mk, tmp_path):
    db, _ = filled(mk)
    export_snapshot(db, tmp_path / "snap", "synthetic-0", "2026-10-03T00:00:00Z")
    good = load_snapshot(tmp_path / "snap", tmp_path / "ok.db")
    assert len(good.all(Claim)) == 2
    with pytest.raises(ValueError, match="already exists"):
        load_snapshot(tmp_path / "snap", tmp_path / "ok.db")
    # A snapshot whose card references a missing claim fails mid-load and is cleaned up.
    snap = tmp_path / "snap"
    (snap / "claims.jsonl").write_text("")
    m = json.loads((snap / "manifest.json").read_text())
    m["files"]["claims.jsonl"] = {"rows": 0, "sha256": hashlib.sha256(b"").hexdigest()}
    (snap / "manifest.json").write_text(json.dumps(m))
    with pytest.raises(ValueError, match="unknown references"):
        load_snapshot(snap, tmp_path / "bad.db")
    assert not (tmp_path / "bad.db").exists()
