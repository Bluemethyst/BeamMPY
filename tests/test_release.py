import sys
import pytest

from beammpy import cli
from conftest import headers


def test_cli_password_reset_revokes_sessions_and_preserves_account(app, client, monkeypatch):
    app.extensions["shutdown"]()
    passwords = iter(["resetCLI", "resetCLI"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(passwords))
    monkeypatch.setattr(sys, "argv", ["beammpy", "reset-password", "--data-dir", str(app.config["DATA_DIR"]), "--username", "admin"])
    cli.main()
    with app.extensions["store"].connection() as db:
        assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM auth_sessions").fetchone()[0] == 0
    assert client.get("/api/servers").status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "resetCLI"}, headers=headers(client)).status_code == 200


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


def test_local_maintenance_refuses_running_panel_without_prompting(app, monkeypatch):
    def unexpected(prompt):
        raise AssertionError("Must reject active panel before prompting")
    monkeypatch.setattr(cli.getpass, "getpass", unexpected)
    monkeypatch.setattr(sys, "argv", ["beammpy", "reset-password", "--data-dir", str(app.config["DATA_DIR"]), "--username", "admin"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2


def test_offline_first_admin_and_username_recovery_close_setup(tmp_path, monkeypatch, capsys):
    from beammpy import create_app
    passwords = iter(["firstCLI", "firstCLI"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(passwords))
    monkeypatch.setattr(sys, "argv", ["beammpy", "create-admin", "--data-dir", str(tmp_path), "--username", "owner"])
    cli.main()
    with pytest.raises(SystemExit):
        cli.main()
    monkeypatch.setattr(sys, "argv", ["beammpy", "list-users", "--data-dir", str(tmp_path)])
    cli.main()
    output = capsys.readouterr().out
    assert "owner  administrator  enabled" in output
    assert "firstCLI" not in output
    app = create_app({"TESTING": True, "DATA_DIR": tmp_path, "SECRET_KEY": "test"})
    try:
        client = app.test_client()
        assert not client.get("/api/auth/session").json["setup_required"]
        assert client.post("/api/auth/login", json={"username": "owner", "password": "firstCLI"}, headers=headers(client)).json["user"]["is_admin"]
    finally:
        app.extensions["shutdown"]()
