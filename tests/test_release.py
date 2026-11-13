import sys

from beammpy import cli
from conftest import headers


def test_cli_password_reset_revokes_sessions_and_preserves_account(app, client, monkeypatch):
    app.extensions["shutdown"]()
    passwords = iter(["changed-password-123", "changed-password-123"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(passwords))
    monkeypatch.setattr(sys, "argv", ["beammpy", "reset-password", "--data-dir", str(app.config["DATA_DIR"]), "--username", "admin"])
    cli.main()
    with app.extensions["store"].connection() as db:
        assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM auth_sessions").fetchone()[0] == 0
    assert client.get("/api/servers").status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "changed-password-123"}, headers=headers(client)).status_code == 200


def test_frontend_and_assets_are_served_and_legacy_routes_redirect(app, client):
    import re
    response = client.get("/")
    assert response.status_code == 200
    assert "BeamMPY" in response.text
    for path in re.findall(r'(?:src|href)="(/assets/[^\"]+)"', response.text):
        assert client.get(path).status_code == 200
    assert client.get("/assets/missing.js").status_code == 404
    assert client.get("/dashboard").location == "/servers"
    assert client.get("/register").location == "/setup"
    assert client.get("/licenses/M3E-Apache-2.0.txt").status_code == 200
