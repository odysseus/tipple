# tests/test_auth_pages.py
def test_register_page_loads(client):
    resp = client.get("/auth/register")
    assert resp.status_code == 200
    assert b"Create your account" in resp.data


def test_register_then_me_page(client, db):
    # Register via HTML form
    resp = client.post(
        "/auth/register",
        data={
            "email": "new@ex.com",
            "username": "newbie",
            "password": "secret123",
            "confirm": "secret123",
        },
        follow_redirects=True,
    )
    # Redirect lands on index (JSON) or another page; ensure request is OK
    assert resp.status_code == 200

    # Now the user is logged in; /auth/me should render
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert b"new@ex.com" in me.data
    assert b"newbie" in me.data


def test_login_bad_credentials_returns_401(client, make_user):
    make_user(email="bob@example.com", username="bob", password="correct-horse")
    resp = client.post(
        "/auth/login",
        data={"identifier": "bob@example.com", "password": "wrong"},
        follow_redirects=False,
    )
    assert resp.status_code == 401
    assert b"Invalid credentials" in resp.data


def test_logout_flow(client, make_user, login):
    make_user()
    login()
    # logout (HTML route)
    out = client.post("/auth/logout", follow_redirects=False)
    assert out.status_code in (302, 303)

    # access to /auth/me should now redirect to login
    me = client.get("/auth/me", follow_redirects=False)
    assert me.status_code in (302, 303)
