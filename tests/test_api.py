# tests/test_api.py
def test_api_register_login_me_logout_flow(client):
    # Register
    r = client.post("/auth/api/register", json={
        "email": "api@example.com",
        "username": "apiuser",
        "password": "apisecret",
        "bio": "API for all time",
    })
    assert r.status_code == 201

    # Login
    r = client.post("/auth/api/login", json={
        "email": "api@example.com",
        "password": "apisecret",
    })
    assert r.status_code == 200
    assert r.is_json and r.get_json()["message"] == "logged in"

    # Me
    me = client.get("/auth/api/me")
    assert me.status_code == 200
    payload = me.get_json()
    assert payload["email"] == "api@example.com"
    assert payload["username"] == "apiuser"
    assert "bio" in payload

    # Logout
    out = client.post("/auth/api/logout")
    assert out.status_code == 200
    assert out.get_json()["message"] == "logged out"
