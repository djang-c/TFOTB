"""On-demand research endpoint tests with a fake runner (no network, no model, no store writes)."""

import pytest
from fastapi.testclient import TestClient

from atlas.api import create_app
from atlas.api.settings import Settings

SYN = "/api/entities/SYN:disease-a"


def make(tmp_path, runner=None, **kw):
    if kw.get("research_enabled") and "research_token" not in kw:
        kw["research_token"] = "tok"  # enabled research always needs a token (it fails closed without one)
    s = Settings(real_search=False, store_path=tmp_path / "store" / "atlas.db", **kw)
    app = create_app(s)
    app.state.research_runner = runner
    client = TestClient(app)
    if s.research_token:
        client.headers.update({"X-Research-Token": s.research_token})
    return client, app


def fake_runner(result=None, fail=None):
    def runner(request, terms):
        def work():
            if fail:
                raise fail
            return result or {"terms_seen": terms, "claims_added": 3, "papers": []}

        return work

    return runner


def test_research_is_off_by_default_and_says_so(tmp_path):
    c, _ = make(tmp_path)
    assert c.get("/api/research").json()["enabled"] is False
    r = c.post("/api/research", json={"query": "x"})
    assert r.status_code == 403 and "turned off" in r.json()["detail"]


def test_an_enabled_server_runs_a_job_in_the_background_and_reports_the_result(tmp_path):
    c, app = make(tmp_path, fake_runner(), research_enabled=True)
    r = c.post("/api/research", json={"query": "Niemann-Pick type C lysosome"})
    assert r.status_code == 202 and r.json()["terms"] == ["Niemann-Pick type C lysosome"]
    jid = r.json()["job_id"]
    app.state.jobs.wait(jid)
    done = c.get(f"/api/research/{jid}").json()
    assert done["status"] == "done" and done["result"]["claims_added"] == 3 and done["error"] is None


def test_an_entity_is_turned_into_its_name_and_unknown_entities_are_404(tmp_path):
    c, _ = make(tmp_path, fake_runner(), research_enabled=True)
    r = c.post("/api/research", json={"entity_id": "SYN:disease-a"})
    assert r.status_code == 202 and len(r.json()["terms"]) == 1 and r.json()["terms"][0]
    assert c.post("/api/research", json={"entity_id": "SYN:nope"}).status_code == 404
    assert c.post("/api/research", json={}).status_code == 422


def test_a_failed_job_reports_its_error_and_the_server_keeps_working(tmp_path):
    c, app = make(tmp_path, fake_runner(fail=RuntimeError("no reference files")), research_enabled=True)
    jid = c.post("/api/research", json={"query": "x"}).json()["job_id"]
    app.state.jobs.wait(jid)
    j = c.get(f"/api/research/{jid}").json()
    assert j["status"] == "failed" and "RuntimeError" in j["error"] and "no reference files" not in j["error"]
    assert c.get("/api/health").status_code == 200


def test_the_token_is_required_and_a_wrong_or_odd_token_is_a_401_not_a_crash(tmp_path):
    c, _ = make(tmp_path, fake_runner(), research_enabled=True, research_token="s3cret")
    c.headers.pop("X-Research-Token", None)
    assert c.post("/api/research", json={"query": "x"}).status_code == 401
    assert c.post("/api/research", json={"query": "x"}, headers={"X-Research-Token": "wrong"}).status_code == 401
    assert c.post("/api/research", json={"query": "x"}, headers={"X-Research-Token": "é".encode("latin-1")}).status_code == 401
    ok = c.post("/api/research", json={"query": "x"}, headers={"X-Research-Token": "s3cret"})
    assert ok.status_code == 202


def test_enabling_research_without_a_token_fails_closed(tmp_path):
    from atlas.api import create_app as make_app

    app = make_app(Settings(real_search=False, store_path=tmp_path / "s" / "a.db", research_enabled=True, research_token=""))
    c = TestClient(app)
    r = c.post("/api/research", json={"query": "x"})
    assert r.status_code == 503 and "not configured" in r.json()["detail"]


def test_the_job_list_is_only_shown_to_a_caller_with_the_token(tmp_path):
    c, app = make(tmp_path, fake_runner(), research_enabled=True)
    jid = c.post("/api/research", json={"query": "secret topic"}).json()["job_id"]
    app.state.jobs.wait(jid)
    assert c.get("/api/research").json()["recent_jobs"][0]["terms"] == ["secret topic"]
    c.headers.pop("X-Research-Token")
    assert c.get("/api/research").json()["recent_jobs"] == []


def test_jobs_are_rate_limited_per_hour(tmp_path):
    c, _ = make(tmp_path, fake_runner(), research_enabled=True, research_max_jobs_per_hour=2)
    codes = [c.post("/api/research", json={"query": f"q{i}"}).status_code for i in range(3)]
    assert codes == [202, 202, 429]


def test_request_cannot_set_caps_or_extra_fields_and_long_queries_are_refused(tmp_path):
    c, _ = make(tmp_path, fake_runner(), research_enabled=True)
    assert c.post("/api/research", json={"query": "x", "max_papers": 500}).status_code == 422
    assert c.post("/api/research", json={"query": "x" * 201}).status_code == 422


def test_unknown_job_is_404(tmp_path):
    c, _ = make(tmp_path, fake_runner(), research_enabled=True)
    assert c.get("/api/research/nope").status_code == 404


def test_the_real_runner_fails_plainly_when_reference_files_are_missing(tmp_path):
    from atlas.research import ResearchUnavailable, load_extraction_resolver

    with pytest.raises(ResearchUnavailable, match="not available on this server"):
        load_extraction_resolver(tmp_path)
