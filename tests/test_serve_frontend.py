"""The API can serve the built web app from the same address (FRONTEND_DIST)."""

from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.api.settings import Settings


def _client(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "_shell.html").write_text("<html>shell</html>")
    (tmp_path / "assets" / "a.js").write_text("console.log(1)")
    (tmp_path.parent / "secret.txt").write_text("outside")
    return TestClient(create_app(Settings(frontend_dist=tmp_path, real_search=False)))


def test_serves_files_and_falls_back_to_the_shell_for_app_routes(tmp_path):
    c = _client(tmp_path)
    assert c.get("/assets/a.js").text == "console.log(1)"
    for route in ("/", "/10x", "/entity/MONDO:0008767"):
        r = c.get(route)
        assert r.status_code == 200 and "shell" in r.text


def test_api_paths_are_never_answered_with_the_shell(tmp_path):
    c = _client(tmp_path)
    assert c.get("/api/health").json() == {"status": "ok"}
    assert c.get("/api/does-not-exist").status_code == 404


def test_cannot_read_files_outside_the_folder(tmp_path):
    c = _client(tmp_path)
    r = c.get("/..%2fsecret.txt")
    assert "outside" not in r.text
    assert "outside" not in c.get("/../secret.txt").text


def test_off_by_default():
    c = TestClient(create_app(Settings(real_search=False)))
    assert c.get("/10x").status_code == 404
