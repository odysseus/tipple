from __future__ import annotations

from sqlalchemy.exc import IntegrityError


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

def test_register_html_duplicate_email_shows_error(client, db, make_user):
    make_user(email="dup@example.com", username="original", password="pw")
    resp = client.post(
        "/auth/register",
        data={
            "email": "dup@example.com",
            "username": "someone_else",
            "password": "secret123",
            "confirm": "secret123",
        },
        follow_redirects=True,  # form re-renders with errors (200)
    )
    
    # On failed signup should redirect and flash error message
    assert resp.status_code == 200
    assert b"That email is already registered." in resp.data

    # Still only one user
    from tipple.models import User
    assert User.query.count() == 1


def test_register_html_duplicate_username_shows_error(client, db, make_user):
    make_user(email="one@example.com", username="dupeuser", password="pw")
    resp = client.post(
        "/auth/register",
        data={
            "email": "new@example.com",
            "username": "dupeuser",
            "password": "secret123",
            "confirm": "secret123",
        },
        follow_redirects=True,
    )

    # On failed signup should redirect and flash error message
    assert resp.status_code == 200
    assert b"That username is taken." in resp.data

    from tipple.models import User
    assert User.query.count() == 1


def test_api_register_duplicate_email_returns_409(client, db, make_user):
    make_user(email="dup@example.com", username="original", password="pw")
    r = client.post(
        "/auth/api/register",
        json={"email": "dup@example.com", "username": "newuser", "password": "pw2"},
    )
    assert r.status_code == 409
    assert r.is_json
    assert r.get_json().get("error") == "email or username already in use"


def test_api_register_duplicate_username_returns_409(client, db, make_user):
    make_user(email="orig@example.com", username="dupeuser", password="pw")
    r = client.post(
        "/auth/api/register",
        json={"email": "new@example.com", "username": "dupeuser", "password": "pw2"},
    )
    assert r.status_code == 409
    assert r.is_json
    assert r.get_json().get("error") == "email or username already in use"


def test_model_uniqueness_duplicate_email_raises_integrity_error(db, make_user):
    # First user
    u1 = make_user(email="dup@example.com", username="user1")
    from tipple.models import User
    # Second user with same email
    u2 = User(email="dup@example.com", username="user2")
    u2.set_password("pw")
    db.session.add(u2)
    try:
        db.session.commit()
        raised = False
    except IntegrityError:
        db.session.rollback()
        raised = True
    assert raised, "Expected IntegrityError on duplicate email"


def test_model_uniqueness_duplicate_username_raises_integrity_error(db, make_user):
    make_user(email="one@example.com", username="dupeuser")
    from tipple.models import User
    u2 = User(email="two@example.com", username="dupeuser")
    u2.set_password("pw")
    db.session.add(u2)
    try:
        db.session.commit()
        raised = False
    except IntegrityError:
        db.session.rollback()
        raised = True
    assert raised, "Expected IntegrityError on duplicate username"