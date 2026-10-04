"""Audit C regression tests: the private-case tripwire survives look-alike spellings; unsafe source URLs are refused."""

import json

import pytest
from tests.conftest import make_claim

from atlas.db import AtlasDB
from atlas.privacy import contains_private_marker
from atlas.store import PublicStore

VARIANTS = [
    "CASE-SYN-0001", "case-syn-0001", "CASE\u200b-SYN-0001", "CASE‑SYN‑0001", "CASE SYN 0001",
    "ＣＡＳＥ-ＳＹＮ-0001", "Case_Syn_7", "case­-syn-12",
]


@pytest.mark.parametrize("text", VARIANTS)
def test_every_disguised_form_of_the_private_marker_is_detected(text):
    assert contains_private_marker(f"patient {text} notes")


@pytest.mark.parametrize("text", ["a case of synthetic disease", "in this case synthesis was low", "case study 12", "SYN:disease-a"])
def test_ordinary_text_is_not_mistaken_for_the_marker(text):
    assert not contains_private_marker(text)


def test_the_public_database_refuses_every_disguised_marker():
    db = AtlasDB()
    for i, text in enumerate(VARIANTS):
        with pytest.raises(ValueError, match="private"):
            db.put(make_claim(f"CLAIM:p{i}", "PERTURBS_MECHANISM", source_span=f"note {text}"))


def test_an_upload_carrying_the_marker_is_quarantined_not_stored():
    store = PublicStore()
    payload = {
        "claim_id": "CLAIM:u1", "subject_id": "MONDO:0000001", "predicate": "PERTURBS_MECHANISM",
        "object_id": "HP:0000001", "source_url": "https://example.invalid/x", "source_span": "patient CASE\u200b-SYN-0007 jane",
        "lineage_id": "STUDY:u", "contributor": "someone",
    }
    assert store.ingest_lab_finding(payload) is None and "private" in store.quarantine[0]["error"]


def test_a_row_with_the_marker_written_straight_into_the_file_is_never_served(tmp_path):
    import sqlite3

    from atlas.api.claimstore import load_claims

    path = tmp_path / "atlas.db"
    db = AtlasDB(path)
    db.put(make_claim("CLAIM:ok", "PERTURBS_MECHANISM"))
    db.close()
    conn = sqlite3.connect(path)
    bad = json.loads(make_claim("CLAIM:leak", "PERTURBS_MECHANISM", source_span="CASE-SYN-0001 x").model_dump_json())
    conn.execute("INSERT INTO claims (claim_id, subject_id, predicate, object_id, source_type, review_state, lineage_id, json) "
                 "VALUES (?,?,?,?,?,?,?,?)", ("CLAIM:leak", "MONDO:0000001", "PERTURBS_MECHANISM", "HP:0000001", "synthetic_fixture",
                                                "unreviewed", "STUDY:s1", json.dumps(bad)))
    conn.commit()
    conn.close()
    assert set(load_claims(path)) == {"CLAIM:ok"}


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,<script>1</script>", "file:///etc/passwd", "ftp://x/y", ""])
def test_a_claim_cannot_carry_an_unsafe_source_url(url):
    with pytest.raises(ValueError):
        make_claim("CLAIM:x", "PERTURBS_MECHANISM", source_url=url)


@pytest.mark.parametrize("url", ["https://doi.org/10.1000/x", "http://example.org/a", "atlas:ai-hypothesis", "local:robotics/simulate.py#run"])
def test_web_and_internal_source_urls_are_accepted(url):
    assert make_claim("CLAIM:x", "PERTURBS_MECHANISM", source_url=url).source_url == url
