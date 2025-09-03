# tests/test_channels_api.py
from __future__ import annotations

import pytest


@pytest.fixture()
def make_channel(db):
    """Create a Channel directly via the model (when needed)."""
    from tipple.models import Channel
    def _make(name: str = "general", parent: Channel | None = None) -> Channel:
        ch = Channel(name=name)
        if parent:
            ch.parent = parent
        db.session.add(ch)
        db.session.commit()
        return ch
    return _make


def test_create_channel_requires_login(client):
    resp = client.post("/channels/api/new")
    # Flask-Login usually redirects (302) when unauthenticated;
    # if you've customized unauthorized to return 401, accept that too.
    assert resp.status_code in (302, 401)


def test_create_channel_success_with_parent(client, db, make_user, login, make_channel):
    # Make a parent channel directly
    parent = make_channel("platform")

    # Login
    u = make_user(email="creator@example.com", username="creator", password="pw")
    login(identifier=u.email, password="pw")

    # Create child via API, passing parent_id in JSON body
    resp = client.post(f"/channels/api/new", json={"parent_id": parent.id, "name": "dev"})
    assert resp.status_code == 201
    assert resp.is_json
    payload = resp.get_json()
    assert payload["name"] == "dev"
    assert payload["parent_id"] == parent.id
    assert "id" in payload

    # Fetch it back by GET
    cid = payload["id"]
    g = client.get(f"/channels/api/{cid}")
    assert g.status_code == 200
    data = g.get_json()
    assert data["id"] == cid
    assert data["name"] == "dev"
    assert data["parent_id"] == parent.id


def test_create_channel_duplicate_name_conflict(client, make_user, login, make_channel):
    # Seed an existing channel with this name
    make_channel("dev")

    u = make_user(email="dupe@example.com", username="dupe", password="pw")
    login(identifier=u.email, password="pw")

    r = client.post("/channels/api/new", json={"name": "dev"})
    # Expect conflict (the route should guard and/or DB UNIQUE enforces it)
    assert r.status_code == 409
    assert r.is_json
    assert "error" in r.get_json()


def test_get_channel_not_found(client):
    resp = client.get("/channels/api/999999")
    assert resp.status_code == 404


def test_follow_channel_requires_login(client, make_channel):
    ch = make_channel("random")
    r = client.post(f"/channels/api/{ch.id}")
    assert r.status_code in (302, 401)


def test_follow_channel_success_and_idempotent(client, db, make_user, login, make_channel):
    from tipple.models import User, Channel
    ch = make_channel("news")
    u = make_user(email="follower@example.com", username="follower", password="pw")
    login(identifier=u.email, password="pw")

    # First follow
    r1 = client.post(f"/channels/api/{ch.id}")
    assert r1.status_code in (200, 201)  # your route returns 201 on first follow
    assert r1.is_json
    assert "message" in r1.get_json()

    # DB reflects following
    # Re-fetch to ensure session sees the relationship update
    user = db.session.get(User, u.id)
    chan = db.session.get(Channel, ch.id)
    if hasattr(user, "following"):
        assert chan in user.following

    # Idempotent second follow
    r2 = client.post(f"/channels/api/{ch.id}")
    assert r2.status_code in (200, 201)
    msg = r2.get_json().get("message", "")
    # Route typically says "already following" on the second call
    assert "following" in msg.lower()
