"""The local server refuses junk dates before they can be built or stored."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EVERYDAYPASSION_HOME", str(tmp_path))
    from everydaypassion.web.app import create_app

    return TestClient(create_app(online=False)), tmp_path


@pytest.mark.parametrize("bad", ["not-a-date", "20260619", "2999-01-01"])
def test_bad_dates_are_404_and_never_stored(client, bad):
    c, home = client
    assert c.get(f"/day/{bad}").status_code == 404
    assert c.post(f"/favorite/{bad}").status_code == 404
    assert not list((home / "packages").glob("*.json"))
    assert c.get("/archive").status_code == 200
    assert c.get("/favorites").status_code == 200


def test_a_real_past_date_still_builds(client):
    c, home = client
    assert c.get("/day/2026-06-19").status_code == 200
    assert (home / "packages" / "2026-06-19.json").exists()
